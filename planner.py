from __future__ import annotations

import json

from config import Settings
from llm_client import LLMClient
from prompts import PLANNER_PROMPT, PLANNER_SYSTEM_PROMPT


class Planner:
    def __init__(self, llm: LLMClient, settings: Settings) -> None:
        self.llm = llm
        self.settings = settings

    def plan(self, query: str) -> list[str]:
        prompt = PLANNER_PROMPT.format(query=query, max_sub_questions=self.settings.max_sub_questions)
        try:
            response = self.llm.chat(prompt, system_prompt=PLANNER_SYSTEM_PROMPT, temperature=0.2)
            parsed = json.loads(response)
            questions = [str(item).strip() for item in parsed if str(item).strip()]
            return questions[: self.settings.max_sub_questions] or [query]
        except Exception as exc:
            print(f"Warning: 子问题 JSON 解析失败，使用原问题作为 fallback。原因：{exc}")
            return [query]
