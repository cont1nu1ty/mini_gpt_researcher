from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from action_router import ActionRouter  # noqa: E402
from config import Settings  # noqa: E402
from evidence_refiner import EvidenceRefiner  # noqa: E402
from query_planner import QueryPlanner  # noqa: E402
from retrieval_evaluator import RetrievalEvaluator  # noqa: E402
from verifier import Verifier  # noqa: E402
from writer import REQUIRED_SECTIONS, Writer  # noqa: E402


class FakeWriterLLM:
    def chat(self, prompt: str, system_prompt: str | None = None, temperature: float = 0.3, **kwargs) -> str:
        return "\n".join(
            [
                "# AI Agent 在高校教学中的应用现状 调研报告",
                "",
                "## 1. 摘要",
                "这是离线评估报告。",
                "",
                "## 2. 研究问题",
                "- AI Agent 在高校教学中的应用现状",
                "",
                "## 3. 背景介绍",
                "背景来自样例摘要。",
                "",
                "## 4. 主要发现",
                "- 高校教学正在探索智能助教和个性化学习。",
                "",
                "## 5. 分主题分析",
                "- 应用场景包括答疑、反馈和学习分析。",
                "",
                "## 6. 结论",
                "仍需结合教学实践验证。",
                "",
                "## 7. 局限性",
                "本报告基于自动搜索和网页摘要生成，可能受搜索结果质量、网页可访问性和模型总结能力影响。",
                "",
                "## 8. 参考来源",
                "- 样例来源：https://example.com",
            ]
        )


class FakePlanLLM:
    def chat(self, prompt: str, system_prompt: str | None = None, temperature: float = 0.3, **kwargs) -> str:
        return json.dumps(
            {
                "question_type": "literature_review",
                "needs_freshness": True,
                "research_intent": "了解教育场景中的 AI Agent 应用",
                "sub_questions": ["AI Agent 在教育中的应用有哪些？"],
                "search_queries": [
                    {"query": "AI Agent 教育 应用", "mode": "broad", "purpose": "获取应用现状"}
                ],
            },
            ensure_ascii=False,
        )


class FakeRetrievalLLM:
    def __init__(self, label: str = "ambiguous") -> None:
        self.label = label

    def chat(self, prompt: str, system_prompt: str | None = None, temperature: float = 0.3, **kwargs) -> str:
        return json.dumps(
            {
                "label": self.label,
                "relevance": 0.8,
                "authority": 0.6,
                "freshness": 0.6,
                "coverage": 0.5,
                "contradiction": False,
                "reason": "样例来源部分覆盖问题，需要继续补搜。",
                "suggested_rewrite_queries": ["AI Agent 教育 应用 案例"],
                "accepted_urls": ["https://example.com"],
                "rejected_urls": ["https://low-quality.example.com"],
            },
            ensure_ascii=False,
        )


class FakeVerifierLLM:
    def chat(self, prompt: str, system_prompt: str | None = None, temperature: float = 0.3, **kwargs) -> str:
        return json.dumps(
            {
                "supported": True,
                "missing_user_intent": False,
                "citation_issues": [],
                "unsupported_claims": [],
                "revision_required": False,
            },
            ensure_ascii=False,
        )


def main() -> int:
    dataset = ROOT / "evals" / "datasets" / "smoke_questions.jsonl"
    report_path = ROOT / "evals" / "reports" / "offline_eval_latest.json"
    questions = [json.loads(line)["query"] for line in dataset.read_text(encoding="utf-8").splitlines() if line.strip()]

    settings = Settings(zai_api_key="test", min_accepted_sources=2, max_search_rounds=2)
    planner = QueryPlanner(FakePlanLLM(), settings)
    retrieval_evaluator = RetrievalEvaluator(FakeRetrievalLLM(), settings)
    router = ActionRouter(settings)
    refiner = EvidenceRefiner()
    writer = Writer(FakeWriterLLM())
    verifier = Verifier(FakeVerifierLLM())
    checks = []
    for query in questions:
        plan = planner.plan(query)
        pages = [
            {
                "title": "样例来源",
                "url": "https://example.com",
                "query": query,
                "content": "高校教学正在探索智能助教、个性化反馈和学习分析。" * 20,
            },
            {
                "title": "低质量来源",
                "url": "https://low-quality.example.com",
                "query": query,
                "content": "广告 导航 联系我们",
            },
        ]
        evaluation = retrieval_evaluator.evaluate(query, plan, pages, 1)
        decision = router.route(evaluation, 1)
        refined_pages = refiner.refine(pages, evaluation, query)
        markdown = writer.write(
            query,
            plan.sub_questions,
            [
                {
                    "title": "样例来源",
                    "url": "https://example.com",
                    "query": query,
                    "summary": "高校教学正在探索智能助教、个性化反馈和学习分析。",
                    "key_points": ["智能助教", "个性化反馈"],
                }
            ],
        )
        verification = verifier.verify(query, markdown, [])
        checks.append(
            {
                "query": query,
                "query_planner_generates_queries": bool(plan.search_queries),
                "retrieval_evaluator_filters_low_quality": "https://low-quality.example.com" in evaluation["rejected_urls"],
                "ambiguous_triggers_supplemental_search": decision.should_continue_search,
                "evidence_refiner_keeps_passages": bool(refined_pages and refined_pages[0]["evidence_passages"]),
                "verifier_accepts_report": verification["supported"],
                "has_required_sections": all(section in markdown for section in REQUIRED_SECTIONS),
                "has_limitation": "本报告基于自动搜索和网页摘要生成" in markdown,
                "has_reference_url": "https://example.com" in markdown,
            }
        )

    passed = all(
        all(
            item[key]
            for key in [
                "query_planner_generates_queries",
                "retrieval_evaluator_filters_low_quality",
                "ambiguous_triggers_supplemental_search",
                "evidence_refiner_keeps_passages",
                "verifier_accepts_report",
                "has_required_sections",
                "has_limitation",
                "has_reference_url",
            ]
        )
        for item in checks
    )
    payload = {"passed": passed, "cases": checks}
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
