# 开发说明

## AI/Codex 协作最佳实践

- 保持模块小而清晰，每个文件只承担一个职责。
- Prompt 集中放在 `prompts.py`，便于评审和迭代。
- 所有外部边界都要有异常处理：模型、搜索、网页抓取、JSON 解析。
- GLM 默认使用 `zai-sdk` 的 `ZhipuAiClient`；仅在需要兼容网关时使用 `LLM_PROVIDER=openai_compatible`。
- OpenAI-compatible 兜底的 base URL 使用 `https://open.bigmodel.cn/api/paas/v4`，不要包含 `/chat/completions`。
- 搜索默认使用 `SEARCH_PROVIDER=auto` 和 `SEARCH_AGGREGATE_PROVIDERS=true` 聚合多后端；可选 `TAVILY_API_KEY` 启用 Tavily，`SEARXNG_BASE_URL` 启用 SearXNG JSON。
- `search_snippet` 只能作为最后的低置信 fallback，不应优先于检索器原文或成功抓取的网页正文。
- 报告生成支持 `research_report`、`resource_report`、`outline_report` 三种轻量类型；切换报告结构时必须同步更新 writer 测试和离线评估。
- 抓取后的网页必须先经过 `RetrievalEvaluator` 批量评估和 `ActionRouter` 路由，再进入证据精炼与摘要阶段；评估标签使用 `correct`、`incorrect`、`ambiguous`。
- 补搜必须受 `MAX_SEARCH_ROUNDS` 限制，避免无限循环和模型调用失控。
- 改报告结构时同步更新 `tests/` 和 `evals/`。
- 不引入大型 agent 框架，优先保持作业可讲解性。

## 本地检查

```bash
python -m pytest
python evals/scripts/run_offline_eval.py
```

## 手动验收

```bash
cp .env.example .env
# 填写 ZAI_API_KEY
python main.py "大语言模型智能体在教育领域的应用现状"
```
