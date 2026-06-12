from __future__ import annotations

from config import Settings
from writer import OUTLINE_REPORT_SECTIONS, REQUIRED_SECTIONS, RESOURCE_REPORT_SECTIONS, Writer


class FakeLLM:
    def __init__(self, response: str) -> None:
        self.response = response

    def chat(self, prompt: str, system_prompt: str | None = None, temperature: float = 0.3, **kwargs) -> str:
        return self.response


def test_writer_falls_back_when_sections_missing():
    writer = Writer(FakeLLM("bad report"))
    markdown = writer.write(
        "AI Agent 在高校教学中的应用现状",
        ["有哪些应用？"],
        [{"title": "来源", "url": "https://example.com", "query": "有哪些应用？", "summary": "有智能助教。"}],
    )

    assert all(section in markdown for section in REQUIRED_SECTIONS)
    assert "https://example.com" in markdown


def test_writer_empty_report_contains_limitations():
    writer = Writer(FakeLLM(""))
    markdown = writer.write("研究问题", ["研究问题"], [])

    assert "未获得可用来源" in markdown
    assert "本报告基于自动搜索和网页摘要生成" in markdown


def test_writer_template_cleans_json_summaries_and_builds_actionable_report():
    class FailingLLM:
        def chat(self, prompt: str, system_prompt: str | None = None, temperature: float = 0.3, **kwargs) -> str:
            raise RuntimeError("timeout")

    writer = Writer(FailingLLM())
    markdown = writer.write(
        "北京夏季男性短袖购买，材质工艺挑选",
        ["男士短袖面料怎么选？"],
        [
            {
                "title": "短袖克重",
                "url": "https://example.com/weight",
                "query": "短袖克重怎么选",
                "summary": '```json\n{"summary": "夏季短袖建议关注克重和透气性。", "key_points": ["夏季 T 恤克重可优先试 180g-220g", "过厚偏闷热"]}\n```',
                "key_points": [],
                "evaluation_label": "ambiguous",
                "content_source": "search_snippet",
            },
            {
                "title": "面料",
                "url": "https://example.com/fabric",
                "query": "男士短袖面料",
                "summary": "纯棉吸湿但排湿慢，速干化纤更适合出汗场景。",
                "key_points": ["纯棉排湿慢", "速干化纤适合运动"],
            },
        ],
    )

    assert "```json" not in markdown
    assert "180g-220g" in markdown
    assert "速干化纤" in markdown
    assert "搜索摘要 snippet" in markdown


def test_writer_uses_compact_model_prompt_without_reducing_generation_budget():
    class InspectingLLM:
        def __init__(self) -> None:
            self.prompt = ""
            self.kwargs = {}

        def chat(self, prompt: str, system_prompt: str | None = None, temperature: float = 0.3, **kwargs) -> str:
            self.prompt = prompt
            self.kwargs = kwargs
            return "\n".join(
                [
                    "# 报告",
                    "",
                    "## 1. 摘要",
                    "摘要",
                    "",
                    "## 2. 研究问题",
                    "- 问题",
                    "",
                    "## 3. 背景介绍",
                    "背景",
                    "",
                    "## 4. 主要发现",
                    "- 发现",
                    "",
                    "## 5. 分主题分析",
                    "- 分析",
                    "",
                    "## 6. 结论",
                    "结论",
                    "",
                    "## 7. 局限性",
                    "局限",
                    "",
                    "## 8. 参考来源",
                    "- 来源：https://example.com",
                ]
            )

    llm = InspectingLLM()
    writer = Writer(llm)
    summaries = [
        {
            "title": f"来源{i}",
            "url": f"https://example.com/{i}",
            "query": "短袖",
            "summary": "很长的摘要" * 300,
            "key_points": ["要点"] * 10,
        }
        for i in range(12)
    ]

    writer.write("短袖选购", ["怎么选？"], summaries)

    assert llm.kwargs["max_tokens"] == 65536
    assert llm.kwargs["thinking"] == "enabled"
    assert "https://example.com/10" not in llm.prompt
    assert len(llm.prompt) < 12000
    assert "URL: https://example.com/0" in llm.prompt
    assert '"url":' not in llm.prompt


def test_writer_preserves_gpt_researcher_style_report_without_numbered_sections():
    report = "\n".join(
        [
            "# 北京夏季男士短袖材质工艺挑选",
            "",
            "北京夏季高温、通勤和空调切换让短袖选择需要同时考虑透气、挺括和耐洗。",
            "",
            "## 材质选择",
            "精梳棉适合日常通勤，速干混纺适合大量出汗场景。([来源](https://example.com/fabric))",
            "",
            "## 工艺指标",
            "克重、支数和领口工艺需要结合判断。([来源](https://example.com/craft))",
            "",
            "## 场景建议",
            "办公室可选棉氨混纺，户外优先速干和防晒。",
            "",
            "## 参考来源",
            "- 来源：https://example.com/fabric",
            "- 工艺：https://example.com/craft",
        ]
    )
    report += "\n" + ("补充分析。" * 220)
    writer = Writer(FakeLLM(report))

    markdown = writer.write(
        "北京夏季男性短袖购买，材质工艺挑选",
        ["材质怎么选？"],
        [
            {"title": "来源", "url": "https://example.com/fabric", "query": "面料", "summary": "精梳棉和速干。"},
            {"title": "工艺", "url": "https://example.com/craft", "query": "工艺", "summary": "克重和支数。"},
        ],
    )

    assert "## 材质选择" in markdown
    assert "## 1. 摘要" not in markdown
    assert "本报告围绕" not in markdown
    assert "https://example.com/fabric" in markdown


def test_writer_supports_resource_report_type():
    class FailingLLM:
        def chat(self, prompt: str, system_prompt: str | None = None, temperature: float = 0.3, **kwargs) -> str:
            raise RuntimeError("timeout")

    writer = Writer(FailingLLM(), Settings(zai_api_key="test", report_type="resource_report"))
    markdown = writer.write(
        "AI Agent 教育应用",
        ["有哪些资料？"],
        [
            {
                "title": "资料来源",
                "url": "https://example.com/resource",
                "query": "AI Agent 教育",
                "summary": "介绍智能助教应用。",
                "key_points": ["智能助教", "个性化反馈"],
            }
        ],
    )

    assert all(section in markdown for section in RESOURCE_REPORT_SECTIONS)
    assert "## 8. 参考来源" not in markdown
    assert "https://example.com/resource" in markdown


def test_writer_supports_outline_report_type_and_uses_gpt_researcher_style_prompt():
    class InspectingLLM:
        def __init__(self) -> None:
            self.prompt = ""

        def chat(self, prompt: str, system_prompt: str | None = None, temperature: float = 0.3, **kwargs) -> str:
            self.prompt = prompt
            raise RuntimeError("timeout")

    llm = InspectingLLM()
    writer = Writer(llm, Settings(zai_api_key="test", report_type="outline_report", total_words=800))
    markdown = writer.write(
        "AI Agent 教育应用",
        ["提纲怎么写？"],
        [
            {
                "title": "提纲来源",
                "url": "https://example.com/outline",
                "query": "AI Agent 教育",
                "summary": "介绍报告结构。",
                "key_points": ["背景", "应用", "挑战"],
            }
        ],
    )

    assert "生成一份结构化研究报告提纲" in llm.prompt
    assert "约 800 字的报告" in llm.prompt
    assert all(section in markdown for section in OUTLINE_REPORT_SECTIONS)


def test_writer_gpt_researcher_style_prompts_are_chinese():
    class InspectingLLM:
        def __init__(self) -> None:
            self.prompt = ""

        def chat(self, prompt: str, system_prompt: str | None = None, temperature: float = 0.3, **kwargs) -> str:
            self.prompt = prompt
            raise RuntimeError("timeout")

    llm = InspectingLLM()
    writer = Writer(llm, Settings(zai_api_key="test", report_type="research_report"))
    writer.write(
        "北京夏季男士短袖选购",
        ["面料怎么选？"],
        [
            {
                "title": "来源",
                "url": "https://example.com",
                "query": "短袖",
                "summary": "面料对比。",
                "key_points": ["棉", "速干"],
            }
        ],
    )

    assert "资料信息" in llm.prompt
    assert "报告要求" in llm.prompt
    assert "自行设计有信息量的一级、二级、三级标题" in llm.prompt
    assert "报告必须包含以下 Markdown 章节标题" not in llm.prompt
    assert "Research sub-questions" not in llm.prompt
    assert "Report requirements" not in llm.prompt
