from __future__ import annotations

import sys
import types

from config import Settings
from llm_client import LLMClient


class FakeMessage:
    content = "模型回复"


class FakeChoice:
    message = FakeMessage()


class FakeResponse:
    choices = [FakeChoice()]


def test_llm_client_uses_zai_provider_by_default(monkeypatch):
    calls = {}

    class FakeCompletions:
        def create(self, **payload):
            calls.update(payload)
            return FakeResponse()

    class FakeClient:
        def __init__(self, api_key: str, timeout: int):
            calls["api_key"] = api_key
            calls["timeout"] = timeout
            self.chat = types.SimpleNamespace(completions=FakeCompletions())

    fake_zai = types.SimpleNamespace(ZhipuAiClient=FakeClient)
    monkeypatch.setitem(sys.modules, "zai", fake_zai)

    client = LLMClient(Settings(zai_api_key="test-key"))
    result = client.chat("你好", temperature=0.7)

    assert result == "模型回复"
    assert calls["api_key"] == "test-key"
    assert calls["timeout"] == 60
    assert calls["model"] == "glm-5.1"
    assert calls["thinking"] == {"type": "enabled"}
    assert calls["temperature"] == 0.7


def test_llm_client_allows_per_call_generation_overrides(monkeypatch):
    calls = {}

    class FakeCompletions:
        def create(self, **payload):
            calls.update(payload)
            return FakeResponse()

    class FakeClient:
        def __init__(self, api_key: str, timeout: int):
            self.chat = types.SimpleNamespace(completions=FakeCompletions())

    fake_zai = types.SimpleNamespace(ZhipuAiClient=FakeClient)
    monkeypatch.setitem(sys.modules, "zai", fake_zai)

    client = LLMClient(Settings(zai_api_key="test-key"))
    client.chat("写报告", max_tokens=4096, thinking="disabled")

    assert calls["max_tokens"] == 4096
    assert calls["thinking"] == {"type": "disabled"}


def test_llm_client_openai_compatible_provider(monkeypatch):
    calls = {}

    class FakeCompletions:
        def create(self, **payload):
            calls.update(payload)
            return FakeResponse()

    class FakeOpenAI:
        def __init__(self, api_key: str, base_url: str, timeout: int):
            calls["api_key"] = api_key
            calls["base_url"] = base_url
            calls["timeout"] = timeout
            self.chat = types.SimpleNamespace(completions=FakeCompletions())

    fake_openai = types.SimpleNamespace(OpenAI=FakeOpenAI)
    monkeypatch.setitem(sys.modules, "openai", fake_openai)

    client = LLMClient(Settings(zai_api_key="test-key", llm_provider="openai_compatible"))
    result = client.chat("你好")

    assert result == "模型回复"
    assert calls["api_key"] == "test-key"
    assert calls["base_url"] == "https://open.bigmodel.cn/api/paas/v4"
    assert calls["timeout"] == 60
    assert calls["model"] == "glm-5.1"
    assert calls["extra_body"] == {"thinking": {"type": "enabled"}}
