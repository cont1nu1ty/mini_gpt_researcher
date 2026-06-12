from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - only used before dependencies are installed
    def load_dotenv(*args, **kwargs):
        return False


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_ZAI_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"


class ConfigError(RuntimeError):
    """Raised when required runtime configuration is missing."""


@dataclass(frozen=True)
class Settings:
    zai_api_key: str
    llm_provider: str = "zai"
    zai_base_url: str = DEFAULT_ZAI_BASE_URL
    zai_model: str = "glm-5.1"
    zai_thinking: str = "enabled"
    zai_max_tokens: int = 128000
    llm_timeout_seconds: int = 60
    max_sub_questions: int = 4
    max_planned_queries: int = 6
    search_provider: str = "auto"
    search_aggregate_providers: bool = True
    tavily_api_key: str = ""
    tavily_include_raw_content: bool = True
    searxng_base_url: str = ""
    max_search_results: int = 4
    max_search_workers: int = 4
    max_web_pages: int = 8
    max_search_rounds: int = 2
    max_rewrite_queries: int = 3
    min_accepted_sources: int = 4
    output_language: str = "zh-CN"
    request_timeout_seconds: int = 12
    max_content_chars: int = 12000
    summarizer_mode: str = "extractive"
    report_type: str = "research_report"
    report_format: str = "APA"
    total_words: int = 1200
    writer_prompt_style: str = "gpt_researcher"


def load_settings(require_api_key: bool = True) -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.getenv("ZAI_API_KEY", "").strip()
    if require_api_key and not api_key:
        raise ConfigError(
            "缺少 ZAI_API_KEY。请先执行 `cp .env.example .env`，然后在 .env 中填写真实 API Key。"
        )
    return Settings(
        zai_api_key=api_key,
        llm_provider=os.getenv("LLM_PROVIDER", "zai").strip() or "zai",
        zai_base_url=os.getenv("ZAI_BASE_URL", DEFAULT_ZAI_BASE_URL).strip(),
        zai_model=os.getenv("ZAI_MODEL", "glm-5.1").strip(),
        zai_thinking=os.getenv("ZAI_THINKING", "enabled").strip() or "enabled",
        zai_max_tokens=_get_int("ZAI_MAX_TOKENS", 65536, minimum=512, maximum=65536),
        llm_timeout_seconds=_get_int("LLM_TIMEOUT_SECONDS", 60, minimum=10, maximum=300),
        max_sub_questions=_get_int("MAX_SUB_QUESTIONS", 4, minimum=1, maximum=8),
        max_planned_queries=_get_int("MAX_PLANNED_QUERIES", 6, minimum=1, maximum=12),
        search_provider=os.getenv("SEARCH_PROVIDER", "auto").strip() or "auto",
        search_aggregate_providers=_get_bool("SEARCH_AGGREGATE_PROVIDERS", True),
        tavily_api_key=os.getenv("TAVILY_API_KEY", "").strip(),
        tavily_include_raw_content=_get_bool("TAVILY_INCLUDE_RAW_CONTENT", True),
        searxng_base_url=os.getenv("SEARXNG_BASE_URL", "").strip().rstrip("/"),
        max_search_results=_get_int("MAX_SEARCH_RESULTS", 4, minimum=1, maximum=10),
        max_search_workers=_get_int("MAX_SEARCH_WORKERS", 4, minimum=1, maximum=12),
        max_web_pages=_get_int("MAX_WEB_PAGES", 8, minimum=1, maximum=30),
        max_search_rounds=_get_int("MAX_SEARCH_ROUNDS", 2, minimum=1, maximum=4),
        max_rewrite_queries=_get_int("MAX_REWRITE_QUERIES", 3, minimum=1, maximum=8),
        min_accepted_sources=_get_int("MIN_ACCEPTED_SOURCES", 4, minimum=1, maximum=20),
        output_language=os.getenv("OUTPUT_LANGUAGE", "zh-CN").strip() or "zh-CN",
        request_timeout_seconds=_get_int("REQUEST_TIMEOUT_SECONDS", 12, minimum=3, maximum=60),
        max_content_chars=_get_int("MAX_CONTENT_CHARS", 12000, minimum=1000, maximum=50000),
        summarizer_mode=os.getenv("SUMMARIZER_MODE", "extractive").strip().lower() or "extractive",
        report_type=os.getenv("REPORT_TYPE", "research_report").strip() or "research_report",
        report_format=os.getenv("REPORT_FORMAT", "APA").strip() or "APA",
        total_words=_get_int("TOTAL_WORDS", 1200, minimum=300, maximum=5000),
        writer_prompt_style=os.getenv("WRITER_PROMPT_STYLE", "gpt_researcher").strip() or "gpt_researcher",
    )


def _get_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(minimum, min(value, maximum))


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return default
