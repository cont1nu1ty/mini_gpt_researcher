from __future__ import annotations

import main


def test_main_passes_debug_flag_to_agent(monkeypatch):
    calls = []

    class FakeAgent:
        def __init__(self, *, debug: bool = False) -> None:
            calls.append(("init", debug))

        def run(self, query: str) -> str:
            calls.append(("run", query))
            return "outputs/report.md"

    monkeypatch.setattr(main, "ResearchAgent", FakeAgent)

    assert main.main(["北京夏季男性短袖购买，材质工艺挑选", "--debug"]) == 0
    assert calls == [
        ("init", True),
        ("run", "北京夏季男性短袖购买，材质工艺挑选"),
    ]


def test_main_keeps_plain_query_mode(monkeypatch):
    calls = []

    class FakeAgent:
        def __init__(self, *, debug: bool = False) -> None:
            calls.append(("init", debug))

        def run(self, query: str) -> str:
            calls.append(("run", query))
            return "outputs/report.md"

    monkeypatch.setattr(main, "ResearchAgent", FakeAgent)

    assert main.main(["AI Agent", "高校教学"]) == 0
    assert calls == [
        ("init", False),
        ("run", "AI Agent 高校教学"),
    ]
