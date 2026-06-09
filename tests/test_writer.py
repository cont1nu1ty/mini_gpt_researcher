from __future__ import annotations

from writer import REQUIRED_SECTIONS, Writer


class FakeLLM:
    def __init__(self, response: str) -> None:
        self.response = response

    def chat(self, prompt: str, system_prompt: str | None = None, temperature: float = 0.3) -> str:
        return self.response


def test_writer_falls_back_when_sections_missing():
    writer = Writer(FakeLLM("bad report"))
    markdown = writer.write(
        "AI Agent 在高校教学中的应用现状",
        ["有哪些应用？"],
        [{"title": "来源", "url": "https://example.com", "query": "有哪些应用？", "summary": "有智能助教。"}],
    )

    assert all(section in markdown for section in REQUIRED_SECTIONS)
    assert "https://example.com" in markdown


def test_writer_empty_report_contains_limitations():
    writer = Writer(FakeLLM(""))
    markdown = writer.write("研究问题", ["研究问题"], [])

    assert "未获得可用来源" in markdown
    assert "本报告基于自动搜索和网页摘要生成" in markdown
