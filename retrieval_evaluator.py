from __future__ import annotations

import json
import re
from dataclasses import dataclass
from urllib.parse import urlparse

from config import Settings
from llm_client import LLMClient
from prompts import RETRIEVAL_EVALUATOR_PROMPT, RETRIEVAL_EVALUATOR_SYSTEM_PROMPT
from query_planner import ResearchPlan
from utils import clean_text, parse_json_object, truncate_text


VALID_LABELS = {"correct", "incorrect", "ambiguous"}


@dataclass(frozen=True)
class RetrievalEvaluation:
    label: str
    relevance: float
    authority: float
    freshness: float
    coverage: float
    contradiction: bool
    reason: str
    suggested_rewrite_queries: list[str]
    accepted_urls: list[str]
    rejected_urls: list[str]

    def as_dict(self) -> dict:
        return {
            "label": self.label,
            "relevance": self.relevance,
            "authority": self.authority,
            "freshness": self.freshness,
            "coverage": self.coverage,
            "contradiction": self.contradiction,
            "reason": self.reason,
            "suggested_rewrite_queries": self.suggested_rewrite_queries,
            "accepted_urls": self.accepted_urls,
            "rejected_urls": self.rejected_urls,
        }


class RetrievalEvaluator:
    def __init__(self, llm: LLMClient, settings: Settings, *, batch_size: int = 8) -> None:
        self.llm = llm
        self.settings = settings
        self.batch_size = batch_size

    def evaluate(self, original_query: str, plan: ResearchPlan, pages: list[dict], round_index: int) -> dict:
        if not pages:
            return self._empty_evaluation(original_query, "没有抓取到可评估网页。").as_dict()

        evaluations = []
        for batch in self._batches(pages):
            try:
                model_evaluation = self._evaluate_batch(original_query, plan, batch, round_index)
                heuristic_evaluation = self._heuristic_evaluation(original_query, plan, batch)
                evaluations.append(self._reconcile_evaluation(model_evaluation, heuristic_evaluation))
            except Exception as exc:
                print(f"Warning: 批量检索评估失败，使用本地规则 fallback。原因：{exc}")
                evaluations.append(self._heuristic_evaluation(original_query, plan, batch))
        return self._merge_evaluations(evaluations).as_dict()

    def _evaluate_batch(
        self,
        original_query: str,
        plan: ResearchPlan,
        pages: list[dict],
        round_index: int,
    ) -> RetrievalEvaluation:
        evidence = [
            {
                "title": page.get("title", ""),
                "url": page.get("url", ""),
                "query": page.get("query", ""),
                "provider": page.get("provider", ""),
                "mode": page.get("mode", ""),
                "purpose": page.get("purpose", ""),
                "snippet": page.get("snippet", ""),
                "content_excerpt": truncate_text(page.get("content", ""), 1200),
            }
            for page in pages
        ]
        prompt = RETRIEVAL_EVALUATOR_PROMPT.format(
            original_query=original_query,
            research_intent=plan.research_intent,
            question_type=plan.question_type,
            needs_freshness=plan.needs_freshness,
            round_index=round_index,
            min_accepted_sources=self.settings.min_accepted_sources,
            evidence=json.dumps(evidence, ensure_ascii=False, indent=2),
        )
        response = self.llm.chat(prompt, system_prompt=RETRIEVAL_EVALUATOR_SYSTEM_PROMPT, temperature=0.0)
        return self._parse_response(response, pages)

    def _parse_response(self, response: str, pages: list[dict]) -> RetrievalEvaluation:
        parsed = parse_json_object(response)
        label = str(parsed.get("label", "ambiguous")).strip().lower()
        if label not in VALID_LABELS:
            label = "ambiguous"
        page_urls = {str(page.get("url", "")).strip() for page in pages if page.get("url")}
        accepted = [url for url in self._string_list(parsed.get("accepted_urls", [])) if url in page_urls]
        rejected = [url for url in self._string_list(parsed.get("rejected_urls", [])) if url in page_urls]
        if not accepted and label != "incorrect":
            accepted = [url for url in page_urls if url not in rejected]
        return RetrievalEvaluation(
            label=label,
            relevance=self._score(parsed.get("relevance", 0.5)),
            authority=self._score(parsed.get("authority", 0.5)),
            freshness=self._score(parsed.get("freshness", 0.5)),
            coverage=self._score(parsed.get("coverage", 0.5)),
            contradiction=bool(parsed.get("contradiction", False)),
            reason=clean_text(str(parsed.get("reason", ""))) or "模型未给出评估原因。",
            suggested_rewrite_queries=self._string_list(parsed.get("suggested_rewrite_queries", [])),
            accepted_urls=accepted,
            rejected_urls=rejected,
        )

    def _heuristic_evaluation(self, original_query: str, plan: ResearchPlan, pages: list[dict]) -> RetrievalEvaluation:
        query_terms = self._tokenize(" ".join([original_query, plan.research_intent, *plan.sub_questions]))
        accepted = []
        rejected = []
        authority_scores = []
        for page in pages:
            content = " ".join([page.get("title", ""), page.get("snippet", ""), page.get("content", "")])
            overlap = len(query_terms & self._tokenize(content))
            url = str(page.get("url", "")).strip()
            authority_scores.append(self._authority_score(url))
            min_content_len = 10 if page.get("content_source") == "search_snippet" else 200
            if len(page.get("content", "")) >= min_content_len and overlap >= 2:
                accepted.append(url)
            else:
                rejected.append(url)
        accepted = [url for url in accepted if url]
        rejected = [url for url in rejected if url]
        coverage = min(1.0, len(accepted) / max(1, self.settings.min_accepted_sources))
        if len(accepted) >= self.settings.min_accepted_sources and coverage >= 0.7:
            label = "correct"
        elif accepted:
            label = "ambiguous"
        else:
            label = "incorrect"
        return RetrievalEvaluation(
            label=label,
            relevance=coverage,
            authority=sum(authority_scores) / max(1, len(authority_scores)),
            freshness=0.5,
            coverage=coverage,
            contradiction=self._has_conflict_markers(pages),
            reason="本地规则基于关键词重合、正文长度和域名粗略评估。",
            suggested_rewrite_queries=self._fallback_rewrites(original_query, plan),
            accepted_urls=accepted,
            rejected_urls=rejected,
        )

    def _reconcile_evaluation(
        self,
        model_evaluation: RetrievalEvaluation,
        heuristic_evaluation: RetrievalEvaluation,
    ) -> RetrievalEvaluation:
        if model_evaluation.accepted_urls:
            return model_evaluation
        if not heuristic_evaluation.accepted_urls:
            return model_evaluation
        accepted = self._dedupe(model_evaluation.accepted_urls + heuristic_evaluation.accepted_urls)
        rejected = [url for url in model_evaluation.rejected_urls if url not in accepted]
        return RetrievalEvaluation(
            label="ambiguous",
            relevance=max(model_evaluation.relevance, heuristic_evaluation.relevance),
            authority=max(model_evaluation.authority, heuristic_evaluation.authority),
            freshness=max(model_evaluation.freshness, heuristic_evaluation.freshness),
            coverage=max(model_evaluation.coverage, heuristic_evaluation.coverage),
            contradiction=model_evaluation.contradiction or heuristic_evaluation.contradiction,
            reason=f"{model_evaluation.reason} | 本地规则保留部分候选证据，降级为 ambiguous。",
            suggested_rewrite_queries=self._dedupe(
                model_evaluation.suggested_rewrite_queries + heuristic_evaluation.suggested_rewrite_queries
            ),
            accepted_urls=accepted,
            rejected_urls=rejected,
        )

    def _merge_evaluations(self, evaluations: list[RetrievalEvaluation]) -> RetrievalEvaluation:
        accepted = self._dedupe([url for item in evaluations for url in item.accepted_urls])
        rejected = self._dedupe([url for item in evaluations for url in item.rejected_urls if url not in accepted])
        coverage = min(1.0, len(accepted) / max(1, self.settings.min_accepted_sources))
        if len(accepted) >= self.settings.min_accepted_sources and coverage >= 0.7:
            label = "correct"
        elif accepted:
            label = "ambiguous"
        else:
            label = "incorrect"
        return RetrievalEvaluation(
            label=label,
            relevance=self._avg([item.relevance for item in evaluations], coverage),
            authority=self._avg([item.authority for item in evaluations], 0.5),
            freshness=self._avg([item.freshness for item in evaluations], 0.5),
            coverage=max(coverage, self._avg([item.coverage for item in evaluations], 0.0)),
            contradiction=any(item.contradiction for item in evaluations),
            reason=" | ".join(item.reason for item in evaluations if item.reason)[:500],
            suggested_rewrite_queries=self._dedupe([q for item in evaluations for q in item.suggested_rewrite_queries]),
            accepted_urls=accepted,
            rejected_urls=rejected,
        )

    def _empty_evaluation(self, original_query: str, reason: str) -> RetrievalEvaluation:
        return RetrievalEvaluation(
            label="incorrect",
            relevance=0.0,
            authority=0.0,
            freshness=0.0,
            coverage=0.0,
            contradiction=False,
            reason=reason,
            suggested_rewrite_queries=[original_query],
            accepted_urls=[],
            rejected_urls=[],
        )

    def _batches(self, pages: list[dict]) -> list[list[dict]]:
        return [pages[index : index + self.batch_size] for index in range(0, len(pages), self.batch_size)]

    def _score(self, raw) -> float:
        try:
            value = float(raw)
        except (TypeError, ValueError):
            value = 0.5
        return max(0.0, min(1.0, value))

    def _avg(self, values: list[float], default: float) -> float:
        return sum(values) / len(values) if values else default

    def _string_list(self, raw) -> list[str]:
        if not isinstance(raw, list):
            return []
        return [clean_text(str(item)) for item in raw if clean_text(str(item))]

    def _dedupe(self, items: list[str]) -> list[str]:
        seen = set()
        deduped = []
        for item in items:
            if item and item not in seen:
                seen.add(item)
                deduped.append(item)
        return deduped

    def _tokenize(self, text: str) -> set[str]:
        text = clean_text(text).lower()
        tokens = {item for item in re.findall(r"[a-z0-9][a-z0-9_\-]{1,}", text)}
        for chunk in re.findall(r"[\u4e00-\u9fff]{2,}", text):
            tokens.add(chunk)
            tokens.update(chunk[index : index + 2] for index in range(max(0, len(chunk) - 1)))
        return tokens

    def _authority_score(self, url: str) -> float:
        netloc = urlparse(url).netloc.lower()
        if any(token in netloc for token in [".edu", ".gov", "edu.cn", "gov.cn", "arxiv.org", "who.int"]):
            return 0.9
        if any(token in netloc for token in ["wikipedia.org", "baike.baidu.com", "zhihu.com"]):
            return 0.6
        return 0.45

    def _has_conflict_markers(self, pages: list[dict]) -> bool:
        text = " ".join(page.get("content", "") for page in pages)
        return any(marker in text for marker in ["相反", "争议", "不一致", "contradict", "conflict"])

    def _fallback_rewrites(self, original_query: str, plan: ResearchPlan) -> list[str]:
        suffixes = ["权威 来源", "最新 信息", "案例 分析"]
        if plan.question_type == "buying_advice":
            suffixes = ["选购 指南", "材质 对比", "避坑 经验"]
        return [f"{original_query} {suffix}" for suffix in suffixes[: self.settings.max_rewrite_queries]]
