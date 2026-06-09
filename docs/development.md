# 开发说明

## AI/Codex 协作最佳实践

- 保持模块小而清晰，每个文件只承担一个职责。
- Prompt 集中放在 `prompts.py`，便于评审和迭代。
- 所有外部边界都要有异常处理：模型、搜索、网页抓取、JSON 解析。
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
