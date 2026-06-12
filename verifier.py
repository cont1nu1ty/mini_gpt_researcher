from __future__ import annotations

import json

from citation_manager import format_references
from llm_client import LLMClient
from prompts import VERIFIER_PROMPT, VERIFIER_SYSTEM_PROMPT
from utils import clean_text, parse_json_object


class Verifier:
    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def verify(self, query: str, markdown: str, summaries: list[dict]) -> dict:
        prompt = VERIFIER_PROMPT.format(
            query=query,
            markdown=markdown[:12000],
            summaries=json.dumps(self._compact_summaries(summaries), ensure_ascii=False, indent=2),
        )
        try:
            response = self.llm.chat(
                prompt,
                system_prompt=VERIFIER_SYSTEM_PROMPT,
                temperature=0.0,
                max_tokens=65536,
                thinking="enabled",
            )
            return self._parse_response(response)
        except Exception as exc:
            print(f"Warning: 报告校验失败，使用本地校验 fallback。原因：{exc}")
            return self._local_verify(query, markdown, summaries)

    def revise(self, markdown: str, verification: dict, summaries: list[dict]) -> str:
        if not verification.get("revision_required", False):
            return markdown

        revised = markdown.rstrip()
        citation_issues = verification.get("citation_issues", [])
        unsupported_claims = self._actionable_unsupported_claims(verification.get("unsupported_claims", []))
        if citation_issues and "## 8. 参考来源" in revised:
            before = revised.split("## 8. 参考来源", 1)[0].rstrip()
            revised = f"{before}\n\n## 8. 参考来源\n{format_references(summaries)}"
        if verification.get("missing_user_intent", False):
            revised += "\n\n## 未充分覆盖的问题\n- 当前证据未完全覆盖用户问题，建议补充更具体或更权威的来源后复核。"
        if unsupported_claims:
            revised += "\n\n## 证据支持性提示\n"
            revised += "\n".join(f"- {item}" for item in unsupported_claims[:5])
        return revised + "\n"

    def _parse_response(self, response: str) -> dict:
        parsed = parse_json_object(response)
        return {
            "supported": bool(parsed.get("supported", False)),
            "missing_user_intent": bool(parsed.get("missing_user_intent", False)),
            "citation_issues": self._string_list(parsed.get("citation_issues", [])),
            "unsupported_claims": self._string_list(parsed.get("unsupported_claims", [])),
            "revision_required": bool(parsed.get("revision_required", False)),
        }

    def _local_verify(self, query: str, markdown: str, summaries: list[dict]) -> dict:
        urls = [str(item.get("url", "")).strip() for item in summaries if item.get("url")]
        missing_urls = [url for url in urls if url not in markdown]
        missing_user_intent = bool(query and query[:8] not in markdown)
        return {
            "supported": not missing_urls,
            "missing_user_intent": missing_user_intent,
            "citation_issues": [f"报告缺少参考 URL：{url}" for url in missing_urls],
            "unsupported_claims": [],
            "revision_required": bool(missing_urls or missing_user_intent),
        }

    def _string_list(self, raw) -> list[str]:
        if not isinstance(raw, list):
            return []
        return [str(item).strip() for item in raw if str(item).strip()]

    def _compact_summaries(self, summaries: list[dict]) -> list[dict]:
        compact = []
        for item in summaries[:12]:
            compact.append(
                {
                    "title": clean_text(str(item.get("title", "")))[:100],
                    "url": item.get("url", ""),
                    "summary": clean_text(str(item.get("summary", "")))[:360],
                    "key_points": [clean_text(str(point))[:140] for point in item.get("key_points", [])[:3]],
                }
            )
        return compact

    def _actionable_unsupported_claims(self, claims: list[str]) -> list[str]:
        markers = [
            "缺乏",
            "未支持",
            "不能支持",
            "无法支持",
            "不匹配",
            "相悖",
            "矛盾",
            "遗漏",
            "unsupported",
            "not supported",
            "contradict",
        ]
        actionable = []
        for claim in self._string_list(claims):
            lowered = claim.lower()
            if any(marker in lowered for marker in markers):
                actionable.append(claim)
        return actionable
