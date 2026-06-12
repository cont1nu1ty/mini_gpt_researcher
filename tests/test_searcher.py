from __future__ import annotations

from config import Settings
from searcher import SearchResult, Searcher


def test_searcher_auto_falls_back_to_next_provider(monkeypatch):
    searcher = Searcher(Settings(zai_api_key="test", max_search_results=3, search_aggregate_providers=False))

    def fake_provider(provider: str, query: str):
        if provider == "ddgs":
            raise RuntimeError("network failed")
        return [SearchResult(title="测试问题 结果", url="https://example.com", snippet="测试问题 摘要", query=query)]

    monkeypatch.setattr(searcher, "_search_with_provider", fake_provider)

    results = searcher.search("测试问题")

    assert results == [
        SearchResult(
            title="测试问题 结果",
            url="https://example.com",
            snippet="测试问题 摘要",
            query="测试问题",
            provider="duckduckgo_html",
        )
    ]


def test_searcher_search_many_deduplicates_urls(monkeypatch):
    searcher = Searcher(Settings(zai_api_key="test", max_search_results=3))

    def fake_search(query: str, *, mode: str = "broad", purpose: str = ""):
        return [
            SearchResult(title="A", url="https://example.com/a", snippet="", query=query, mode=mode, purpose=purpose),
            SearchResult(title="A2", url="https://example.com/a", snippet="", query=query, mode=mode, purpose=purpose),
        ]

    monkeypatch.setattr(searcher, "search", fake_search)

    results = searcher.search_many(["q1", "q2"])

    assert len(results) == 1
    assert results[0].title == "A"


def test_searcher_searxng_json_provider(monkeypatch):
    searcher = Searcher(Settings(zai_api_key="test", search_provider="searxng_json", searxng_base_url="https://searx.test"))

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "results": [
                    {"title": "测试结果", "url": "https://example.com/a", "content": "测试摘要"},
                ]
            }

    def fake_get(url, headers, timeout):
        assert url.startswith("https://searx.test/search?")
        assert "format=json" in url
        return FakeResponse()

    import types
    import sys

    monkeypatch.setitem(sys.modules, "requests", types.SimpleNamespace(get=fake_get))

    results = searcher.search("测试", mode="targeted", purpose="补搜")

    assert results == [
        SearchResult(
            title="测试结果",
            url="https://example.com/a",
            snippet="测试摘要",
            query="测试",
            provider="searxng_json",
            mode="targeted",
            purpose="补搜",
        )
    ]


def test_searcher_skips_unconfigured_searxng_in_auto(monkeypatch):
    searcher = Searcher(Settings(zai_api_key="test", max_search_results=3))
    calls = []

    def fake_provider(provider: str, query: str):
        calls.append(provider)
        if provider in {"ddgs", "searxng_json"}:
            raise RuntimeError("failed")
        return [SearchResult(title="测试问题 结果", url="https://example.com", snippet="测试问题 摘要", query=query)]

    monkeypatch.setattr(searcher, "_search_with_provider", fake_provider)

    results = searcher.search("测试问题")

    assert calls == ["ddgs", "duckduckgo_html", "bing_html", "baidu_html"]
    assert "searxng_json" not in calls
    assert results[0].provider in {"duckduckgo_html", "bing_html", "baidu_html"}


def test_searcher_filters_irrelevant_provider_results(monkeypatch):
    searcher = Searcher(Settings(zai_api_key="test", max_search_results=3))

    def fake_provider(provider: str, query: str):
        if provider == "ddgs":
            return [SearchResult(title="novafms Pro APP Review", url="https://example.com/app", snippet="", query=query)]
        if provider == "searxng_json":
            raise RuntimeError("not configured")
        return [SearchResult(title="北京夏季男士短袖面料", url="https://example.com/shirt", snippet="棉和速干面料", query=query)]

    monkeypatch.setattr(searcher, "_search_with_provider", fake_provider)

    results = searcher.search("北京夏季男士短袖面料")

    assert results[0].url == "https://example.com/shirt"
    assert results[0].provider in {"duckduckgo_html", "bing_html", "baidu_html"}


def test_searcher_auto_aggregates_providers_and_ranks_results(monkeypatch):
    searcher = Searcher(Settings(zai_api_key="test", tavily_api_key="test-tavily-key", max_search_results=2))

    def fake_provider(provider: str, query: str):
        if provider == "tavily":
            return [
                SearchResult(
                    title="北京夏季男士短袖面料工艺",
                    url="https://example.com/tavily?utm_source=x",
                    snippet="北京夏季男士短袖要关注棉、速干、克重和做工。",
                    query=query,
                    raw_content="北京夏季男士短袖选购需要关注透气、排汗、克重、缝线和领口工艺。" * 20,
                )
            ]
        if provider == "ddgs":
            return [
                SearchResult(
                    title="北京夏季男士短袖面料工艺",
                    url="https://example.com/tavily",
                    snippet="重复来源",
                    query=query,
                )
            ]
        return [
            SearchResult(
                title=f"{provider} 男士短袖面料",
                url=f"https://example.com/{provider}",
                snippet="棉和速干面料对比。",
                query=query,
            )
        ]

    monkeypatch.setattr(searcher, "_search_with_provider", fake_provider)

    results = searcher.search("北京夏季男士短袖面料工艺")

    assert len(results) == 2
    assert results[0].provider == "tavily"
    assert results[0].raw_content
    assert len([item for item in results if item.url.startswith("https://example.com/tavily")]) == 1


def test_searcher_auto_prefers_tavily_when_configured():
    searcher = Searcher(Settings(zai_api_key="test", tavily_api_key="test-tavily-key"))

    assert searcher._provider_order()[0] == "tavily"


def test_searcher_tavily_provider_parses_content(monkeypatch):
    searcher = Searcher(
        Settings(
            zai_api_key="test",
            search_provider="tavily",
            tavily_api_key="test-tavily-key",
            max_search_results=2,
        )
    )

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "results": [
                    {
                        "title": "北京夏季男士短袖面料",
                        "url": "https://example.com/tavily",
                        "content": "北京夏季短袖可选棉和速干面料。",
                        "raw_content": "北京夏季男士短袖选购需要关注透气、排汗、克重和做工。" * 5,
                    }
                ]
            }

    def fake_post(url, json, headers, timeout):
        assert url == "https://api.tavily.com/search"
        assert json["api_key"] == "test-tavily-key"
        assert json["include_raw_content"] is True
        return FakeResponse()

    import sys
    import types

    monkeypatch.setitem(sys.modules, "requests", types.SimpleNamespace(post=fake_post))

    results = searcher.search("北京夏季男士短袖面料")

    assert results[0].provider == "tavily"
    assert results[0].raw_content.startswith("北京夏季男士短袖选购")
