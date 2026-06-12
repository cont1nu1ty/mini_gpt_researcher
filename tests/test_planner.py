from __future__ import annotations

from config import Settings
from planner import Planner


class FakeLLM:
    def __init__(self, response: str) -> None:
        self.response = response

    def chat(self, prompt: str, system_prompt: str | None = None, temperature: float = 0.3, **kwargs) -> str:
        return self.response


class FailingLLM:
    def chat(self, prompt: str, system_prompt: str | None = None, temperature: float = 0.3, **kwargs) -> str:
        raise RuntimeError("Request timed out.")


def test_planner_parses_json_array():
    planner = Planner(FakeLLM('["问题一？", "问题二？"]'), Settings(zai_api_key="test"))

    assert planner.plan("原问题") == ["问题一？", "问题二？"]


def test_planner_fallbacks_to_original_query():
    planner = Planner(FakeLLM("not json"), Settings(zai_api_key="test"))

    assert planner.plan("原问题") == ["原问题"]


def test_planner_fallbacks_when_llm_call_fails(capsys):
    planner = Planner(FailingLLM(), Settings(zai_api_key="test"))

    assert planner.plan("原问题") == ["原问题"]
    captured = capsys.readouterr()
    assert "子问题规划模型调用失败" in captured.out
    assert "子问题 JSON 解析失败" not in captured.out
