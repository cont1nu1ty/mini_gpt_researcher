from __future__ import annotations

from evidence_refiner import EvidenceRefiner


def test_evidence_refiner_keeps_top_passages_and_deduplicates():
    refiner = EvidenceRefiner(max_passages_per_page=2, passage_chars=120)
    pages = [
        {
            "title": "短袖面料",
            "url": "https://example.com/a",
            "query": "男士短袖 面料",
            "purpose": "面料对比",
            "content": "男士短袖夏季适合棉和速干面料。低支棉容易闷热。男士短袖夏季适合棉和速干面料。",
        },
        {
            "title": "无关",
            "url": "https://example.com/b",
            "query": "男士短袖 面料",
            "purpose": "",
            "content": "这是一段无关内容。",
        },
    ]

    refined = refiner.refine(
        pages,
        {"accepted_urls": ["https://example.com/a"], "rejected_urls": ["https://example.com/b"], "relevance": 0.8},
        "男士短袖 面料",
    )

    assert len(refined) == 1
    assert refined[0]["url"] == "https://example.com/a"
    assert refined[0]["evidence_passages"]
    assert refined[0]["evaluation_label"] == "correct"


def test_evidence_refiner_uses_low_confidence_fallback_when_all_rejected():
    refiner = EvidenceRefiner(max_passages_per_page=1, passage_chars=120)
    pages = [
        {
            "title": "短袖面料摘要",
            "url": "https://example.com/snippet",
            "query": "男士短袖 面料",
            "purpose": "面料对比",
            "content": "男士短袖夏季适合选择透气棉和速干面料。",
            "content_source": "search_snippet",
        }
    ]

    refined = refiner.refine(
        pages,
        {
            "accepted_urls": [],
            "rejected_urls": ["https://example.com/snippet"],
            "relevance": 0.2,
            "reason": "模型评估过严。",
        },
        "男士短袖 面料",
    )

    assert len(refined) == 1
    assert refined[0]["evaluation_label"] == "ambiguous"


def test_evidence_refiner_prioritizes_full_pages_before_snippets():
    refiner = EvidenceRefiner(max_passages_per_page=1, passage_chars=120)
    pages = [
        {
            "title": "搜索摘要",
            "url": "https://example.com/snippet",
            "query": "男士短袖 面料",
            "purpose": "面料对比",
            "content": "男士短袖夏季适合棉和速干面料。",
            "content_source": "search_snippet",
        },
        {
            "title": "完整网页",
            "url": "https://example.com/full",
            "query": "男士短袖 面料",
            "purpose": "面料对比",
            "content": "男士短袖夏季选购应比较棉、聚酯纤维、速干面料、克重和缝线做工。" * 5,
            "content_source": "web_page",
        },
    ]

    refined = refiner.refine(
        pages,
        {
            "accepted_urls": ["https://example.com/snippet", "https://example.com/full"],
            "rejected_urls": [],
            "relevance": 0.8,
        },
        "男士短袖 面料",
    )

    assert refined[0]["url"] == "https://example.com/full"
    assert refined[1]["evaluation_label"] == "ambiguous"
