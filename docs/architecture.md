# 架构说明

`mini_gpt_researcher` 采用线性流水线，避免复杂框架：

```text
CLI -> ResearchAgent
    -> Planner
    -> Searcher
    -> Crawler
    -> Summarizer
    -> Writer
    -> outputs/report.md
```

## 模块边界

- `config.py`：只负责读取 `.env` 和默认配置。
- `llm_client.py`：只负责 OpenAI-compatible 模型调用。
- `planner.py`：只负责把研究问题拆成 JSON 子问题。
- `searcher.py`：只负责网页搜索和 URL 去重。
- `crawler.py`：只负责抓取公开网页正文。
- `summarizer.py`：只负责单来源摘要。
- `writer.py`：只负责整合报告和引用来源。
- `citation_manager.py`：只负责参考来源去重和格式化。

## 失败策略

- Planner JSON 解析失败：使用原问题作为唯一子问题。
- 搜索失败：打印 warning，继续执行。
- 网页抓取失败：返回空内容并跳过摘要。
- 摘要失败：跳过该来源或使用文本 fallback。
- 没有任何资料：仍生成说明性 Markdown 报告。
