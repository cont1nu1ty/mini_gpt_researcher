from __future__ import annotations

import re
from collections import Counter
from difflib import SequenceMatcher
from math import sqrt

from utils import clean_text, truncate_text


class EvidenceRefiner:
    def __init__(self, *, max_passages_per_page: int = 3, passage_chars: int = 900) -> None:
        self.max_passages_per_page = max_passages_per_page
        self.passage_chars = passage_chars

    def refine(self, pages: list[dict], evaluation: dict, original_query: str) -> list[dict]:
        accepted_urls = set(evaluation.get("accepted_urls", []))
        rejected_urls = set(evaluation.get("rejected_urls", []))
        candidates = [page for page in pages if page.get("url") in accepted_urls]
        if not candidates:
            candidates = [page for page in pages if page.get("url") not in rejected_urls and page.get("content")]
        if not candidates:
            candidates = [page for page in pages if page.get("content")]
        candidates = sorted(candidates, key=self._source_priority)

        refined = []
        seen_passages: list[str] = []
        for page in candidates:
            passages = self._top_passages(page, original_query, seen_passages)
            if not passages:
                continue
            seen_passages.extend(passages)
            refined.append(
                {
                    **page,
                    "content": "\n\n".join(passages),
                    "evidence_passages": passages,
                    "evaluation_label": self._evaluation_label(page, accepted_urls),
                    "evaluation_score": page.get("evaluation_score", evaluation.get("relevance", 0.5)),
                    "evaluation_reason": page.get("evaluation_reason", evaluation.get("reason", "低置信候选证据。")),
                    "possible_conflict": self._has_conflict_markers(passages),
                    "refinement_reason": "按 query 关键词重合、本地去重和段落长度保留 top passages。",
                }
            )
        return refined

    def _top_passages(self, page: dict, original_query: str, seen_passages: list[str]) -> list[str]:
        query_text = " ".join([original_query, page.get("query", ""), page.get("purpose", "")])
        query_terms = set(self._tokenize(query_text))
        query_vector = Counter(self._tokenize(query_text))
        chunks = self._chunk(page.get("content", ""))
        scored = []
        for chunk in chunks:
            if self._is_duplicate(chunk, seen_passages):
                continue
            chunk_tokens = self._tokenize(chunk)
            overlap = len(query_terms & set(chunk_tokens))
            cosine = self._cosine(query_vector, Counter(chunk_tokens))
            source_penalty = 0.4 if page.get("content_source") == "search_snippet" else 0.0
            score = overlap + cosine * 4 + min(2, len(chunk) // 300) - source_penalty
            scored.append((score, chunk))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [chunk for score, chunk in scored[: self.max_passages_per_page] if score > 0]

    def _chunk(self, text: str) -> list[str]:
        text = clean_text(text)
        if not text:
            return []
        raw_parts = [item.strip() for item in re.split(r"(?<=[。！？.!?])\s+|\n+", text) if item.strip()]
        chunks = []
        buffer = ""
        for part in raw_parts:
            if len(buffer) + len(part) <= self.passage_chars:
                buffer = f"{buffer} {part}".strip()
                continue
            if buffer:
                chunks.append(truncate_text(buffer, self.passage_chars))
            buffer = part
        if buffer:
            chunks.append(truncate_text(buffer, self.passage_chars))
        if not chunks and text:
            chunks.append(truncate_text(text, self.passage_chars))
        return chunks

    def _tokenize(self, text: str) -> list[str]:
        text = clean_text(text).lower()
        tokens = [item for item in re.findall(r"[a-z0-9][a-z0-9_\-]{1,}", text)]
        for chunk in re.findall(r"[\u4e00-\u9fff]{2,}", text):
            tokens.append(chunk)
            tokens.extend(chunk[index : index + 2] for index in range(max(0, len(chunk) - 1)))
        return tokens

    def _is_duplicate(self, passage: str, seen_passages: list[str]) -> bool:
        return any(SequenceMatcher(None, passage, seen).ratio() > 0.88 for seen in seen_passages)

    def _has_conflict_markers(self, passages: list[str]) -> bool:
        text = " ".join(passages)
        return any(marker in text for marker in ["相反", "争议", "不一致", "contradict", "conflict"])

    def _source_priority(self, page: dict) -> tuple[int, int]:
        source = page.get("content_source", "web_page")
        priority = {
            "retriever_raw_content": 0,
            "web_page": 1,
            "search_snippet": 2,
        }.get(source, 1)
        return priority, -len(page.get("content", ""))

    def _evaluation_label(self, page: dict, accepted_urls: set[str]) -> str:
        if page.get("content_source") == "search_snippet":
            return "ambiguous"
        return "correct" if page.get("url") in accepted_urls else "ambiguous"

    def _cosine(self, left: Counter, right: Counter) -> float:
        if not left or not right:
            return 0.0
        numerator = sum(left[token] * right.get(token, 0) for token in left)
        left_norm = sqrt(sum(value * value for value in left.values()))
        right_norm = sqrt(sum(value * value for value in right.values()))
        if not left_norm or not right_norm:
            return 0.0
        return numerator / (left_norm * right_norm)
