from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from config import Settings


class LLMClient:
    def __init__(self, settings: "Settings") -> None:
        self.settings = settings
        self.provider = settings.llm_provider
        if self.provider == "zai":
            self.client = self._init_zai_client()
            return
        if self.provider == "openai_compatible":
            self.client = self._init_openai_compatible_client()
            return
        raise RuntimeError("LLM_PROVIDER 仅支持 `zai` 或 `openai_compatible`。")

    def _init_zai_client(self):
        try:
            from zai import ZhipuAiClient
        except ImportError as exc:  # pragma: no cover - depends on local env
            raise RuntimeError("缺少 zai-sdk 依赖，请先运行 `pip install -r requirements.txt`。") from exc
        return ZhipuAiClient(api_key=self.settings.zai_api_key, timeout=self.settings.llm_timeout_seconds)

    def _init_openai_compatible_client(self):
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - depends on local env
            raise RuntimeError("缺少 openai 依赖，请先运行 `pip install -r requirements.txt`。") from exc
        return OpenAI(
            api_key=self.settings.zai_api_key,
            base_url=self.settings.zai_base_url,
            timeout=self.settings.llm_timeout_seconds,
        )

    def chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int | None = None,
        thinking: str | None = None,
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        if self.provider == "zai":
            return self._chat_with_zai(messages, temperature, max_tokens=max_tokens, thinking=thinking)
        return self._chat_with_openai_compatible(messages, temperature, max_tokens=max_tokens, thinking=thinking)

    def _chat_with_zai(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        *,
        max_tokens: int | None = None,
        thinking: str | None = None,
    ) -> str:
        payload = {
            "model": self.settings.zai_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens or self.settings.zai_max_tokens,
        }
        thinking_type = thinking if thinking is not None else self.settings.zai_thinking
        if thinking_type in {"enabled", "disabled"}:
            payload["thinking"] = {"type": thinking_type}
        try:
            response = self.client.chat.completions.create(**payload)
        except Exception as exc:  # pragma: no cover - real API boundary
            raise RuntimeError(f"Z.ai SDK 模型调用失败：{exc}") from exc
        return self._extract_message_content(response)

    def _chat_with_openai_compatible(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        *,
        max_tokens: int | None = None,
        thinking: str | None = None,
    ) -> str:
        extra_body = {}
        thinking_type = thinking if thinking is not None else self.settings.zai_thinking
        if thinking_type in {"enabled", "disabled"}:
            extra_body["thinking"] = {"type": thinking_type}
        try:
            response = self.client.chat.completions.create(
                model=self.settings.zai_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens or self.settings.zai_max_tokens,
                extra_body=extra_body or None,
            )
        except Exception as exc:  # pragma: no cover - real API boundary
            raise RuntimeError(f"OpenAI-compatible 模型调用失败：{exc}") from exc
        return self._extract_message_content(response)

    def _extract_message_content(self, response) -> str:
        if not getattr(response, "choices", None):
            return ""
        message = response.choices[0].message
        if isinstance(message, dict):
            return str(message.get("content") or "").strip()
        content = response.choices[0].message.content if response.choices else ""
        return (content or "").strip()
