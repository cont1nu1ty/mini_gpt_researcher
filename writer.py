from __future__ import annotations

import json

from citation_manager import format_references
from llm_client import LLMClient
from prompts import WRITER_PROMPT, WRITER_SYSTEM_PROMPT
from utils import save_markdown


REQUIRED_SECTIONS = [
    "## 1. 摘要",
    "## 2. 研究问题",
    "## 3. 背景介绍",
    "## 4. 主要发现",
    "## 5. 分主题分析",
    "## 6. 结论",
    "## 7. 局限性",
    "## 8. 参考来源",
]


class Writer:
    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def write(self, query: str, sub_questions: list[str], summaries: list[dict]) -> str:
        if not summaries:
            return self._empty_report(query, sub_questions)

        prompt = WRITER_PROMPT.format(
            query=query,
            sub_questions=json.dumps(sub_questions, ensure_ascii=False, indent=2),
            summaries=json.dumps(summaries, ensure_ascii=False, indent=2),
        )
        try:
            markdown = self.llm.chat(prompt, system_prompt=WRITER_SYSTEM_PROMPT, temperature=0.4)
        except Exception as exc:
            print(f"Warning: 报告生成失败，使用本地模板 fallback。原因：{exc}")
            markdown = self._template_report(query, sub_questions, summaries)

        markdown = self._ensure_required_sections(markdown, query, sub_questions, summaries)
        return self._ensure_reference_section(markdown, summaries)

    def save(self, markdown: str) -> str:
        return str(save_markdown(markdown))

    def _template_report(self, query: str, sub_questions: list[str], summaries: list[dict]) -> str:
        findings = []
        for index, item in enumerate(summaries, start=1):
            findings.append(f"- {item.get('summary', '')} [{index}]")
        return "\n".join(
            [
                f"# {query} 调研报告",
                "",
                "## 1. 摘要",
                f"本报告围绕“{query}”整理自动搜索到的网页摘要。",
                "",
                "## 2. 研究问题",
                "\n".join(f"- {item}" for item in sub_questions),
                "",
                "## 3. 背景介绍",
                "背景信息来自自动抓取网页的摘要，需结合人工复核进一步确认。",
                "",
                "## 4. 主要发现",
                "\n".join(findings),
                "",
                "## 5. 分主题分析",
                "\n".join(f"- {item.get('query', query)}：{item.get('summary', '')}" for item in summaries),
                "",
                "## 6. 结论",
                "从当前资料看，该主题已有可观察的应用和讨论，但仍需更多高质量来源交叉验证。",
                "",
                "## 7. 局限性",
                "本报告基于自动搜索和网页摘要生成，可能受搜索结果质量、网页可访问性和模型总结能力影响。",
                "",
                "## 8. 参考来源",
                format_references(summaries),
            ]
        )

    def _empty_report(self, query: str, sub_questions: list[str]) -> str:
        return "\n".join(
            [
                f"# {query} 调研报告",
                "",
                "## 1. 摘要",
                "本次运行未获得可用网页摘要，因此无法形成充分证据支持的调研结论。",
                "",
                "## 2. 研究问题",
                "\n".join(f"- {item}" for item in sub_questions),
                "",
                "## 3. 背景介绍",
                "暂无可用网页正文作为背景材料。",
                "",
                "## 4. 主要发现",
                "- 未获得可用来源。",
                "",
                "## 5. 分主题分析",
                "- 暂无可分析来源。",
                "",
                "## 6. 结论",
                "建议检查网络连接、搜索服务可用性或更换更具体的研究问题后重试。",
                "",
                "## 7. 局限性",
                "本报告基于自动搜索和网页摘要生成，可能受搜索结果质量、网页可访问性和模型总结能力影响。",
                "",
                "## 8. 参考来源",
                "- 本次运行没有可列出的参考来源。",
            ]
        )

    def _ensure_required_sections(
        self,
        markdown: str,
        query: str,
        sub_questions: list[str],
        summaries: list[dict],
    ) -> str:
        if all(section in markdown for section in REQUIRED_SECTIONS):
            return markdown
        return self._template_report(query, sub_questions, summaries)

    def _ensure_reference_section(self, markdown: str, summaries: list[dict]) -> str:
        marker = "## 8. 参考来源"
        references = format_references(summaries)
        if marker not in markdown:
            return f"{markdown.rstrip()}\n\n{marker}\n{references}\n"
        before = markdown.split(marker, 1)[0].rstrip()
        return f"{before}\n\n{marker}\n{references}\n"
