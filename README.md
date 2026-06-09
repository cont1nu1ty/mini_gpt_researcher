# Mini GPT Researcher

`mini_gpt_researcher` 是一个基于大语言模型的自主调研与报告生成 CLI 原型。用户输入一个研究问题后，程序会自动完成问题拆解、资料搜索、网页读取、来源摘要和中文 Markdown 报告生成。

本项目不是 GPT Researcher 的完整复刻，而是参考其核心流程实现的轻量级 CLI 原型。项目保留了“规划、搜索、阅读、摘要、报告生成”的主流程，删除了前端、后端、多智能体框架、MCP、PDF 导出等复杂模块。

## 项目架构

```text
main.py        CLI 入口
agent.py       串联完整研究流程
planner.py     将原问题拆解为 3-5 个子问题
searcher.py    使用 DuckDuckGo 搜索网页结果
crawler.py     使用 requests + BeautifulSoup 抓取网页正文
summarizer.py  调用 GLM 5.1 总结单个网页来源
writer.py      生成最终中文 Markdown 报告
citation_manager.py 参考来源去重与格式化
prompts.py     集中管理 Prompt 模板
config.py      读取 .env 配置
utils.py       文本清洗、去重、保存文件等工具
docs/          架构、开发、数据合规说明
tests/         离线单元测试
evals/         作业展示用离线质量检查
outputs/       默认报告输出目录
```

## 和 GPT Researcher 的关系

GPT Researcher 是完整的深度研究框架，包含更复杂的检索器、网页处理、上下文管理、多智能体、前后端和导出能力。本项目只实现最小主链路：

```text
Planner -> Searcher -> Crawler -> Summarizer -> Writer -> Citation Manager
```

## 安装方式

```bash
cd mini_gpt_researcher
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 配置 .env

```bash
cp .env.example .env
```

然后填写：

```env
ZAI_API_KEY=your_api_key_here
ZAI_BASE_URL=https://api.z.ai/api/paas/v4
ZAI_MODEL=glm-5.1
```

不要把真实 `.env` 提交到版本库。

## 运行方式

命令行直接传入问题：

```bash
python main.py "AI Agent 在高校教学中的应用现状"
```

或者交互式输入：

```bash
python main.py
```

程序会提示：

```text
请输入研究问题：
```

## 输出示例

运行过程中会显示：

```text
开始规划研究问题...
已生成 4 个子问题。
开始搜索资料...
搜索到 12 条去重后的网页结果。
开始抓取网页...
成功抓取 6 个网页正文。
开始总结来源...
成功生成 6 条来源摘要。
开始生成报告...
报告已保存：outputs/report.md
```

报告保存到：

```text
outputs/report.md
```

## 项目裁剪说明

为了适合作业展示，本项目刻意不实现：

- 前端页面
- FastAPI 后端服务
- MCP 服务
- 复杂多智能体框架
- Docker 部署
- PDF / Word 导出
- 数据库
- 登录系统
- 复杂评估系统

## 测试与评估

离线单元测试：

```bash
python -m pytest
```

离线结构评估：

```bash
python evals/scripts/run_offline_eval.py
```

该评估不调用 LLM，也不联网，只检查报告结构、局限性声明和引用格式等基础质量。

## 后续可扩展方向

- 增加 Tavily、Bing、Serper 等可替换搜索器。
- 增加 robots.txt 检查、缓存和更细粒度网页正文抽取。
- 支持多轮研究和中间结果保存。
- 支持按领域定制 Prompt。
- 增加人工标注评测集和引用准确性评估。
