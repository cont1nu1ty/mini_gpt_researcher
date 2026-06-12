from __future__ import annotations

from agent import ResearchAgent
from query_planner import PlannedQuery
from searcher import SearchResult


def test_agent_builds_snippet_fallback_pages_without_initializing():
    agent = object.__new__(ResearchAgent)
    results = [
        SearchResult(
            title="北京夏季男士短袖面料",
            url="https://example.com/shirt",
            snippet="北京夏季适合选择透气棉、速干和凉感面料。",
            query="北京夏季男士短袖面料",
            provider="ddgs",
            mode="targeted",
            purpose="面料对比",
        )
    ]

    pages = agent._snippet_fallback_pages(results, set())

    assert pages[0]["content_source"] == "search_snippet"
    assert "透气棉" in pages[0]["content"]
    assert pages[0]["provider"] == "ddgs"


def test_agent_uses_snippet_fallback_only_when_evidence_is_insufficient():
    agent = object.__new__(ResearchAgent)

    class Settings:
        min_accepted_sources = 2

    agent.settings = Settings()

    assert agent._should_use_snippet_fallback({"label": "ambiguous", "accepted_urls": ["https://example.com/a"]})
    assert not agent._should_use_snippet_fallback(
        {"label": "correct", "accepted_urls": ["https://example.com/a", "https://example.com/b"]}
    )


def test_agent_ensures_original_query_is_part_of_formal_search_queries():
    agent = object.__new__(ResearchAgent)

    queries = agent._ensure_original_query(
        "北京夏季男性短袖购买，材质工艺挑选",
        [PlannedQuery(query="男士短袖 面料 对比", mode="targeted", purpose="比较面料")],
    )

    assert [item.query for item in queries] == [
        "男士短袖 面料 对比",
        "北京夏季男性短袖购买，材质工艺挑选",
    ]
    assert queries[-1].mode == "broad"
