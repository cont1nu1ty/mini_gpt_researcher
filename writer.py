from __future__ import annotations

import json
import re
from collections import defaultdict

from citation_manager import build_citation_labels, citation_label_for, format_references
from config import Settings
from llm_client import LLMClient
from prompts import (
    GPT_RESEARCHER_STYLE_OUTLINE_PROMPT,
    GPT_RESEARCHER_STYLE_REPORT_PROMPT,
    GPT_RESEARCHER_STYLE_RESOURCE_PROMPT,
    WRITER_PROMPT,
    WRITER_SYSTEM_PROMPT,
)
from utils import clean_text, parse_json_object, save_markdown


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

RESOURCE_REPORT_SECTIONS = [
    "## 1. 资料概览",
    "## 2. 推荐来源",
    "## 3. 来源对研究问题的贡献",
    "## 4. 证据强度与局限",
    "## 5. 使用建议",
    "## 6. 参考来源",
]

OUTLINE_REPORT_SECTIONS = [
    "## 1. 核心论题",
    "## 2. 建议结构",
    "## 3. 分节要点",
    "## 4. 证据与引用安排",
    "## 5. 待补充问题",
    "## 6. 参考来源",
]

SUPPORTED_REPORT_TYPES = {"research_report", "resource_report", "outline_report"}


class Writer:
    max_model_sources = 10

    def __init__(self, llm: LLMClient, settings: Settings | None = None) -> None:
        self.llm = llm
        self.settings = settings
        self.report_type = self._normalize_report_type(getattr(settings, "report_type", "research_report"))
        self.report_format = getattr(settings, "report_format", "APA")
        self.total_words = getattr(settings, "total_words", 1200)
        self.prompt_style = getattr(settings, "writer_prompt_style", "gpt_researcher")

    def write(self, query: str, sub_questions: list[str], summaries: list[dict]) -> str:
        if not summaries:
            return self._empty_report(query, sub_questions)

        normalized = [self._normalize_summary(item) for item in summaries]
        model_context = self._build_model_context(normalized)
        prompt = self._build_prompt(
            query=query,
            sub_questions=sub_questions,
            summaries=model_context,
        )
        try:
            markdown = self.llm.chat(
                prompt,
                system_prompt=WRITER_SYSTEM_PROMPT,
                temperature=0.3,
                max_tokens=65536,
                thinking="enabled",
            )
        except Exception as exc:
            print(f"Warning: 报告生成失败，使用本地模板 fallback。原因：{exc}")
            markdown = self._template_report(query, sub_questions, normalized)

        markdown = self._ensure_required_sections(markdown, query, sub_questions, normalized)
        markdown = self._normalize_inline_citations(markdown, normalized)
        return self._ensure_reference_section(markdown, normalized)

    def save(self, markdown: str) -> str:
        return str(save_markdown(markdown))

    def _template_report(self, query: str, sub_questions: list[str], summaries: list[dict]) -> str:
        if self.report_type == "resource_report":
            return self._resource_template_report(query, sub_questions, summaries)
        if self.report_type == "outline_report":
            return self._outline_template_report(query, sub_questions, summaries)

        normalized = [self._normalize_summary(item) for item in summaries]
        findings = []
        for index, item in enumerate(normalized, start=1):
            summary = item.get("summary", "")
            if summary:
                findings.append(f"- {summary} [{index}]")
            for point in item.get("key_points", [])[:2]:
                findings.append(f"  - {point}")

        grouped = defaultdict(list)
        for index, item in enumerate(normalized, start=1):
            grouped[item.get("query") or query].append((index, item))

        themed_lines = []
        for topic, items in grouped.items():
            themed_lines.append(f"### {topic}")
            for index, item in items[:4]:
                key_points = item.get("key_points", [])
                if key_points:
                    themed_lines.extend(f"- {point} [{index}]" for point in key_points[:3])
                elif item.get("summary"):
                    themed_lines.append(f"- {item['summary']} [{index}]")

        conclusion = self._build_local_conclusion(query, normalized)
        return "\n".join(
            [
                f"# {query} 调研报告",
                "",
                "## 1. 摘要",
                f"本报告围绕“{query}”整理自动搜索、检索评估和证据精炼后的来源摘要。"
                "以下结论仅基于本次可访问网页和搜索摘要，低置信来源已在局限性中说明。",
                "",
                "## 2. 研究问题",
                "\n".join(f"- {item}" for item in sub_questions),
                "",
                "## 3. 背景介绍",
                self._build_background(query, normalized),
                "",
                "## 4. 主要发现",
                "\n".join(findings[:16]) if findings else "- 未获得足够的结构化发现。",
                "",
                "## 5. 分主题分析",
                "\n".join(themed_lines) if themed_lines else "- 暂无可分析来源。",
                "",
                "## 6. 结论",
                conclusion,
                "",
                "## 7. 局限性",
                self._build_limitations(normalized),
                "",
                "## 8. 参考来源",
                format_references(normalized),
            ]
        )

    def _empty_report(self, query: str, sub_questions: list[str]) -> str:
        if self.report_type == "resource_report":
            return "\n".join(
                [
                    f"# {query} 资料推荐报告",
                    "",
                    "## 1. 资料概览",
                    "本次运行未获得可用网页摘要，因此无法形成资料推荐。",
                    "",
                    "## 2. 推荐来源",
                    "- 未获得可用来源。",
                    "",
                    "## 3. 来源对研究问题的贡献",
                    "- 暂无可分析来源。",
                    "",
                    "## 4. 证据强度与局限",
                    "本报告基于自动搜索和网页摘要生成，可能受搜索结果质量、网页可访问性和模型总结能力影响。",
                    "",
                    "## 5. 使用建议",
                    "建议检查网络连接、搜索服务可用性或更换更具体的研究问题后重试。",
                    "",
                    "## 6. 参考来源",
                    "- 本次运行没有可列出的参考来源。",
                ]
            )
        if self.report_type == "outline_report":
            return "\n".join(
                [
                    f"# {query} 报告提纲",
                    "",
                    "## 1. 核心论题",
                    "本次运行未获得可用网页摘要，因此无法形成充分证据支持的报告提纲。",
                    "",
                    "## 2. 建议结构",
                    "- 暂无可用来源支撑结构设计。",
                    "",
                    "## 3. 分节要点",
                    "- 暂无可分析来源。",
                    "",
                    "## 4. 证据与引用安排",
                    "- 暂无可引用来源。",
                    "",
                    "## 5. 待补充问题",
                    "- 需要重新搜索或更换检索源。",
                    "",
                    "## 6. 参考来源",
                    "- 本次运行没有可列出的参考来源。",
                ]
            )
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
        if self.report_type == "research_report" and self._is_usable_research_report(markdown, summaries):
            return markdown
        if all(section in markdown for section in self._required_sections()):
            return markdown
        return self._template_report(query, sub_questions, summaries)

    def _ensure_reference_section(self, markdown: str, summaries: list[dict]) -> str:
        marker = self._find_reference_marker(markdown)
        references = format_references(summaries)
        if marker not in markdown:
            marker = self._reference_marker()
            return f"{markdown.rstrip()}\n\n{marker}\n{references}\n"
        before = markdown.split(marker, 1)[0].rstrip()
        return f"{before}\n\n{marker}\n{references}\n"

    def _normalize_summary(self, item: dict) -> dict:
        summary = clean_text(str(item.get("summary", "")))
        key_points = [clean_text(str(point)) for point in item.get("key_points", []) if clean_text(str(point))]
        if summary.startswith("```") or ('"summary"' in summary and '"key_points"' in summary):
            try:
                parsed = parse_json_object(summary)
                summary = clean_text(str(parsed.get("summary", ""))) or summary
                key_points = [
                    clean_text(str(point))
                    for point in parsed.get("key_points", [])
                    if clean_text(str(point))
                ] or key_points
            except Exception:
                pass
        normalized = dict(item)
        normalized["summary"] = summary
        normalized["key_points"] = key_points
        return normalized

    def _compact_summaries_for_model(self, summaries: list[dict]) -> list[dict]:
        compact = []
        for item in summaries[: self.max_model_sources]:
            compact.append(
                {
                    "title": clean_text(str(item.get("title", "")))[:120],
                    "url": item.get("url", ""),
                    "query": clean_text(str(item.get("query", "")))[:120],
                    "summary": clean_text(str(item.get("summary", "")))[:500],
                    "key_points": [clean_text(str(point))[:180] for point in item.get("key_points", [])[:4]],
                    "evaluation_label": item.get("evaluation_label", "unknown"),
                    "content_source": item.get("content_source", "web_page"),
                }
            )
        return compact

    def _build_model_context(self, summaries: list[dict]) -> str:
        lines = []
        citation_labels = build_citation_labels(summaries)
        for index, item in enumerate(self._compact_summaries_for_model(summaries), start=1):
            citation_label = citation_label_for(item, citation_labels)
            url = item.get("url", "")
            lines.extend(
                [
                    f"[{index}] {item.get('title') or 'Untitled'}",
                    f"URL: {url}",
                    f"正文短引用: ([{citation_label}]({url}))",
                    f"检索 query: {item.get('query', '')}",
                    f"证据来源类型: {item.get('content_source', 'unknown')}",
                    f"评估标签: {item.get('evaluation_label', 'unknown')}",
                    f"摘要: {item.get('summary', '')}",
                ]
            )
            key_points = item.get("key_points", [])
            if key_points:
                lines.append("关键证据:")
                lines.extend(f"- {point}" for point in key_points)
            lines.append("")
        return "\n".join(lines).strip()

    def _build_prompt(self, query: str, sub_questions: list[str], summaries: list[dict]) -> str:
        prompt_kwargs = {
            "query": query,
            "sub_questions": json.dumps(sub_questions, ensure_ascii=False, indent=2),
            "summaries": summaries if isinstance(summaries, str) else json.dumps(summaries, ensure_ascii=False, indent=2),
            "report_format": self.report_format,
            "total_words": self.total_words,
        }
        if self.prompt_style != "gpt_researcher":
            return WRITER_PROMPT.format(**prompt_kwargs)
        if self.report_type == "resource_report":
            return GPT_RESEARCHER_STYLE_RESOURCE_PROMPT.format(**prompt_kwargs)
        if self.report_type == "outline_report":
            return GPT_RESEARCHER_STYLE_OUTLINE_PROMPT.format(**prompt_kwargs)
        return GPT_RESEARCHER_STYLE_REPORT_PROMPT.format(**prompt_kwargs)

    def _normalize_report_type(self, report_type: str) -> str:
        report_type = clean_text(str(report_type)).lower()
        if report_type not in SUPPORTED_REPORT_TYPES:
            return "research_report"
        return report_type

    def _is_usable_research_report(self, markdown: str, summaries: list[dict]) -> bool:
        text = clean_text(markdown)
        if len(text) < 800:
            return False
        if not markdown.lstrip().startswith("#"):
            return False
        heading_count = sum(1 for line in markdown.splitlines() if line.startswith("## "))
        if heading_count < 3:
            return False
        urls = [str(item.get("url", "")).strip() for item in summaries if item.get("url")]
        cited_count = sum(1 for url in urls if url and url in markdown)
        if urls and cited_count == 0:
            return False
        return True

    def _required_sections(self) -> list[str]:
        if self.report_type == "resource_report":
            return RESOURCE_REPORT_SECTIONS
        if self.report_type == "outline_report":
            return OUTLINE_REPORT_SECTIONS
        return REQUIRED_SECTIONS

    def _reference_marker(self) -> str:
        if self.report_type in {"resource_report", "outline_report"}:
            return "## 6. 参考来源"
        return "## 8. 参考来源"

    def _find_reference_marker(self, markdown: str) -> str:
        candidates = [self._reference_marker(), "## 参考来源", "## References"]
        for marker in candidates:
            if marker in markdown:
                return marker
        return self._reference_marker()

    def _normalize_inline_citations(self, markdown: str, summaries: list[dict]) -> str:
        labels = build_citation_labels(summaries)
        marker = self._find_reference_marker(markdown)
        if marker in markdown:
            body, references = markdown.split(marker, 1)
            suffix = f"{marker}{references}"
        else:
            body, suffix = markdown, ""
        for url, label in labels.items():
            if not url:
                continue
            escaped_url = re.escape(url)
            body = re.sub(
                rf"\[([^\]\n]+)\]\({escaped_url}\)",
                lambda match: self._shorten_link_text(match, label, url),
                body,
            )
        return f"{body}{suffix}"

    def _shorten_link_text(self, match: re.Match, label: str, url: str) -> str:
        text = match.group(1).strip()
        if text == label:
            return match.group(0)
        if text.startswith("http://") or text.startswith("https://") or len(text) > 14:
            return f"[{label}]({url})"
        if re.search(r"[\u4e00-\u9fff]", text) and len(text) >= 6:
            return f"[{label}]({url})"
        generic_texts = {"来源", "网页", "资料", "参考", "链接", "source"}
        if text.lower() in generic_texts:
            return f"[{label}]({url})"
        return match.group(0)

    def _resource_template_report(self, query: str, sub_questions: list[str], summaries: list[dict]) -> str:
        normalized = [self._normalize_summary(item) for item in summaries]
        rows = ["| 来源 | 贡献 | 证据强度 |", "| --- | --- | --- |"]
        for index, item in enumerate(normalized, start=1):
            source_type = item.get("content_source", "web_page")
            strength = "低" if source_type == "search_snippet" or item.get("evaluation_label") == "ambiguous" else "中高"
            rows.append(f"| [{index}] {item.get('title', 'Untitled')} | {item.get('summary', '')} | {strength} |")
        return "\n".join(
            [
                f"# {query} 资料推荐报告",
                "",
                "## 1. 资料概览",
                f"本报告围绕“{query}”整理可用于后续写作的资料来源。",
                "",
                "## 2. 推荐来源",
                "\n".join(rows),
                "",
                "## 3. 来源对研究问题的贡献",
                "\n".join(f"- {point} [{index}]" for index, item in enumerate(normalized, start=1) for point in item.get("key_points", [])[:2])
                or "- 暂无足够结构化要点。",
                "",
                "## 4. 证据强度与局限",
                self._build_limitations(normalized),
                "",
                "## 5. 使用建议",
                "优先使用证据强度较高、能直接回答研究问题的来源；对低置信搜索摘要只作线索，不作强结论依据。",
                "",
                "## 6. 参考来源",
                format_references(normalized),
            ]
        )

    def _outline_template_report(self, query: str, sub_questions: list[str], summaries: list[dict]) -> str:
        normalized = [self._normalize_summary(item) for item in summaries]
        grouped = defaultdict(list)
        for index, item in enumerate(normalized, start=1):
            grouped[item.get("query") or query].append((index, item))
        section_lines = []
        for topic, items in grouped.items():
            section_lines.append(f"### {topic}")
            for index, item in items[:3]:
                if item.get("summary"):
                    section_lines.append(f"- 可用证据：{item['summary']} [{index}]")
                for point in item.get("key_points", [])[:2]:
                    section_lines.append(f"  - {point}")
        return "\n".join(
            [
                f"# {query} 报告提纲",
                "",
                "## 1. 核心论题",
                f"围绕“{query}”建立一个基于证据的研究报告框架。",
                "",
                "## 2. 建议结构",
                "- 摘要\n- 背景介绍\n- 主要发现\n- 分主题分析\n- 结论与局限性\n- 参考来源",
                "",
                "## 3. 分节要点",
                "\n".join(section_lines) if section_lines else "- 暂无可分析来源。",
                "",
                "## 4. 证据与引用安排",
                "建议在每个分节中引用与该分节直接相关的 URL；低置信 search_snippet 只作为补充线索。",
                "",
                "## 5. 待补充问题",
                "\n".join(f"- {item}" for item in sub_questions) if sub_questions else "- 暂无。",
                "",
                "## 6. 参考来源",
                format_references(normalized),
            ]
        )

    def _build_background(self, query: str, summaries: list[dict]) -> str:
        climate_points = [
            point
            for item in summaries
            for point in item.get("key_points", [])
            if any(token in point for token in ["北京", "夏季", "紫外线", "炎热", "干燥", "昼夜温差"])
        ]
        if climate_points:
            return " ".join(climate_points[:3])
        return f"本报告围绕“{query}”汇总可访问网页和搜索摘要中的材料，重点关注场景、材质、工艺参数和购买决策。"

    def _build_local_conclusion(self, query: str, summaries: list[dict]) -> str:
        points = [point for item in summaries for point in item.get("key_points", [])]
        if any(token in query for token in ["购买", "挑选", "选购", "短袖", "材质"]):
            recommendations = []
            if any("纯棉" in point or "棉" in point for point in points):
                recommendations.append("日常通勤可优先看透气棉或棉混纺，但要注意纯棉排湿慢、易皱和缩水。")
            if any("速干" in point or "化纤" in point or "聚酯" in point for point in points):
                recommendations.append("高温出汗或运动场景可考虑速干化纤或功能混纺，重点看排汗、快干和亲肤性。")
            if any("克重" in point for point in points):
                recommendations.append("夏季 T 恤克重可优先试 180g-220g，过薄易透，过厚偏闷。")
            if any("支数" in point for point in points):
                recommendations.append("支数、克重和工艺要一起看，不宜只按单一参数判断品质。")
            if recommendations:
                return "\n".join(f"- {item}" for item in recommendations)
        return "从当前资料看，该主题已有可观察的信息，但仍需更多高质量来源交叉验证。"

    def _build_limitations(self, summaries: list[dict]) -> str:
        snippet_count = sum(1 for item in summaries if item.get("content_source") == "search_snippet")
        ambiguous_count = sum(1 for item in summaries if item.get("evaluation_label") == "ambiguous")
        lines = [
            "本报告基于自动搜索、网页抓取和网页摘要生成，可能受搜索结果质量、网页可访问性和模型总结能力影响。"
        ]
        if snippet_count:
            lines.append(f"其中 {snippet_count} 个来源来自搜索摘要 snippet，未能抓取完整网页正文，证据强度较低。")
        if ambiguous_count:
            lines.append(f"其中 {ambiguous_count} 个来源被标记为 ambiguous，相关但证据覆盖有限。")
        return "\n".join(f"- {line}" for line in lines)
