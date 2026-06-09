from __future__ import annotations

from dataclasses import asdict, dataclass

from config import Settings
from utils import unique_by_url


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str
    query: str


class Searcher:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def search_many(self, queries: list[str]) -> list[SearchResult]:
        results: list[dict] = []
        for query in queries:
            results.extend(asdict(item) for item in self.search(query))
        return [SearchResult(**item) for item in unique_by_url(results)]

    def search(self, query: str) -> list[SearchResult]:
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            print("Warning: 缺少 duckduckgo-search 依赖，跳过搜索。")
            return []

        try:
            with DDGS() as ddgs:
                raw_results = list(ddgs.text(query, max_results=self.settings.max_search_results))
        except Exception as exc:
            print(f"Warning: 搜索失败，query={query}，原因：{exc}")
            return []

        results: list[SearchResult] = []
        for item in raw_results[: self.settings.max_search_results]:
            url = str(item.get("href") or item.get("url") or "").strip()
            if not url:
                continue
            results.append(
                SearchResult(
                    title=str(item.get("title") or "").strip(),
                    url=url,
                    snippet=str(item.get("body") or item.get("snippet") or "").strip(),
                    query=query,
                )
            )
        return results
