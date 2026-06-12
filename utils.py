from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_ROOT / "outputs"


def ensure_output_dir() -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUTPUT_DIR


def save_markdown(markdown: str, filename: str = "report.md") -> Path:
    output_dir = ensure_output_dir()
    path = output_dir / filename
    path.write_text(markdown, encoding="utf-8")
    return path


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "")
    return text.strip()


def truncate_text(text: str, max_chars: int) -> str:
    text = clean_text(text)
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + "\n\n[内容已截断]"


def unique_by_url(items: Iterable[dict]) -> list[dict]:
    seen: set[str] = set()
    unique: list[dict] = []
    for item in items:
        url = str(item.get("url", "")).strip()
        if not url or url in seen:
            continue
        seen.add(url)
        unique.append(item)
    return unique


def tokenize_for_relevance(text: str) -> set[str]:
    text = clean_text(text).lower()
    tokens = {item for item in re.findall(r"[a-z0-9][a-z0-9_\-]{1,}", text)}
    for chunk in re.findall(r"[\u4e00-\u9fff]{2,}", text):
        tokens.add(chunk)
        tokens.update(chunk[index : index + 2] for index in range(max(0, len(chunk) - 1)))
    return tokens


def relevance_overlap(left: str, right: str) -> int:
    return len(tokenize_for_relevance(left) & tokenize_for_relevance(right))


def parse_json_object(text: str) -> dict:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if not match:
            raise
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("JSON 不是对象。")
    return parsed


def parse_json_array(text: str) -> list:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", raw, flags=re.DOTALL)
        if not match:
            raise
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, list):
        raise ValueError("JSON 不是数组。")
    return parsed
