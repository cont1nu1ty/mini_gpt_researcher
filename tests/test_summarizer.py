from __future__ import annotations

from config import Settings
from summarizer import Summarizer


class FakeLLM:
    def __init__(self, response: str) -> None:
        self.response = response
        self.last_prompt = ""

    def chat(self, prompt: str, system_prompt: str | None = None, temperature: float = 0.3, **kwargs) -> str:
        self.last_prompt = prompt
        return self.response


def test_summarizer_includes_source_evaluation_context():
    llm = FakeLLM('{"summary": "来源讨论了智能助教。", "key_points": ["智能助教"]}')
    summarizer = Summarizer(llm)

    summary = summarizer.summarize(
        {
            "title": "AI Agent 教学应用",
            "url": "https://example.com",
            "query": "AI Agent 在高校教学中的应用现状",
            "content": "高校正在探索智能助教。",
            "evaluation_label": "ambiguous",
            "evaluation_score": 0.55,
            "evaluation_reason": "部分相关但证据有限。",
            "content_source": "search_snippet",
        }
    )

    assert summary["evaluation_label"] == "ambiguous"
    assert summary["evaluation_score"] == 0.55
    assert summary["content_source"] == "search_snippet"
    assert "label: ambiguous" in llm.last_prompt
    assert "部分相关但证据有限" in llm.last_prompt
    assert "不要使用“该网页与研究子问题相关”" in llm.last_prompt


def test_summarizer_parses_fenced_json_response():
    llm = FakeLLM(
        """
        ```json
        {
          "summary": "短袖克重建议为180到220克。",
          "key_points": ["180-220克较适合夏季", "过厚会闷热"]
        }
        ```
        """
    )
    summarizer = Summarizer(llm)

    summary = summarizer.summarize(
        {
            "title": "短袖克重",
            "url": "https://example.com",
            "query": "短袖克重怎么选",
            "content": "夏季短袖克重建议为180到220克。",
        }
    )

    assert summary["summary"] == "短袖克重建议为180到220克。"
    assert summary["key_points"] == ["180-220克较适合夏季", "过厚会闷热"]


def test_summarizer_extractive_mode_keeps_evidence_without_model_call():
    class FailingLLM:
        def chat(self, *args, **kwargs):
            raise AssertionError("extractive mode should not call LLM")

    summarizer = Summarizer(FailingLLM(), Settings(zai_api_key="test", summarizer_mode="extractive"))

    summary = summarizer.summarize(
        {
            "title": "短袖克重",
            "url": "https://example.com/weight",
            "query": "短袖克重怎么选",
            "content": "夏季短袖克重建议为220g到250g，能兼顾透气和挺括。领口建议选择二本针工艺。",
            "content_source": "web_page",
        }
    )

    assert summary["url"] == "https://example.com/weight"
    assert summary["content_source"] == "web_page"
    assert "220g到250g" in summary["summary"]
    assert any("领口" in item for item in summary["key_points"])
