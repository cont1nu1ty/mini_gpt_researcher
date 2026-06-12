from __future__ import annotations

from verifier import Verifier


class FakeLLM:
    def __init__(self, response: str) -> None:
        self.response = response

    def chat(self, prompt: str, system_prompt: str | None = None, temperature: float = 0.3, **kwargs) -> str:
        return self.response


def test_verifier_parses_revision_required():
    verifier = Verifier(
        FakeLLM(
            """
            {
              "supported": false,
              "missing_user_intent": true,
              "citation_issues": ["缺少 URL"],
              "unsupported_claims": ["断言缺证据"],
              "revision_required": true
            }
            """
        )
    )

    result = verifier.verify("问题", "报告", [])

    assert result["revision_required"] is True
    assert result["citation_issues"] == ["缺少 URL"]


def test_verifier_revises_reference_section():
    verifier = Verifier(FakeLLM("{}"))
    markdown = "# 报告\n\n## 8. 参考来源\n- old"
    summaries = [{"title": "来源", "url": "https://example.com"}]

    revised = verifier.revise(
        markdown,
        {"revision_required": True, "citation_issues": ["bad"], "unsupported_claims": [], "missing_user_intent": False},
        summaries,
    )

    assert "https://example.com" in revised
    assert "- old" not in revised


def test_verifier_only_appends_actionable_unsupported_claims():
    verifier = Verifier(FakeLLM("{}"))

    revised = verifier.revise(
        "# 报告\n\n## 8. 参考来源\n- 来源",
        {
            "revision_required": True,
            "citation_issues": [],
            "unsupported_claims": ["精梳棉通过剔除短纤维改善平滑度", "结论缺乏证据支持"],
            "missing_user_intent": False,
        },
        [],
    )

    assert "结论缺乏证据支持" in revised
    assert "精梳棉通过剔除短纤维" not in revised
