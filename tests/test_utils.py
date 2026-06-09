from __future__ import annotations

from utils import clean_text, truncate_text, unique_by_url


def test_clean_text_collapses_whitespace():
    assert clean_text("  a\n\n b\tc  ") == "a b c"


def test_truncate_text_adds_marker():
    assert truncate_text("a " * 100, 20).endswith("[内容已截断]")


def test_unique_by_url_keeps_first_seen():
    items = [
        {"url": "https://example.com/a", "title": "A1"},
        {"url": "https://example.com/a", "title": "A2"},
        {"url": "https://example.com/b", "title": "B"},
    ]
    assert [item["title"] for item in unique_by_url(items)] == ["A1", "B"]
