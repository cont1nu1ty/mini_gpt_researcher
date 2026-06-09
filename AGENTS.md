# Mini GPT Researcher 开发约束

## 项目目标

实现一个轻量 CLI research agent，保留 GPT Researcher 的核心链路：
规划问题、搜索资料、读取网页、摘要来源、生成 Markdown 报告。

## 工程规则

- 不引入 LangChain、LangGraph、CrewAI、AutoGen 等大型框架。
- 不实现前端、后端 API、MCP、Docker、数据库、登录、PDF/Word 导出。
- 不在代码、README、测试或样例中写入真实 API Key。
- 不编造引用；报告参考来源只能来自实际搜索/抓取/摘要过的 URL。
- 网络请求必须设置 User-Agent、timeout 和异常处理。
- 模型输出 JSON 的地方必须有解析失败 fallback。
- 改 prompts、报告结构或质量规则时，同步更新 `evals/` 或 `tests/`。

## 推荐检查

```bash
python -m pytest
python evals/scripts/run_offline_eval.py
python main.py "AI Agent 在高校教学中的应用现状"
```
