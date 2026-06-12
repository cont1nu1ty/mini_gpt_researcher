from __future__ import annotations

from config import Settings
from query_planner import PlannedQuery, ResearchPlan
from retrieval_evaluator import RetrievalEvaluator


class FakeLLM:
    def __init__(self, response: str) -> None:
        self.response = response

    def chat(self, prompt: str, system_prompt: str | None = None, temperature: float = 0.3, **kwargs) -> str:
        return self.response


def _plan():
    return ResearchPlan(
        question_type="buying_advice",
        needs_freshness=True,
        research_intent="挑选男士短袖",
        sub_questions=["面料怎么选？"],
        search_queries=[PlannedQuery("男士短袖 面料")],
    )


def test_retrieval_evaluator_parses_batch_result():
    evaluator = RetrievalEvaluator(
        FakeLLM(
            """
            {
              "label": "correct",
              "relevance": 0.9,
              "authority": 0.6,
              "freshness": 0.7,
              "coverage": 0.8,
              "contradiction": false,
              "reason": "来源可用",
              "suggested_rewrite_queries": [],
              "accepted_urls": ["https://example.com/a"],
              "rejected_urls": []
            }
            """
        ),
        Settings(zai_api_key="test", min_accepted_sources=1),
    )
    pages = [{"title": "A", "url": "https://example.com/a", "content": "男士短袖面料选择建议" * 20}]

    result = evaluator.evaluate("男士短袖", _plan(), pages, 1)

    assert result["label"] == "correct"
    assert result["accepted_urls"] == ["https://example.com/a"]


def test_retrieval_evaluator_heuristic_fallback_on_bad_json():
    evaluator = RetrievalEvaluator(FakeLLM("not json"), Settings(zai_api_key="test", min_accepted_sources=2))
    pages = [
        {
            "title": "男士短袖面料",
            "url": "https://example.com/a",
            "snippet": "面料",
            "content": "男士短袖 面料 夏季 速干 棉 选择 建议 " * 30,
        }
    ]

    result = evaluator.evaluate("男士短袖 面料", _plan(), pages, 1)

    assert result["label"] == "ambiguous"
    assert result["accepted_urls"] == ["https://example.com/a"]
    assert result["suggested_rewrite_queries"]


def test_retrieval_evaluator_recovers_when_model_rejects_relevant_snippet():
    evaluator = RetrievalEvaluator(
        FakeLLM(
            """
            {
              "label": "incorrect",
              "relevance": 0.1,
              "authority": 0.2,
              "freshness": 0.2,
              "coverage": 0.0,
              "contradiction": false,
              "reason": "模型认为不可用",
              "suggested_rewrite_queries": [],
              "accepted_urls": [],
              "rejected_urls": ["https://example.com/snippet"]
            }
            """
        ),
        Settings(zai_api_key="test", min_accepted_sources=2),
    )
    pages = [
        {
            "title": "男士短袖面料",
            "url": "https://example.com/snippet",
            "snippet": "男士短袖 夏季 面料 速干 棉",
            "content": "男士短袖 夏季 面料 速干 棉",
            "content_source": "search_snippet",
        }
    ]

    result = evaluator.evaluate("男士短袖 面料", _plan(), pages, 1)

    assert result["label"] == "ambiguous"
    assert result["accepted_urls"] == ["https://example.com/snippet"]
