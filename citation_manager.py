from __future__ import annotations

import re
from urllib.parse import urlparse


DOMAIN_LABELS = {
    "baidu.com": "Baidu",
    "b2bwiki.baidu.com": "Baidu B2B",
    "bilibili.com": "Bilibili",
    "blog.csdn.net": "CSDN",
    "bk.taobao.com": "Taobao Baike",
    "clothing.taobao.com": "Taobao",
    "csdn.net": "CSDN",
    "gq.com.tw": "GQ Taiwan",
    "jd.com": "JD",
    "shuma.taobao.com": "Taobao",
    "smzdm.com": "SMZDM",
    "sohu.com": "Sohu",
    "tibetcn.com": "TibetCN",
    "tshe.com": "Tshe",
    "zhihu.com": "Zhihu",
    "zhuanlan.zhihu.com": "Zhihu",
}


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
    return "\n".join(_format_reference(item, summaries) for item in references)


def build_citation_labels(summaries: list[dict]) -> dict[str, str]:
    references = collect_references(summaries)
    return {
        item["url"]: _base_citation_label(item.get("title", ""), item.get("url", ""), _source_text(summaries, item.get("url", "")))
        for item in references
    }


def citation_label_for(item: dict, labels: dict[str, str] | None = None) -> str:
    url = str(item.get("url", "")).strip()
    if labels and url in labels:
        return labels[url]
    return _base_citation_label(str(item.get("title", "")), url, _single_source_text(item))


def _base_citation_label(title: str, url: str, source_text: str = "") -> str:
    source = _source_name(title, url)
    year = _year_from_text(" ".join([title, source_text, url]))
    return f"{source}, {year}"


def _format_reference(item: dict, summaries: list[dict]) -> str:
    title = _clean_title(str(item.get("title") or "Untitled"))
    url = str(item.get("url", "")).strip()
    source = _source_name(title, url)
    year = _year_from_text(" ".join([title, _source_text(summaries, url), url]))
    return f"- {source}. ({year}). {title}. [{source}]({url})"


def _source_name(title: str, url: str) -> str:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    for domain, label in DOMAIN_LABELS.items():
        if host == domain or host.endswith(f".{domain}"):
            return label
    if host:
        parts = host.split(".")
        if len(parts) >= 2:
            return parts[-2].replace("-", " ").title()
        return host.title()
    title = re.sub(r"[_｜|].*$", "", title).strip()
    return title[:24] or "Source"


def _clean_title(title: str) -> str:
    title = re.sub(r"\s+", " ", title).strip()
    title = re.sub(r"\s+[-–—]\s+(知乎|搜狐|CSDN|哔哩哔哩|bilibili|淘宝|百度百科|什么值得买).*$", "", title, flags=re.IGNORECASE)
    return title or "Untitled"


def _year_from_text(text: str) -> str:
    match = re.search(r"(?:19|20)\d{2}", text)
    return match.group(0) if match else "n.d."


def _source_text(summaries: list[dict], url: str) -> str:
    for item in summaries:
        if str(item.get("url", "")).strip() == url:
            return _single_source_text(item)
    return ""


def _single_source_text(item: dict) -> str:
    return " ".join(
        [
            str(item.get("summary", "")),
            " ".join(str(point) for point in item.get("key_points", [])),
            str(item.get("query", "")),
        ]
    )
