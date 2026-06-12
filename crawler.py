from __future__ import annotations

from config import Settings
from searcher import SearchResult
from utils import clean_text, truncate_text


class Crawler:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.last_crawl_records: list[dict] = []
        self.headers = {
            "User-Agent": "mini-gpt-researcher/0.1 (+https://example.local; educational demo)"
        }

    def crawl_many(self, results: list[SearchResult]) -> list[dict]:
        self.last_crawl_records = []
        pages: list[dict] = []
        for index, result in enumerate(results):
            if index >= self.settings.max_web_pages:
                self.last_crawl_records.append(self._crawl_record(result, "skipped_max_web_pages"))
                continue
            page = self.crawl(result)
            status = "success" if page["content"] else "failed_or_empty"
            self.last_crawl_records.append(self._crawl_record(result, status, page))
            if page["content"]:
                pages.append(page)
        return pages

    def crawl(self, result: SearchResult) -> dict:
        if result.raw_content and len(result.raw_content) >= 100:
            return {
                "title": result.title,
                "url": result.url,
                "content": truncate_text(result.raw_content, self.settings.max_content_chars),
                "query": result.query,
                "snippet": result.snippet,
                "provider": result.provider,
                "mode": result.mode,
                "purpose": result.purpose,
                "content_source": "retriever_raw_content",
            }

        try:
            import requests
            from bs4 import BeautifulSoup
        except ImportError as exc:
            print(f"Warning: 缺少网页抓取依赖，请先运行 `pip install -r requirements.txt`。原因：{exc}")
            return self._empty_page(result)

        try:
            response = requests.get(
                result.url,
                headers=self.headers,
                timeout=self.settings.request_timeout_seconds,
            )
            response.raise_for_status()
        except Exception as exc:
            print(f"Warning: 网页抓取失败，url={result.url}，原因：{exc}")
            return self._empty_page(result)

        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
            tag.decompose()

        title = clean_text(soup.title.get_text(" ")) if soup.title else result.title
        text = clean_text(soup.get_text(" "))
        return {
            "title": title or result.title,
            "url": result.url,
            "content": truncate_text(text, self.settings.max_content_chars),
            "query": result.query,
            "snippet": result.snippet,
            "provider": result.provider,
            "mode": result.mode,
            "purpose": result.purpose,
            "content_source": "web_page",
        }

    def _empty_page(self, result: SearchResult) -> dict:
        return {
            "title": result.title,
            "url": result.url,
            "content": "",
            "query": result.query,
            "snippet": result.snippet,
            "provider": result.provider,
            "mode": result.mode,
            "purpose": result.purpose,
        }

    def _crawl_record(self, result: SearchResult, status: str, page: dict | None = None) -> dict:
        return {
            "status": status,
            "title": result.title,
            "url": result.url,
            "query": result.query,
            "provider": result.provider,
            "mode": result.mode,
            "purpose": result.purpose,
            "snippet_length": len(result.snippet),
            "raw_content_length": len(result.raw_content),
            "content_length": len((page or {}).get("content", "")),
            "content_source": (page or {}).get("content_source", ""),
        }
