from __future__ import annotations

from config import Settings
from query_planner import QueryPlanner


class FakeLLM:
    def __init__(self, response: str) -> None:
        self.response = response
        self.last_prompt = ""

    def chat(self, prompt: str, system_prompt: str | None = None, temperature: float = 0.3, **kwargs) -> str:
        self.last_prompt = prompt
        return self.response


class FailingLLM:
    def chat(self, prompt: str, system_prompt: str | None = None, temperature: float = 0.3, **kwargs) -> str:
        raise RuntimeError("timeout")


def test_query_planner_parses_structured_plan():
    planner = QueryPlanner(
        FakeLLM(
            """
            {
              "question_type": "buying_advice",
              "needs_freshness": true,
              "research_intent": "挑选北京夏季男士短袖",
              "sub_questions": ["面料怎么选？"],
              "search_queries": [
                {"query": "北京 夏季 男士 短袖 面料", "mode": "targeted", "purpose": "面料对比"}
              ]
            }
            """
        ),
        Settings(zai_api_key="test"),
    )

    plan = planner.plan("北京夏季男性短袖购买，材质工艺挑选")

    assert plan.question_type == "buying_advice"
    assert plan.needs_freshness is True
    assert plan.search_queries[0].mode == "targeted"
    assert plan.search_queries[0].purpose == "面料对比"


def test_query_planner_fallbacks_to_original_query():
    planner = QueryPlanner(FailingLLM(), Settings(zai_api_key="test"))

    plan = planner.plan("原问题")

    assert plan.sub_questions == ["原问题"]
    assert plan.search_queries[0].query == "原问题"
    assert plan.search_queries[0].mode == "broad"


def test_query_planner_filters_ungrounded_model_queries():
    planner = QueryPlanner(
        FakeLLM(
            """
            {
              "question_type": "buying_advice",
              "needs_freshness": true,
              "research_intent": "北京夏季男士短袖选购",
              "sub_questions": ["面料怎么选？"],
              "search_queries": [
                {"query": "novafms Pro APP Review", "mode": "targeted", "purpose": "坏 query"},
                {"query": "北京 夏季 男士短袖 面料", "mode": "targeted", "purpose": "好 query"}
              ]
            }
            """
        ),
        Settings(zai_api_key="test"),
    )

    plan = planner.plan("北京夏季男性短袖购买，材质工艺挑选")

    assert [item.query for item in plan.search_queries] == ["北京 夏季 男士短袖 面料"]


def test_query_planner_includes_initial_search_context():
    llm = FakeLLM(
        """
        {
          "question_type": "buying_advice",
          "needs_freshness": false,
          "research_intent": "北京夏季短袖选购",
          "sub_questions": ["面料怎么选？"],
          "search_queries": [
            {"query": "北京 夏季 男士短袖 面料", "mode": "targeted", "purpose": "面料对比"}
          ]
        }
        """
    )
    planner = QueryPlanner(llm, Settings(zai_api_key="test"))

    planner.plan(
        "北京夏季男性短袖购买，材质工艺挑选",
        initial_results=[
            {
                "title": "北京夏季短袖选购",
                "url": "https://example.com/search",
                "snippet": "棉、速干和凉感面料对比。",
            }
        ],
    )

    assert "初始搜索结果" in llm.last_prompt
    assert "棉、速干和凉感面料对比" in llm.last_prompt
