from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from writer import REQUIRED_SECTIONS, Writer  # noqa: E402


class FakeLLM:
    def chat(self, prompt: str, system_prompt: str | None = None, temperature: float = 0.3) -> str:
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


def main() -> int:
    dataset = ROOT / "evals" / "datasets" / "smoke_questions.jsonl"
    report_path = ROOT / "evals" / "reports" / "offline_eval_latest.json"
    questions = [json.loads(line)["query"] for line in dataset.read_text(encoding="utf-8").splitlines() if line.strip()]

    writer = Writer(FakeLLM())
    checks = []
    for query in questions:
        markdown = writer.write(
            query,
            [query],
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
        checks.append(
            {
                "query": query,
                "has_required_sections": all(section in markdown for section in REQUIRED_SECTIONS),
                "has_limitation": "本报告基于自动搜索和网页摘要生成" in markdown,
                "has_reference_url": "https://example.com" in markdown,
            }
        )

    passed = all(all(item[key] for key in ["has_required_sections", "has_limitation", "has_reference_url"]) for item in checks)
    payload = {"passed": passed, "cases": checks}
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
