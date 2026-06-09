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


class ConfigError(RuntimeError):
    """Raised when required runtime configuration is missing."""


@dataclass(frozen=True)
class Settings:
    zai_api_key: str
    zai_base_url: str = "https://api.z.ai/api/paas/v4"
    zai_model: str = "glm-5.1"
    max_sub_questions: int = 4
    max_search_results: int = 4
    max_web_pages: int = 8
    output_language: str = "zh-CN"
    request_timeout_seconds: int = 12
    max_content_chars: int = 12000


def load_settings(require_api_key: bool = True) -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.getenv("ZAI_API_KEY", "").strip()
    if require_api_key and not api_key:
        raise ConfigError(
            "缺少 ZAI_API_KEY。请先执行 `cp .env.example .env`，然后在 .env 中填写真实 API Key。"
        )
    return Settings(
        zai_api_key=api_key,
        zai_base_url=os.getenv("ZAI_BASE_URL", "https://api.z.ai/api/paas/v4").strip(),
        zai_model=os.getenv("ZAI_MODEL", "glm-5.1").strip(),
        max_sub_questions=_get_int("MAX_SUB_QUESTIONS", 4, minimum=1, maximum=8),
        max_search_results=_get_int("MAX_SEARCH_RESULTS", 4, minimum=1, maximum=10),
        max_web_pages=_get_int("MAX_WEB_PAGES", 8, minimum=1, maximum=30),
        output_language=os.getenv("OUTPUT_LANGUAGE", "zh-CN").strip() or "zh-CN",
        request_timeout_seconds=_get_int("REQUEST_TIMEOUT_SECONDS", 12, minimum=3, maximum=60),
        max_content_chars=_get_int("MAX_CONTENT_CHARS", 12000, minimum=1000, maximum=50000),
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
