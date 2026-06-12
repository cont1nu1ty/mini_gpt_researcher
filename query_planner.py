from __future__ import annotations

import json
from dataclasses import dataclass, field

from config import Settings
from llm_client import LLMClient
from prompts import QUERY_REWRITE_PROMPT, QUERY_REWRITE_SYSTEM_PROMPT, RESEARCH_PLAN_PROMPT, RESEARCH_PLAN_SYSTEM_PROMPT
from utils import clean_text, relevance_overlap, truncate_text


QUESTION_TYPES = {"fact", "literature_review", "comparison", "latest", "multi_hop", "buying_advice"}
QUERY_MODES = {"broad", "targeted", "source_specific"}


@dataclass(frozen=True)
class PlannedQuery:
    query: str
    mode: str = "broad"
    purpose: str = "初始搜索"


@dataclass(frozen=True)
class ResearchPlan:
    question_type: str
    needs_freshness: bool
    research_intent: str
    sub_questions: list[str] = field(default_factory=list)
    search_queries: list[PlannedQuery] = field(default_factory=list)


class QueryPlanner:
    def __init__(self, llm: LLMClient, settings: Settings) -> None:
        self.llm = llm
        self.settings = settings

    def plan(self, query: str, initial_results: list | None = None) -> ResearchPlan:
        prompt = RESEARCH_PLAN_PROMPT.format(
            query=query,
            max_sub_questions=self.settings.max_sub_questions,
            max_planned_queries=self.settings.max_planned_queries,
            initial_context=self._format_initial_context(initial_results or []),
        )
        try:
            response = self.llm.chat(prompt, system_prompt=RESEARCH_PLAN_SYSTEM_PROMPT, temperature=0.2)
            return self._parse_plan(response, query)
        except Exception as exc:
            print(f"Warning: 研究计划生成失败，使用原问题作为 fallback。原因：{exc}")
            return self._fallback_plan(query)

    def rewrite_queries(self, query: str, plan: ResearchPlan, evaluation: dict, round_index: int) -> list[PlannedQuery]:
        grounding_text = " ".join([query, plan.research_intent, *plan.sub_questions])
        suggested = [
            PlannedQuery(clean_text(item), "targeted", "检索评估建议的补充搜索")
            for item in evaluation.get("suggested_rewrite_queries", [])
            if clean_text(str(item)) and self._is_grounded_query(str(item), grounding_text)
        ]
        if suggested:
            return suggested[: self.settings.max_rewrite_queries]

        prompt = QUERY_REWRITE_PROMPT.format(
            query=query,
            research_intent=plan.research_intent,
            question_type=plan.question_type,
            evaluation=json.dumps(evaluation, ensure_ascii=False, indent=2),
            max_rewrite_queries=self.settings.max_rewrite_queries,
            round_index=round_index,
        )
        try:
            response = self.llm.chat(prompt, system_prompt=QUERY_REWRITE_SYSTEM_PROMPT, temperature=0.2)
            parsed = json.loads(response)
            queries = self._parse_queries(parsed)
        except Exception as exc:
            print(f"Warning: query 改写失败，使用本地补搜 query fallback。原因：{exc}")
            queries = []
        queries = [item for item in queries if self._is_grounded_query(item.query, grounding_text)]
        return (queries or self._fallback_rewrite_queries(query, plan))[: self.settings.max_rewrite_queries]

    def _parse_plan(self, response: str, original_query: str) -> ResearchPlan:
        parsed = json.loads(response)
        question_type = str(parsed.get("question_type", "multi_hop")).strip()
        if question_type not in QUESTION_TYPES:
            question_type = "multi_hop"
        sub_questions = [
            clean_text(str(item))
            for item in parsed.get("sub_questions", [])
            if clean_text(str(item))
        ][: self.settings.max_sub_questions]
        grounding_text = " ".join([original_query, str(parsed.get("research_intent", "")), *sub_questions])
        queries = [
            item
            for item in self._parse_queries(parsed.get("search_queries", []))
            if self._is_grounded_query(item.query, grounding_text)
        ][: self.settings.max_planned_queries]
        if not sub_questions:
            sub_questions = [original_query]
        if not queries:
            queries = [PlannedQuery(original_query, "broad", "原问题 fallback 搜索")]
        return ResearchPlan(
            question_type=question_type,
            needs_freshness=bool(parsed.get("needs_freshness", False)),
            research_intent=clean_text(str(parsed.get("research_intent", ""))) or original_query,
            sub_questions=sub_questions,
            search_queries=queries,
        )

    def _parse_queries(self, raw_queries) -> list[PlannedQuery]:
        queries: list[PlannedQuery] = []
        if not isinstance(raw_queries, list):
            return queries
        for item in raw_queries:
            if isinstance(item, str):
                text = clean_text(item)
                if text:
                    queries.append(PlannedQuery(text))
                continue
            if not isinstance(item, dict):
                continue
            text = clean_text(str(item.get("query", "")))
            if not text:
                continue
            mode = str(item.get("mode", "broad")).strip()
            if mode not in QUERY_MODES:
                mode = "broad"
            purpose = clean_text(str(item.get("purpose", ""))) or "搜索资料"
            queries.append(PlannedQuery(text, mode, purpose))
        return queries

    def _fallback_plan(self, query: str) -> ResearchPlan:
        return ResearchPlan(
            question_type="multi_hop",
            needs_freshness=False,
            research_intent=query,
            sub_questions=[query],
            search_queries=[PlannedQuery(query, "broad", "原问题 fallback 搜索")],
        )

    def _fallback_rewrite_queries(self, query: str, plan: ResearchPlan) -> list[PlannedQuery]:
        suffixes = ["权威 来源", "最新 信息", "案例 分析"]
        if plan.question_type == "buying_advice":
            suffixes = ["选购 指南", "材质 对比", "避坑 经验"]
        return [PlannedQuery(f"{query} {suffix}", "targeted", "本地规则补搜") for suffix in suffixes]

    def _is_grounded_query(self, query: str, grounding_text: str) -> bool:
        return relevance_overlap(query, grounding_text) > 0

    def _format_initial_context(self, initial_results: list) -> str:
        if not initial_results:
            return "无"
        lines = []
        for index, item in enumerate(initial_results[: self.settings.max_search_results], start=1):
            title = clean_text(str(self._field(item, "title")))
            url = clean_text(str(self._field(item, "url")))
            snippet = clean_text(str(self._field(item, "snippet")))
            lines.append(
                f"{index}. 标题：{title}\n"
                f"   URL：{url}\n"
                f"   摘要：{truncate_text(snippet, 240)}"
            )
        return "\n".join(lines)

    def _field(self, item, name: str) -> str:
        if isinstance(item, dict):
            return item.get(name, "")
        return getattr(item, name, "")
