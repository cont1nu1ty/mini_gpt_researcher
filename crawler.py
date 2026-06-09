from __future__ import annotations

from config import Settings
from searcher import SearchResult
from utils import clean_text, truncate_text


class Crawler:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.headers = {
            "User-Agent": "mini-gpt-researcher/0.1 (+https://example.local; educational demo)"
        }

    def crawl_many(self, results: list[SearchResult]) -> list[dict]:
        pages: list[dict] = []
        for result in results[: self.settings.max_web_pages]:
            page = self.crawl(result)
            if page["content"]:
                pages.append(page)
        return pages

    def crawl(self, result: SearchResult) -> dict:
        try:
            import requests
            from bs4 import BeautifulSoup
        except ImportError as exc:
            print(f"Warning: 缺少网页抓取依赖，请先运行 `pip install -r requirements.txt`。原因：{exc}")
            return {"title": result.title, "url": result.url, "content": "", "query": result.query}

        try:
            response = requests.get(
                result.url,
                headers=self.headers,
                timeout=self.settings.request_timeout_seconds,
            )
            response.raise_for_status()
        except Exception as exc:
            print(f"Warning: 网页抓取失败，url={result.url}，原因：{exc}")
            return {"title": result.title, "url": result.url, "content": "", "query": result.query}

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
        }
