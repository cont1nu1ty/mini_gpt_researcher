from __future__ import annotations

import argparse
import sys

from agent import ResearchAgent
from config import ConfigError


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="轻量级 GPT Researcher CLI")
    parser.add_argument("query", nargs="*", help="研究问题。留空时进入交互式输入。")
    parser.add_argument("--debug", action="store_true", help="显示每一步的结构化中间数据。")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    query = " ".join(args.query).strip()
    if not query:
        query = input("请输入研究问题：").strip()
    if not query:
        print("研究问题不能为空。")
        return 2

    try:
        agent = ResearchAgent(debug=args.debug)
        agent.run(query)
    except ConfigError as exc:
        print(f"配置错误：{exc}")
        return 1
    except KeyboardInterrupt:
        print("\n用户中断运行。")
        return 130
    except Exception as exc:
        print(f"运行失败：{exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
