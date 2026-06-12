PLANNER_SYSTEM_PROMPT = "你是一个严谨的中文研究规划助手。输出必须可被 JSON 解析。"

PLANNER_PROMPT = """请将下面的研究问题拆解成 {max_sub_questions} 个以内的研究子问题。

要求：
- 只返回 JSON 数组，不要 Markdown，不要解释。
- 数组元素必须是中文问题字符串。
- 子问题要覆盖背景、现状、典型案例、技术路径、挑战或趋势。

研究问题：
{query}
"""

RESEARCH_PLAN_SYSTEM_PROMPT = "你是一个严谨的中文研究计划助手。输出必须可被 JSON 解析。"

RESEARCH_PLAN_PROMPT = """请为下面的用户问题生成检索研究计划。

要求：
- 只返回 JSON 对象，不要 Markdown，不要解释。
- question_type 只能是 fact、literature_review、comparison、latest、multi_hop、buying_advice。
- needs_freshness 表示是否需要近期信息。
- sub_questions 最多 {max_sub_questions} 个。
- search_queries 最多 {max_planned_queries} 个。
- search_queries[].mode 只能是 broad、targeted、source_specific。
- query 要适合直接用于搜索引擎。
- 如果给出了初始搜索结果，请利用它修正搜索方向，但不要被明显跑题结果带偏。

返回 JSON 格式：
{{
  "question_type": "fact|literature_review|comparison|latest|multi_hop|buying_advice",
  "needs_freshness": false,
  "research_intent": "用户真正想解决的问题",
  "sub_questions": ["中文子问题"],
  "search_queries": [
    {{"query": "搜索词", "mode": "broad", "purpose": "搜索目的"}}
  ]
}}

用户问题：
{query}

初始搜索结果：
{initial_context}
"""

QUERY_REWRITE_SYSTEM_PROMPT = "你是一个检索 query 改写助手。输出必须可被 JSON 解析。"

QUERY_REWRITE_PROMPT = """当前检索结果质量不足，请改写搜索 query 以补充更可靠的来源。

要求：
- 只返回 JSON 数组，不要 Markdown，不要解释。
- 最多返回 {max_rewrite_queries} 个对象。
- mode 只能是 broad、targeted、source_specific。
- query 要避免重复已有失败方向，并尽量更具体。

原始问题：
{query}

研究意图：
{research_intent}

问题类型：
{question_type}

当前轮次：
{round_index}

检索评估：
{evaluation}

返回 JSON 格式：
[
  {{"query": "改写后的搜索词", "mode": "targeted", "purpose": "为什么补搜"}}
]
"""

SUMMARIZER_SYSTEM_PROMPT = "你是一个严谨的中文研究证据整理助手，只能基于给定网页正文抽取可用于报告写作的事实、参数和判断。"

SUMMARIZER_PROMPT = """请基于网页正文，整理可直接用于研究报告写作的证据。

要求：
- 使用中文。
- 不要编造网页中没有的信息。
- 如果来源评估为 ambiguous，请明确保持谨慎，不要把低置信信息写成确定事实。
- 如果正文信息不足，请明确说信息有限。
- 返回 JSON 对象，字段为 summary 和 key_points。
- key_points 是 2 到 5 条中文要点。
- summary 要直接概括该来源提供了哪些实质信息，不要使用“该网页与研究子问题相关”“网页正文提供了”这类元叙述开头。
- key_points 优先保留具体材料、工艺参数、数值范围、适用场景、风险或反例。
- 如果来源主要是商品列表、广告页或内容很浅，请把局限性写入 summary，而不是把它包装成强证据。

研究子问题：
{query}

网页标题：
{title}

网页 URL：
{url}

来源评估：
- label: {evaluation_label}
- score: {evaluation_score}
- reason: {evaluation_reason}

网页正文：
{content}
"""

SOURCE_EVALUATOR_SYSTEM_PROMPT = "你是一个严谨的资料检索评估器，只判断网页内容是否可用于回答研究子问题。输出必须可被 JSON 解析。"

SOURCE_EVALUATOR_PROMPT = """请评估下面网页内容是否适合作为研究子问题的资料来源。

要求：
- 只返回 JSON 对象，不要 Markdown，不要解释。
- label 只能是 correct、incorrect 或 ambiguous。
- correct 表示网页正文与研究子问题高度相关，且有可用于报告的实质信息。
- incorrect 表示网页正文为空、低质量、广告/导航/列表页为主、明显跑题，或无法支撑研究问题。
- ambiguous 表示部分相关但证据不充分、信息较泛、主题边缘相关，后续摘要时应谨慎使用。
- score 是 0 到 1 之间的小数，表示可用性置信度。
- reason 用一句中文说明判断理由。
- refined_content 只保留与研究子问题有关的关键正文；如果 label 为 incorrect，refined_content 为空字符串。
- 不要引入网页正文之外的信息。

返回 JSON 格式：
{{
  "label": "correct|incorrect|ambiguous",
  "score": 0.0,
  "reason": "一句中文理由",
  "refined_content": "筛选后的关键正文"
}}

研究子问题：
{query}

网页标题：
{title}

网页 URL：
{url}

网页正文：
{content}
"""

RETRIEVAL_EVALUATOR_SYSTEM_PROMPT = "你是一个严谨的批量检索评估器。只基于给定搜索结果和正文片段判断，不要引入外部知识。输出必须可被 JSON 解析。"

RETRIEVAL_EVALUATOR_PROMPT = """请评估本轮检索结果是否足以支撑后续报告。

要求：
- 只返回 JSON 对象，不要 Markdown，不要解释。
- label 只能是 correct、incorrect、ambiguous。
- relevance、authority、freshness、coverage 都是 0 到 1 的小数。
- accepted_urls 只能包含输入 evidence 中的 URL。
- rejected_urls 只能包含输入 evidence 中的 URL。
- 如果结果不足，请给出 suggested_rewrite_queries，最多 3 条。
- correct 表示至少有 {min_accepted_sources} 个可用来源且覆盖用户意图。
- incorrect 表示整体跑题、低质量、正文不足或不能支撑问题。
- ambiguous 表示有部分可用证据但覆盖不足，需要继续搜索。

原始问题：
{original_query}

研究意图：
{research_intent}

问题类型：
{question_type}

是否需要新鲜信息：
{needs_freshness}

搜索轮次：
{round_index}

Evidence:
{evidence}

返回 JSON 格式：
{{
  "label": "correct|incorrect|ambiguous",
  "relevance": 0.0,
  "authority": 0.0,
  "freshness": 0.0,
  "coverage": 0.0,
  "contradiction": false,
  "reason": "一句中文原因",
  "suggested_rewrite_queries": ["补搜 query"],
  "accepted_urls": ["https://..."],
  "rejected_urls": ["https://..."]
}}
"""

WRITER_SYSTEM_PROMPT = "你是一个严谨的中文研究报告写作者，必须基于给定摘要和真实 URL 写作。"

WRITER_PROMPT = """请基于以下研究问题、子问题和网页摘要，生成中文 Markdown 调研报告。

硬性要求：
- 不要编造来源，不要引用输入之外的 URL。
- 区分确定事实、推测/经验判断、不确定或证据不足，不要把低置信信息写成确定结论。
- 优先使用 content_source 为 retriever_raw_content 或 web_page 的来源；search_snippet 只能作为低置信补充。
- 主要发现要给出可执行结论，避免只罗列来源摘要。
- 分主题分析中可使用 Markdown 表格做对比，例如材质、适用场景、优点、风险、证据强度。
- 报告必须包含这些一级/二级标题：
  # 调研报告标题
  ## 1. 摘要
  ## 2. 研究问题
  ## 3. 背景介绍
  ## 4. 主要发现
  ## 5. 分主题分析
  ## 6. 结论
  ## 7. 局限性
  ## 8. 参考来源
- “局限性”必须说明：本报告基于自动搜索和网页摘要生成，可能受搜索结果质量、网页可访问性和模型总结能力影响。
- 如果使用了 search_snippet 来源，必须说明它未抓取到完整正文，不能作为强证据。
- 在正文中使用来源信息时，必须使用资料中给出的“正文短引用”格式，例如 `([Sohu, 2024](URL))`，不要把完整网页标题作为正文链接文字。
- “参考来源”中每条包含完整标题和 URL。

原始研究问题：
{query}

子问题：
{sub_questions}

网页摘要：
{summaries}
"""

GPT_RESEARCHER_STYLE_REPORT_PROMPT = """资料信息：
{summaries}
---
请基于以上资料，围绕下面的问题或任务撰写一份详细调研报告："{query}"。

报告要求：
- 使用中文和 Markdown 语法写作，并尽量符合 {report_format} 格式风格。
- 报告必须聚焦回答用户问题，结构清晰、信息充分、分析深入、覆盖全面。
- 当证据足够时，正文目标不少于 {total_words} 字。
- 像正式研究报告一样组织内容：自行设计有信息量的一级、二级、三级标题，不要按来源逐条复述，不要写成资料清单。
- 优先围绕主题归纳综合，例如材料类型、工艺指标、使用场景、购买避坑、结论建议等；只有在适合比较时才使用列表。
- 必须基于给定资料形成具体、有效的判断，不要写空泛结论。
- 做对比分析时优先使用 Markdown 表格，尤其适用于材质、场景、风险、证据强度等内容。
- 优先考虑来源的相关性、可靠性和重要性；当来源可信时，优先使用较新的资料。
- 不得编造输入中没有的来源、事实、数字或 URL。
- 必须区分“确定事实”“经验判断/推测”和“证据不足或不确定”。
- 优先使用 content_source=retriever_raw_content 和 content_source=web_page 的来源；search_snippet 只能作为低置信补充证据。
- 如果使用了 search_snippet，必须在“局限性”中说明未抓取到完整网页正文，证据强度较弱。
- 在正文中使用来源信息时，必须使用资料中给出的“正文短引用”格式，例如 `([Sohu, 2024](URL))`。
- 不要把完整网页标题作为正文链接文字；完整标题和完整 URL 只放在文末“参考来源”。
- 报告末尾必须包含“参考来源”章节，列出实际使用过的标题和完整 URL，避免重复来源。
- 不要输出目录。

研究子问题：
{sub_questions}
"""

GPT_RESEARCHER_STYLE_RESOURCE_PROMPT = """资料信息："{summaries}"
---
请基于以上资料，围绕下面的问题或主题生成一份资料/文献推荐报告："{query}"。

报告要求：
- 使用中文和 Markdown 语法写作，并尽量符合 {report_format} 格式风格。
- 说明每个推荐来源如何帮助回答研究问题。
- 重点分析每个来源的相关性、可靠性、重要性、证据强度和局限性。
- 适合用表格时使用 Markdown 表格组织信息。
- 不得编造输入中没有的来源或 URL。
- 优先使用完整网页正文或检索器原文，不要优先依赖 search_snippet。
- 如果使用 search_snippet，必须标注为低置信资料线索。
- 当证据足够时，正文目标不少于 {total_words} 字。

报告必须包含以下 Markdown 章节标题：
# {query} 资料推荐报告
## 1. 资料概览
## 2. 推荐来源
## 3. 来源对研究问题的贡献
## 4. 证据强度与局限
## 5. 使用建议
## 6. 参考来源

研究子问题：
{sub_questions}
"""

GPT_RESEARCHER_STYLE_OUTLINE_PROMPT = """资料信息："{summaries}"
---
请基于以上资料，为下面的问题或主题生成一份结构化研究报告提纲："{query}"。

提纲要求：
- 使用中文和 Markdown 语法。
- 为最终报告提供清晰框架，包括主要章节、子章节和应覆盖的关键要点。
- 如果资料中有可用证据或 URL，应将其安排到对应章节下。
- 能提升清晰度时，可以使用 Markdown 表格。
- 不得编造输入中没有的来源、URL、事实或数字。
- 必须明确标注不确定问题和弱证据，尤其是 search_snippet 证据。
- 提纲应足够详细，能够指导撰写一篇约 {total_words} 字的报告。

提纲必须包含以下 Markdown 章节标题：
# {query} 报告提纲
## 1. 核心论题
## 2. 建议结构
## 3. 分节要点
## 4. 证据与引用安排
## 5. 待补充问题
## 6. 参考来源

研究子问题：
{sub_questions}
"""

VERIFIER_SYSTEM_PROMPT = "你是一个严谨的报告校验器，检查报告是否被给定证据支持。输出必须可被 JSON 解析。"

VERIFIER_PROMPT = """请校验报告是否被证据支持。

要求：
- 只返回 JSON 对象，不要 Markdown，不要解释。
- supported 表示主要结论是否能由 evidence summaries 支持。
- missing_user_intent 表示报告是否遗漏用户核心问题。
- citation_issues 列出引用缺失、URL 不匹配或引用不在证据中的问题。
- unsupported_claims 列出报告中证据不足的关键断言。
- revision_required 表示是否需要一次轻量修订。

用户问题：
{query}

报告：
{markdown}

Evidence summaries:
{summaries}

返回 JSON 格式：
{{
  "supported": true,
  "missing_user_intent": false,
  "citation_issues": [],
  "unsupported_claims": [],
  "revision_required": false
}}
"""
