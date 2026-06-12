from __future__ import annotations

from citation_manager import build_citation_labels, citation_label_for, collect_references, format_references


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


def test_format_references_uses_apa_like_markdown_links():
    references = format_references(
        [
            {
                "title": "男士短袖T恤哪种材质好_处理_纤维_文艺",
                "url": "https://www.sohu.com/a/767803565_120913103",
                "summary": "2024年材料指南。",
            }
        ]
    )

    assert "Sohu. (2024)." in references
    assert "[Sohu](https://www.sohu.com/a/767803565_120913103)" in references
    assert "：https://www.sohu.com" not in references


def test_build_citation_labels_uses_domain_and_year():
    labels = build_citation_labels(
        [
            {
                "title": "男士短袖T恤哪种材质好_处理_纤维_文艺",
                "url": "https://www.sohu.com/a/767803565_120913103",
                "summary": "2024年材料指南。",
            },
            {
                "title": "短袖选购指南",
                "url": "https://zhuanlan.zhihu.com/p/1895056434061869294",
                "summary": "2026年夏季男士短袖。",
            },
        ]
    )

    assert labels["https://www.sohu.com/a/767803565_120913103"] == "Sohu, 2024"
    assert labels["https://zhuanlan.zhihu.com/p/1895056434061869294"] == "Zhihu, 2026"


def test_citation_label_for_falls_back_to_domain():
    label = citation_label_for({"title": "无年份来源", "url": "https://example.com/a"})

    assert label == "Example, n.d."
