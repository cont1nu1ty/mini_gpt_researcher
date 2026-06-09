from __future__ import annotations


def collect_references(summaries: list[dict]) -> list[dict]:
    seen: set[str] = set()
    references: list[dict] = []
    for item in summaries:
        url = str(item.get("url", "")).strip()
        if not url or url in seen:
            continue
        seen.add(url)
        references.append({"title": str(item.get("title") or "Untitled"), "url": url})
    return references


def format_references(summaries: list[dict]) -> str:
    references = collect_references(summaries)
    if not references:
        return "- 本次运行没有可列出的参考来源。"
    return "\n".join(f"- [{index}] {item['title']}：{item['url']}" for index, item in enumerate(references, start=1))
