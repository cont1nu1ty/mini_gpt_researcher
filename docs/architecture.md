# 架构说明

`mini_gpt_researcher` 采用 CRAG-inspired 纠错式检索流水线，避免复杂框架：

```text
CLI -> ResearchAgent
    -> Initial Search
    -> QueryPlanner
    -> Searcher / Retriever
    -> Crawler
    -> RetrievalEvaluator
    -> ActionRouter
    -> EvidenceRefiner
    -> Summarizer
    -> Writer
    -> Verifier
    -> outputs/report.md
```

## 模块边界

- `config.py`：只负责读取 `.env` 和默认配置。
- `llm_client.py`：只负责 GLM 模型调用，默认使用 `zai-sdk`，可选 OpenAI-compatible 兜底。
- `query_planner.py`：只负责结合用户问题与初始搜索结果，分析问题类型、生成子问题和结构化搜索 query。
- `searcher.py`：只负责网页搜索、Tavily/SearXNG 可选检索、结果相关性过滤和 URL 去重。
- `crawler.py`：只负责读取检索器原文或抓取公开网页正文；抓取失败时由 `ResearchAgent` 暂存搜索摘要低置信候选证据。
- `retrieval_evaluator.py`：只负责批量评估检索结果，输出 `correct`、`incorrect` 或 `ambiguous` 及补搜建议。
- `action_router.py`：只负责根据评估结果决定进入证据精炼或继续补搜。
- `evidence_refiner.py`：只负责 passage 分块、片段 rerank、去重和冲突标记。
- `summarizer.py`：负责把精炼后的来源整理成写作上下文；默认使用本地抽取式整理，必要时可切换为逐来源 LLM 摘要。
- `writer.py`：只负责按 `REPORT_TYPE` 整合报告和引用来源，支持标准调研报告、资料推荐报告和提纲报告。
- `verifier.py`：只负责校验报告是否被证据支持，并做一次轻量修订。
- `citation_manager.py`：只负责参考来源去重和格式化。

## 失败策略

- QueryPlanner 模型调用或 JSON 解析失败：使用原问题作为唯一 broad query。
- 搜索失败：打印 warning，继续执行。
- 搜索结果与 query 无明显重合：跳过该 provider 的低相关结果，继续尝试下一个 provider。
- 网页抓取失败：返回空内容并跳过正文证据。
- 网页抓取失败但搜索结果有 snippet：先暂存为 `search_snippet`；只有完整网页、检索器原文和补搜仍不足时，才作为最后低置信 fallback 加入评估。
- 检索评估失败：使用本地关键词、正文长度和域名规则 fallback。
- 路由补搜达到 `MAX_SEARCH_ROUNDS`：停止补搜，使用已有部分证据继续生成报告。
- 证据精炼无结果：报告生成空来源说明。
- 来源整理失败：本地抽取式整理会尽量保留精炼 passage；LLM 摘要模式下解析失败时使用文本 fallback。
- 报告校验失败：使用本地 URL 检查 fallback。
- 没有任何资料：仍生成说明性 Markdown 报告。
