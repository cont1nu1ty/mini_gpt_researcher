from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from urllib.parse import parse_qsl, parse_qs, quote_plus, urlencode, urlparse, urlunparse, unquote

from config import Settings
from utils import clean_text, relevance_overlap


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str
    query: str
    provider: str = ""
    mode: str = "broad"
    purpose: str = ""
    raw_content: str = ""


class Searcher:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def search_many(self, queries: list) -> list[SearchResult]:
        coerced_queries = []
        for item in queries:
            coerced = self._coerce_query(item)
            if coerced[0]:
                coerced_queries.append(coerced)
        if not coerced_queries:
            return []
        results: list[dict] = []
        with ThreadPoolExecutor(max_workers=min(len(coerced_queries), self.settings.max_search_workers)) as executor:
            futures = [
                executor.submit(self.search, query, mode=mode, purpose=purpose)
                for query, mode, purpose in coerced_queries
            ]
            for future in futures:
                results.extend(asdict(result) for result in future.result())
        deduped = self._dedupe_results([SearchResult(**item) for item in results])
        return self._rank_results(deduped, " ".join(query for query, _, _ in coerced_queries))

    def search(self, query: str, *, mode: str = "broad", purpose: str = "") -> list[SearchResult]:
        providers = self._provider_order()
        errors: list[str] = []
        aggregated: list[SearchResult] = []
        for provider in providers:
            try:
                results = self._search_with_provider(provider, query)
            except Exception as exc:
                errors.append(f"{provider}: {exc}")
                continue
            results = self._filter_relevant_results(results, query)
            if results:
                aggregated.extend(self._attach_metadata(results, provider, mode, purpose))
                if not self._should_aggregate_providers():
                    break
                continue
            errors.append(f"{provider}: no results")
        if aggregated:
            deduped = self._dedupe_results(aggregated)
            ranked = self._rank_results(deduped, query)
            return ranked[: self.settings.max_search_results]
        print(f"Warning: 搜索失败，query={query}，原因：{' | '.join(errors)}")
        return []

    def _provider_order(self) -> list[str]:
        configured = self.settings.search_provider
        if configured and configured != "auto":
            return [provider.strip() for provider in configured.split(",") if provider.strip()]
        providers = []
        if self.settings.tavily_api_key:
            providers.append("tavily")
        providers.append("ddgs")
        if self.settings.searxng_base_url:
            providers.append("searxng_json")
        providers.extend(["duckduckgo_html", "bing_html", "baidu_html"])
        return providers

    def _should_aggregate_providers(self) -> bool:
        configured = self.settings.search_provider
        if configured and configured != "auto" and "," not in configured:
            return False
        return self.settings.search_aggregate_providers

    def _search_with_provider(self, provider: str, query: str) -> list[SearchResult]:
        if provider == "tavily":
            return self._search_tavily(query)
        if provider == "ddgs":
            return self._search_ddgs(query)
        if provider == "duckduckgo_search":
            return self._search_duckduckgo_search(query)
        if provider == "searxng_json":
            return self._search_searxng_json(query)
        if provider == "duckduckgo_html":
            return self._search_duckduckgo_html(query)
        if provider == "bing_html":
            return self._search_bing_html(query)
        if provider == "baidu_html":
            return self._search_baidu_html(query)
        raise ValueError(f"不支持的 SEARCH_PROVIDER：{provider}")

    def _search_tavily(self, query: str) -> list[SearchResult]:
        if not self.settings.tavily_api_key:
            raise RuntimeError("未配置 TAVILY_API_KEY。")
        try:
            import requests
        except ImportError as exc:
            raise RuntimeError("缺少 requests 依赖。") from exc
        response = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": self.settings.tavily_api_key,
                "query": query,
                "search_depth": "basic",
                "max_results": self.settings.max_search_results,
                "include_answer": False,
                "include_raw_content": self.settings.tavily_include_raw_content,
                "include_images": False,
            },
            headers={
                "Content-Type": "application/json",
                "User-Agent": "mini-gpt-researcher/0.1 (+https://example.local; educational demo)",
            },
            timeout=max(self.settings.request_timeout_seconds, 20),
        )
        response.raise_for_status()
        payload = response.json()
        raw_results = []
        for item in payload.get("results", [])[: self.settings.max_search_results]:
            raw_results.append(
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("content", ""),
                    "raw_content": item.get("raw_content") or "",
                }
            )
        return self._normalize_results(raw_results, query)

    def _search_ddgs(self, query: str) -> list[SearchResult]:
        try:
            from ddgs import DDGS
        except ImportError as exc:
            raise RuntimeError("缺少 ddgs 依赖，请先运行 `pip install -r requirements.txt`。") from exc

        with DDGS() as ddgs:
            raw_results = list(ddgs.text(query, max_results=self.settings.max_search_results))
        return self._normalize_results(raw_results, query)

    def _search_searxng_json(self, query: str) -> list[SearchResult]:
        if not self.settings.searxng_base_url:
            raise RuntimeError("未配置 SEARXNG_BASE_URL。")
        url = f"{self.settings.searxng_base_url}/search?q={quote_plus(query)}&format=json"
        try:
            import requests
        except ImportError as exc:
            raise RuntimeError("缺少 requests 依赖。") from exc
        response = requests.get(
            url,
            headers={
                "User-Agent": "mini-gpt-researcher/0.1 (+https://example.local; educational demo)",
                "Accept": "application/json",
            },
            timeout=self.settings.request_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        raw_results = []
        for item in payload.get("results", [])[: self.settings.max_search_results]:
            raw_results.append(
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("content", ""),
                }
            )
        return self._normalize_results(raw_results, query)

    def _search_duckduckgo_search(self, query: str) -> list[SearchResult]:
        try:
            from duckduckgo_search import DDGS
        except ImportError as exc:
            raise RuntimeError("缺少 duckduckgo-search 依赖。") from exc

        with DDGS() as ddgs:
            raw_results = list(ddgs.text(query, max_results=self.settings.max_search_results))
        return self._normalize_results(raw_results, query)

    def _search_duckduckgo_html(self, query: str) -> list[SearchResult]:
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        html = self._fetch_search_html(url)
        try:
            from bs4 import BeautifulSoup
        except ImportError as exc:
            raise RuntimeError("缺少 beautifulsoup4 依赖。") from exc

        soup = BeautifulSoup(html, "html.parser")
        results: list[SearchResult] = []
        for item in soup.select(".result"):
            link = item.select_one(".result__a")
            if not link:
                continue
            href = self._unwrap_duckduckgo_url(link.get("href", ""))
            if not href:
                continue
            snippet = item.select_one(".result__snippet")
            results.append(
                SearchResult(
                    title=clean_text(link.get_text(" ")),
                    url=href,
                    snippet=clean_text(snippet.get_text(" ")) if snippet else "",
                    query=query,
                )
            )
        return results

    def _search_bing_html(self, query: str) -> list[SearchResult]:
        url = f"https://www.bing.com/search?q={quote_plus(query)}"
        html = self._fetch_search_html(url)
        try:
            from bs4 import BeautifulSoup
        except ImportError as exc:
            raise RuntimeError("缺少 beautifulsoup4 依赖。") from exc

        soup = BeautifulSoup(html, "html.parser")
        results: list[SearchResult] = []
        for item in soup.select("li.b_algo"):
            link = item.select_one("h2 a")
            if not link:
                continue
            snippet = item.select_one(".b_caption p")
            results.append(
                SearchResult(
                    title=clean_text(link.get_text(" ")),
                    url=link.get("href", "").strip(),
                    snippet=clean_text(snippet.get_text(" ")) if snippet else "",
                    query=query,
                )
            )
        return [item for item in results if item.url]

    def _search_baidu_html(self, query: str) -> list[SearchResult]:
        url = f"https://www.baidu.com/s?wd={quote_plus(query)}"
        html = self._fetch_search_html(url)
        try:
            from bs4 import BeautifulSoup
        except ImportError as exc:
            raise RuntimeError("缺少 beautifulsoup4 依赖。") from exc

        soup = BeautifulSoup(html, "html.parser")
        results: list[SearchResult] = []
        for item in soup.select("div.result, div.c-container"):
            link = item.select_one("h3 a")
            if not link:
                continue
            abstract = item.select_one(".c-abstract")
            results.append(
                SearchResult(
                    title=clean_text(link.get_text(" ")),
                    url=link.get("href", "").strip(),
                    snippet=clean_text(abstract.get_text(" ")) if abstract else "",
                    query=query,
                )
            )
        return [item for item in results if item.url]

    def _fetch_search_html(self, url: str) -> str:
        try:
            import requests
        except ImportError as exc:
            raise RuntimeError("缺少 requests 依赖。") from exc
        response = requests.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
            },
            timeout=self.settings.request_timeout_seconds,
        )
        response.raise_for_status()
        return response.text

    def _normalize_results(self, raw_results: list[dict], query: str) -> list[SearchResult]:
        results: list[SearchResult] = []
        for item in raw_results:
            url = str(item.get("href") or item.get("url") or "").strip()
            if not url:
                continue
            results.append(
                SearchResult(
                    title=str(item.get("title") or "").strip(),
                    url=url,
                    snippet=str(item.get("body") or item.get("snippet") or "").strip(),
                    query=query,
                    raw_content=str(item.get("raw_content") or "").strip(),
                )
            )
        return results

    def _attach_metadata(
        self,
        results: list[SearchResult],
        provider: str,
        mode: str,
        purpose: str,
    ) -> list[SearchResult]:
        return [
            SearchResult(
                title=item.title,
                url=item.url,
                snippet=item.snippet,
                query=item.query,
                provider=provider,
                mode=mode,
                purpose=purpose,
                raw_content=item.raw_content,
            )
            for item in results
        ]

    def _filter_relevant_results(self, results: list[SearchResult], query: str) -> list[SearchResult]:
        filtered = []
        for item in results:
            haystack = " ".join([item.title, item.snippet, item.raw_content, item.url])
            if relevance_overlap(query, haystack) > 0:
                filtered.append(item)
        return filtered

    def _rank_results(self, results: list[SearchResult], query: str) -> list[SearchResult]:
        return sorted(results, key=lambda item: self._result_score(item, query), reverse=True)

    def _dedupe_results(self, results: list[SearchResult]) -> list[SearchResult]:
        best_by_url: dict[str, SearchResult] = {}
        for result in results:
            key = self._canonical_url(result.url)
            current = best_by_url.get(key)
            if current is None or self._result_score(result, result.query) > self._result_score(current, current.query):
                best_by_url[key] = result
        return list(best_by_url.values())

    def _result_score(self, result: SearchResult, query: str) -> float:
        title_overlap = relevance_overlap(query, result.title)
        body_overlap = relevance_overlap(query, " ".join([result.snippet, result.raw_content]))
        raw_bonus = 4.0 if len(result.raw_content) >= 500 else 0.0
        snippet_bonus = min(2.0, len(result.snippet) / 160)
        provider_bonus = {
            "tavily": 3.0,
            "searxng_json": 1.6,
            "ddgs": 1.4,
            "bing_html": 1.0,
            "duckduckgo_html": 0.9,
            "baidu_html": 0.8,
        }.get(result.provider, 0.5)
        return title_overlap * 3 + body_overlap + raw_bonus + snippet_bonus + provider_bonus

    def _canonical_url(self, url: str) -> str:
        parsed = urlparse(url.strip())
        query_items = [
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if not key.lower().startswith("utm_")
            and key.lower() not in {"spm", "from", "source", "ref", "track", "utm"}
        ]
        normalized_path = parsed.path.rstrip("/") or "/"
        return urlunparse(
            (
                parsed.scheme.lower(),
                parsed.netloc.lower(),
                normalized_path,
                "",
                urlencode(query_items),
                "",
            )
        )

    def _coerce_query(self, item) -> tuple[str, str, str]:
        if isinstance(item, str):
            return item, "broad", ""
        if isinstance(item, dict):
            return str(item.get("query", "")).strip(), str(item.get("mode", "broad")), str(item.get("purpose", ""))
        return (
            str(getattr(item, "query", "")).strip(),
            str(getattr(item, "mode", "broad")),
            str(getattr(item, "purpose", "")),
        )

    def _unwrap_duckduckgo_url(self, href: str) -> str:
        if not href:
            return ""
        parsed = urlparse(href)
        if parsed.netloc.endswith("duckduckgo.com") and parsed.path == "/l/":
            target = parse_qs(parsed.query).get("uddg", [""])[0]
            return unquote(target)
        return href
