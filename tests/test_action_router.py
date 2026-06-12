from __future__ import annotations

from action_router import ActionRouter
from config import Settings


def test_action_router_refines_when_sources_are_enough():
    router = ActionRouter(Settings(zai_api_key="test", min_accepted_sources=2))

    decision = router.route({"label": "correct", "coverage": 1.0, "accepted_urls": ["a", "b"]}, 1)

    assert decision.action == "refine"
    assert decision.should_continue_search is False


def test_action_router_rewrites_incorrect_before_round_limit():
    router = ActionRouter(Settings(zai_api_key="test", max_search_rounds=2))

    decision = router.route({"label": "incorrect", "coverage": 0.0, "accepted_urls": []}, 1)

    assert decision.action == "rewrite_search"
    assert decision.should_continue_search is True


def test_action_router_keeps_and_searches_ambiguous():
    router = ActionRouter(Settings(zai_api_key="test", max_search_rounds=2))

    decision = router.route({"label": "ambiguous", "coverage": 0.4, "accepted_urls": ["a"]}, 1)

    assert decision.action == "keep_and_search"
    assert decision.should_continue_search is True
