from __future__ import annotations

from dataclasses import dataclass

from config import Settings


@dataclass(frozen=True)
class RouteDecision:
    action: str
    should_continue_search: bool
    reason: str


class ActionRouter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def route(self, evaluation: dict, round_index: int) -> RouteDecision:
        accepted_count = len(evaluation.get("accepted_urls", []))
        label = str(evaluation.get("label", "ambiguous"))
        coverage = float(evaluation.get("coverage", 0.0) or 0.0)
        can_search_more = round_index < self.settings.max_search_rounds

        if accepted_count >= self.settings.min_accepted_sources and coverage >= 0.7:
            return RouteDecision("refine", False, "accepted sources and coverage reached threshold.")
        if label == "incorrect" and can_search_more:
            return RouteDecision("rewrite_search", True, "retrieval judged incorrect; rewrite query and search again.")
        if label == "ambiguous" and can_search_more:
            return RouteDecision("keep_and_search", True, "retrieval judged ambiguous; keep partial evidence and search again.")
        return RouteDecision("refine", False, "search round limit reached or enough partial evidence exists.")
