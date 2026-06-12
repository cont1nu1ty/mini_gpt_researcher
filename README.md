# Mini GPT Researcher

`mini_gpt_researcher` 是一个基于大语言模型的自主调研与报告生成 CLI 原型。用户输入一个研究问题后，程序会自动完成问题分析、搜索规划、多轮资料检索、检索评估、证据精炼、来源摘要、报告生成和校验。

本项目不是 GPT Researcher 的完整复刻，而是参考其核心流程实现的轻量级 CLI 原型。项目保留了“规划、搜索、阅读、摘要、报告生成”的主流程，删除了前端、后端、多智能体框架、MCP、PDF 导出等复杂模块。

## 项目架构

```text
main.py        CLI 入口
agent.py       串联完整研究流程
query_planner.py 分析问题类型并生成结构化搜索计划
searcher.py    使用多搜索后端检索网页并过滤低相关结果
crawler.py     使用 requests + BeautifulSoup 抓取网页正文
retrieval_evaluator.py 批量评估检索质量并建议补搜
action_router.py 根据评估结果决定精炼或继续搜索
evidence_refiner.py 对网页正文分块、rerank、去重
summarizer.py  调用 GLM 5.1 总结单个网页来源
writer.py      生成最终中文 Markdown 报告
verifier.py    校验报告是否被证据支持
citation_manager.py 参考来源去重与格式化
llm_client.py  通过 zai-sdk 调用 GLM 5.1，支持 OpenAI-compatible 兜底
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
QuestionAnalyzer/QueryPlanner -> Searcher/Retriever -> Crawler
-> RetrievalEvaluator -> ActionRouter -> EvidenceRefinement
-> Summarizer -> Writer -> Verifier -> Citation Manager
```

其中检索评估与路由借鉴 CRAG（Corrective Retrieval Augmented Generation）的思想：先判断检索结果为 `correct`、`incorrect` 或 `ambiguous`，再决定进入证据精炼、改写 query 补搜，或保留部分证据继续搜索。本项目没有照搬 CRAG 中的 T5 评估器训练、vLLM 推理、Serper/Google 搜索扩展等重型流程，而是使用现有 LLM 做批量轻量评估，并保留本地规则 fallback。流程会先做一次初始搜索辅助 QueryPlanner 规划；网页抓取失败时，搜索摘要只作为最后的低置信候选证据，避免因为 403 或 timeout 直接生成空报告。

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
LLM_PROVIDER=zai
ZAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4
ZAI_MODEL=glm-5.1
ZAI_THINKING=enabled
ZAI_MAX_TOKENS=65536
LLM_TIMEOUT_SECONDS=60
MAX_PLANNED_QUERIES=6
SEARCH_PROVIDER=auto
SEARCH_AGGREGATE_PROVIDERS=true
TAVILY_API_KEY=
TAVILY_INCLUDE_RAW_CONTENT=true
SEARXNG_BASE_URL=
MAX_SEARCH_RESULTS=4
MAX_SEARCH_WORKERS=4
MAX_SEARCH_ROUNDS=2
MAX_REWRITE_QUERIES=3
MIN_ACCEPTED_SOURCES=4
SUMMARIZER_MODE=extractive
REPORT_TYPE=research_report
REPORT_FORMAT=APA
TOTAL_WORDS=1200
WRITER_PROMPT_STYLE=gpt_researcher
```

不要把真实 `.env` 提交到版本库。

默认 `LLM_PROVIDER=zai`，使用官方 `zai-sdk`：

```python
from zai import ZhipuAiClient
```

如果你确认当前账号或网关必须走 OpenAI-compatible 调用，可以改成：

```env
LLM_PROVIDER=openai_compatible
ZAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4
```

注意：`ZAI_BASE_URL` 只写到 `/api/paas/v4`，不要追加 `/chat/completions`；客户端会自动调用 chat completions 路径。

搜索默认使用 `SEARCH_PROVIDER=auto` 且 `SEARCH_AGGREGATE_PROVIDERS=true`，会聚合多个可用搜索源，去重、排序后返回最相关结果。如果配置了 `TAVILY_API_KEY`，会优先纳入 Tavily 并尽量读取检索器返回的 `raw_content`；未配置时保持免费链路，聚合 `ddgs`、可选 SearXNG JSON、DuckDuckGo HTML、Bing HTML、Baidu HTML。`SEARXNG_BASE_URL` 为空时会自动跳过 SearXNG。国内网络下如果只想使用某个后端，可以手动指定：

```env
SEARCH_PROVIDER=baidu_html
```

可选值：

```text
auto
tavily
ddgs
searxng_json
duckduckgo_html
bing_html
baidu_html
```

报告默认使用 `REPORT_TYPE=research_report`，并采用参考 GPT Researcher 的 prompt 风格。可选报告类型：

```text
research_report   标准调研报告
resource_report   资料/文献推荐报告
outline_report    研究报告提纲
```

可以通过 `.env` 切换：

```env
REPORT_TYPE=resource_report
REPORT_FORMAT=APA
TOTAL_WORDS=1200
WRITER_PROMPT_STYLE=gpt_researcher
```

`SUMMARIZER_MODE=extractive` 表示默认使用本地抽取式证据整理，把 `EvidenceRefiner` 选出的 passage 直接交给报告生成器综合写作，减少逐来源模型调用导致的超时风险；如需逐来源 LLM 摘要，可显式设为 `SUMMARIZER_MODE=llm`。

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
开始分析问题并规划搜索...
问题类型：buying_advice；已生成 4 个搜索 query。
开始第 1 轮搜索资料...
本轮新增 12 条网页结果，累计 12 条。
开始抓取网页...
本轮成功抓取 6 个网页正文，累计 6 个。
开始批量评估检索质量...
检索评估：ambiguous；可用来源 3 个。
路由决策：keep_and_search。
已生成 2 个补搜 query。
开始证据精炼...
保留 5 个精炼后的证据来源。
开始总结来源...
成功生成 5 条来源摘要。
开始生成报告...
开始校验报告...
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
