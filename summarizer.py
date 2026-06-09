from __future__ import annotations

import json

from llm_client import LLMClient
from prompts import SUMMARIZER_PROMPT, SUMMARIZER_SYSTEM_PROMPT


class Summarizer:
    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def summarize_many(self, pages: list[dict]) -> list[dict]:
        summaries: list[dict] = []
        for page in pages:
            summary = self.summarize(page)
            if summary:
                summaries.append(summary)
        return summaries

    def summarize(self, page: dict) -> dict | None:
        content = page.get("content", "").strip()
        if not content:
            return None

        prompt = SUMMARIZER_PROMPT.format(
            query=page.get("query", ""),
            title=page.get("title", ""),
            url=page.get("url", ""),
            content=content,
        )
        try:
            response = self.llm.chat(prompt, system_prompt=SUMMARIZER_SYSTEM_PROMPT, temperature=0.2)
        except Exception as exc:
            print(f"Warning: 摘要模型调用失败，跳过来源。url={page.get('url')}，原因：{exc}")
            return None

        try:
            parsed = json.loads(response)
            summary = str(parsed.get("summary", "")).strip()
            key_points = [str(item).strip() for item in parsed.get("key_points", []) if str(item).strip()]
        except Exception as exc:
            print(f"Warning: 摘要 JSON 解析失败，使用文本 fallback。url={page.get('url')}，原因：{exc}")
            summary = response.strip()
            key_points = []

        return {
            "title": page.get("title", ""),
            "url": page.get("url", ""),
            "query": page.get("query", ""),
            "summary": summary,
            "key_points": key_points,
        }
