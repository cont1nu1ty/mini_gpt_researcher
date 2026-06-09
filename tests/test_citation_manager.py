from __future__ import annotations

from citation_manager import collect_references, format_references


def test_collect_references_deduplicates_urls():
    refs = collect_references(
        [
            {"title": "A", "url": "https://example.com/a"},
            {"title": "A2", "url": "https://example.com/a"},
            {"title": "B", "url": "https://example.com/b"},
        ]
    )

    assert refs == [
        {"title": "A", "url": "https://example.com/a"},
        {"title": "B", "url": "https://example.com/b"},
    ]


def test_format_references_empty():
    assert "没有可列出的参考来源" in format_references([])
