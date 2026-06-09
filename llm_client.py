from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from config import Settings


class LLMClient:
    def __init__(self, settings: "Settings") -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - depends on local env
            raise RuntimeError("缺少 openai 依赖，请先运行 `pip install -r requirements.txt`。") from exc

        self.settings = settings
        self.client = OpenAI(api_key=settings.zai_api_key, base_url=settings.zai_base_url)

    def chat(self, prompt: str, system_prompt: Optional[str] = None, temperature: float = 0.3) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = self.client.chat.completions.create(
                model=self.settings.zai_model,
                messages=messages,
                temperature=temperature,
            )
        except Exception as exc:  # pragma: no cover - real API boundary
            raise RuntimeError(f"模型调用失败：{exc}") from exc

        content = response.choices[0].message.content if response.choices else ""
        return (content or "").strip()
