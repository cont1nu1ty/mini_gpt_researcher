from __future__ import annotations

from config import Settings
from crawler import Crawler
from searcher import SearchResult


def test_crawler_uses_retriever_raw_content_without_http():
    crawler = Crawler(Settings(zai_api_key="test"))
    result = SearchResult(
        title="Tavily 来源",
        url="https://example.com/raw",
        snippet="摘要",
        query="测试问题",
        provider="tavily",
        raw_content="这是检索器直接返回的完整正文，包含可用于报告的具体信息。" * 10,
    )

    page = crawler.crawl(result)

    assert page["content_source"] == "retriever_raw_content"
    assert "完整正文" in page["content"]
    assert page["provider"] == "tavily"
