from __future__ import annotations

import re

from config import Settings
from llm_client import LLMClient
from prompts import SUMMARIZER_PROMPT, SUMMARIZER_SYSTEM_PROMPT
from utils import clean_text, parse_json_object, truncate_text


class Summarizer:
    def __init__(self, llm: LLMClient, settings: Settings | None = None) -> None:
        self.llm = llm
        self.mode = getattr(settings, "summarizer_mode", "llm")

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
        if self.mode != "llm":
            return self._extractive_summary(page)

        prompt = SUMMARIZER_PROMPT.format(
            query=page.get("query", ""),
            title=page.get("title", ""),
            url=page.get("url", ""),
            evaluation_label=page.get("evaluation_label", "unknown"),
            evaluation_score=page.get("evaluation_score", "unknown"),
            evaluation_reason=page.get("evaluation_reason", "未经过来源评估。"),
            content=content,
        )
        try:
            response = self.llm.chat(prompt, system_prompt=SUMMARIZER_SYSTEM_PROMPT, temperature=0.2)
        except Exception as exc:
            print(f"Warning: 摘要模型调用失败，跳过来源。url={page.get('url')}，原因：{exc}")
            return None

        try:
            parsed = parse_json_object(response)
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
            "evaluation_label": page.get("evaluation_label", "unknown"),
            "evaluation_score": page.get("evaluation_score", "unknown"),
            "evaluation_reason": page.get("evaluation_reason", ""),
            "content_source": page.get("content_source", "web_page"),
        }

    def _extractive_summary(self, page: dict) -> dict:
        content = clean_text(str(page.get("content", "")))
        passages = page.get("evidence_passages") or self._split_passages(content)
        passages = [clean_text(str(item)) for item in passages if clean_text(str(item))]
        key_points = []
        for passage in passages:
            for sentence in self._split_sentences(passage):
                if self._looks_informative(sentence):
                    key_points.append(truncate_text(sentence, 180))
                if len(key_points) >= 5:
                    break
            if len(key_points) >= 5:
                break
        if not key_points and passages:
            key_points = [truncate_text(passages[0], 180)]
        summary = truncate_text(" ".join(passages[:2]) or content, 700)
        return {
            "title": page.get("title", ""),
            "url": page.get("url", ""),
            "query": page.get("query", ""),
            "summary": summary,
            "key_points": key_points[:5],
            "evaluation_label": page.get("evaluation_label", "unknown"),
            "evaluation_score": page.get("evaluation_score", "unknown"),
            "evaluation_reason": page.get("evaluation_reason", ""),
            "content_source": page.get("content_source", "web_page"),
        }

    def _split_passages(self, content: str) -> list[str]:
        return [item.strip() for item in re.split(r"\n{2,}", content) if item.strip()]

    def _split_sentences(self, text: str) -> list[str]:
        return [item.strip() for item in re.split(r"(?<=[。！？.!?])\s+", text) if item.strip()]

    def _looks_informative(self, sentence: str) -> bool:
        if len(sentence) < 12:
            return False
        useful_markers = [
            "棉",
            "麻",
            "涤纶",
            "聚酯",
            "速干",
            "克重",
            "支数",
            "领口",
            "工艺",
            "透气",
            "吸湿",
            "排汗",
            "防晒",
            "缩水",
            "起球",
            "北京",
            "夏季",
            "℃",
            "g",
            "%",
        ]
        return any(marker in sentence for marker in useful_markers)
