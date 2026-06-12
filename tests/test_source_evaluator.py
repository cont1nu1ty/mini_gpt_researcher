from __future__ import annotations

from source_evaluator import SourceEvaluator


class FakeLLM:
    def __init__(self, response: str) -> None:
        self.response = response

    def chat(self, prompt: str, system_prompt: str | None = None, temperature: float = 0.3, **kwargs) -> str:
        return self.response


def test_source_evaluator_keeps_correct_source_with_refined_content():
    evaluator = SourceEvaluator(
        FakeLLM(
            """
            {
              "label": "correct",
              "score": 0.9,
              "reason": "内容直接讨论高校教学中的智能助教。",
              "refined_content": "高校正在使用 AI Agent 进行答疑和个性化反馈。"
            }
            """
        )
    )

    page = {
        "title": "AI Agent 教学应用",
        "url": "https://example.com/ai-agent-education",
        "query": "AI Agent 在高校教学中的应用现状",
        "content": "无关导航。高校正在使用 AI Agent 进行答疑和个性化反馈。",
    }

    evaluated = evaluator.evaluate(page)

    assert evaluated["evaluation_label"] == "correct"
    assert evaluated["evaluation_score"] == 0.9
    assert evaluated["content"] == "高校正在使用 AI Agent 进行答疑和个性化反馈。"


def test_source_evaluator_filters_incorrect_sources():
    evaluator = SourceEvaluator(
        FakeLLM(
            """
            {
              "label": "incorrect",
              "score": 0.1,
              "reason": "正文主要是广告和导航。",
              "refined_content": ""
            }
            """
        )
    )

    pages = [
        {
            "title": "广告页",
            "url": "https://example.com/ad",
            "query": "AI Agent 在高校教学中的应用现状",
            "content": "广告 导航 联系我们",
        }
    ]

    assert evaluator.evaluate_many(pages) == []


def test_source_evaluator_uses_heuristic_fallback_on_bad_json():
    evaluator = SourceEvaluator(FakeLLM("not json"))
    page = {
        "title": "AI Agent 教学",
        "url": "https://example.com/fallback",
        "query": "AI Agent 教学",
        "content": "AI Agent 教学 可以用于课堂答疑和学习反馈。" * 20,
    }

    evaluated = evaluator.evaluate(page)

    assert evaluated["evaluation_label"] == "ambiguous"
    assert evaluated["evaluation_score"] == 0.55
    assert "本地规则" in evaluated["evaluation_reason"]
