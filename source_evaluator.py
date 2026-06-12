from __future__ import annotations

import json
import re
from dataclasses import dataclass

from llm_client import LLMClient
from prompts import SOURCE_EVALUATOR_PROMPT, SOURCE_EVALUATOR_SYSTEM_PROMPT
from utils import clean_text, truncate_text


VALID_LABELS = {"correct", "incorrect", "ambiguous"}


@dataclass(frozen=True)
class SourceEvaluation:
    label: str
    score: float
    reason: str
    refined_content: str


class SourceEvaluator:
    def __init__(self, llm: LLMClient, *, max_eval_chars: int = 5000) -> None:
        self.llm = llm
        self.max_eval_chars = max_eval_chars

    def evaluate_many(self, pages: list[dict]) -> list[dict]:
        evaluated_pages: list[dict] = []
        for page in pages:
            evaluated = self.evaluate(page)
            if evaluated["evaluation_label"] == "incorrect":
                print(f"Warning: 来源评估为不可用，已跳过。url={page.get('url')}，原因：{evaluated['evaluation_reason']}")
                continue
            evaluated_pages.append(evaluated)
        return evaluated_pages

    def evaluate(self, page: dict) -> dict:
        content = clean_text(page.get("content", ""))
        if not content:
            return self._attach_evaluation(page, SourceEvaluation("incorrect", 0.0, "网页正文为空。", ""))

        prompt = SOURCE_EVALUATOR_PROMPT.format(
            query=page.get("query", ""),
            title=page.get("title", ""),
            url=page.get("url", ""),
            content=truncate_text(content, self.max_eval_chars),
        )
        try:
            response = self.llm.chat(prompt, system_prompt=SOURCE_EVALUATOR_SYSTEM_PROMPT, temperature=0.0)
            evaluation = self._parse_response(response, content)
        except Exception as exc:
            print(f"Warning: 来源评估失败，使用本地规则 fallback。url={page.get('url')}，原因：{exc}")
            evaluation = self._heuristic_evaluation(page, content)
        return self._attach_evaluation(page, evaluation)

    def _parse_response(self, response: str, original_content: str) -> SourceEvaluation:
        try:
            parsed = json.loads(response)
        except Exception as exc:
            raise ValueError(f"评估器 JSON 解析失败：{exc}") from exc

        label = str(parsed.get("label", "")).strip().lower()
        if label not in VALID_LABELS:
            raise ValueError(f"评估器 label 无效：{label}")

        score = self._clamp_score(parsed.get("score", 0.5))
        reason = clean_text(str(parsed.get("reason", ""))) or "模型未给出原因。"
        refined_content = clean_text(str(parsed.get("refined_content", "")))
        if not refined_content and label != "incorrect":
            refined_content = original_content
        return SourceEvaluation(label=label, score=score, reason=reason, refined_content=refined_content)

    def _heuristic_evaluation(self, page: dict, content: str) -> SourceEvaluation:
        query_terms = self._tokenize(page.get("query", ""))
        title_terms = self._tokenize(page.get("title", ""))
        content_terms = self._tokenize(content)
        overlap = len((query_terms | title_terms) & content_terms)

        if len(content) < 200:
            return SourceEvaluation("incorrect", 0.1, "正文过短，无法支撑摘要。", "")
        if overlap >= 2:
            return SourceEvaluation("ambiguous", 0.55, "本地规则发现部分关键词重合，但仍需模型摘要时谨慎使用。", content)
        return SourceEvaluation("incorrect", 0.2, "本地规则未发现与查询相关的明显关键词。", "")

    def _attach_evaluation(self, page: dict, evaluation: SourceEvaluation) -> dict:
        updated = dict(page)
        updated["evaluation_label"] = evaluation.label
        updated["evaluation_score"] = evaluation.score
        updated["evaluation_reason"] = evaluation.reason
        if evaluation.refined_content:
            updated["content"] = evaluation.refined_content
        return updated

    def _clamp_score(self, raw_score) -> float:
        try:
            score = float(raw_score)
        except (TypeError, ValueError):
            score = 0.5
        return max(0.0, min(1.0, score))

    def _tokenize(self, text: str) -> set[str]:
        text = clean_text(text).lower()
        tokens = {item for item in re.findall(r"[a-z0-9][a-z0-9_\-]{1,}", text)}
        for chunk in re.findall(r"[\u4e00-\u9fff]{2,}", text):
            tokens.add(chunk)
            tokens.update(chunk[index : index + 2] for index in range(max(0, len(chunk) - 1)))
        return tokens
