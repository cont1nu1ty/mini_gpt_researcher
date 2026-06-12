from __future__ import annotations

from action_router import ActionRouter
from config import load_settings
from crawler import Crawler
from evidence_refiner import EvidenceRefiner
from llm_client import LLMClient
from query_planner import PlannedQuery, QueryPlanner
from retrieval_evaluator import RetrievalEvaluator
from searcher import SearchResult, Searcher
from summarizer import Summarizer
from verifier import Verifier
from writer import Writer


class ResearchAgent:
    def __init__(self) -> None:
        self.settings = load_settings(require_api_key=True)
        self.llm = LLMClient(self.settings)
        self.query_planner = QueryPlanner(self.llm, self.settings)
        self.searcher = Searcher(self.settings)
        self.crawler = Crawler(self.settings)
        self.retrieval_evaluator = RetrievalEvaluator(self.llm, self.settings)
        self.action_router = ActionRouter(self.settings)
        self.evidence_refiner = EvidenceRefiner()
        self.summarizer = Summarizer(self.llm, self.settings)
        self.writer = Writer(self.llm, self.settings)
        self.verifier = Verifier(self.llm)

    def run(self, query: str) -> str:
        print("开始初始搜索以辅助规划...")
        initial_results = self.searcher.search(query, mode="broad", purpose="辅助生成搜索计划")
        print(f"初始搜索获得 {len(initial_results)} 条结果。")

        print("开始分析问题并规划搜索...")
        plan = self.query_planner.plan(query, initial_results=initial_results)
        print(f"问题类型：{plan.question_type}；已生成 {len(plan.search_queries)} 个搜索 query。")

        all_results = []
        all_pages = []
        seen_result_urls: set[str] = set()
        seen_page_urls: set[str] = set()
        snippet_candidates = []
        seen_snippet_urls: set[str] = set()
        evaluation = {}
        queries = self._ensure_original_query(query, list(plan.search_queries))

        for round_index in range(1, self.settings.max_search_rounds + 1):
            print(f"开始第 {round_index} 轮搜索资料...")
            search_results = self.searcher.search_many(queries)
            new_results = [item for item in search_results if item.url not in seen_result_urls]
            seen_result_urls.update(item.url for item in new_results)
            all_results.extend(new_results)
            print(f"本轮新增 {len(new_results)} 条网页结果，累计 {len(all_results)} 条。")

            print("开始抓取网页...")
            pages = self.crawler.crawl_many(new_results)
            new_pages = [item for item in pages if item["url"] not in seen_page_urls]
            seen_page_urls.update(item["url"] for item in new_pages)
            all_pages.extend(new_pages)
            print(f"本轮成功抓取 {len(new_pages)} 个网页正文，累计 {len(all_pages)} 个。")

            fallback_pages = self._snippet_fallback_pages(new_results, seen_page_urls | seen_snippet_urls)
            if fallback_pages:
                seen_snippet_urls.update(item["url"] for item in fallback_pages)
                snippet_candidates.extend(fallback_pages)
                print(f"暂存 {len(fallback_pages)} 个搜索摘要低置信候选。")

            print("开始批量评估检索质量...")
            evaluation = self.retrieval_evaluator.evaluate(query, plan, all_pages, round_index)
            accepted_count = len(evaluation.get("accepted_urls", []))
            print(f"检索评估：{evaluation.get('label')}；可用来源 {accepted_count} 个。")

            decision = self.action_router.route(evaluation, round_index)
            print(f"路由决策：{decision.action}。")
            if not decision.should_continue_search:
                break

            queries = self.query_planner.rewrite_queries(query, plan, evaluation, round_index)
            queries = self._ensure_original_query(query, queries)
            print(f"已生成 {len(queries)} 个补搜 query。")

        if self._should_use_snippet_fallback(evaluation) and snippet_candidates:
            print("完整网页证据不足，启用搜索摘要低置信 fallback...")
            all_pages.extend(snippet_candidates)
            evaluation = self.retrieval_evaluator.evaluate(query, plan, all_pages, self.settings.max_search_rounds)
            print(f"fallback 后检索评估：{evaluation.get('label')}；可用来源 {len(evaluation.get('accepted_urls', []))} 个。")

        print("开始证据精炼...")
        refined_pages = self.evidence_refiner.refine(all_pages, evaluation, query)
        print(f"保留 {len(refined_pages)} 个精炼后的证据来源。")

        print("开始总结来源...")
        summaries = self.summarizer.summarize_many(refined_pages)
        print(f"成功生成 {len(summaries)} 条来源摘要。")

        print("开始生成报告...")
        markdown = self.writer.write(query, plan.sub_questions, summaries)
        print("开始校验报告...")
        verification = self.verifier.verify(query, markdown, summaries)
        markdown = self.verifier.revise(markdown, verification, summaries)
        report_path = self.writer.save(markdown)
        print(f"报告已保存：{report_path}")
        return report_path

    def _should_use_snippet_fallback(self, evaluation: dict) -> bool:
        return (
            evaluation.get("label") != "correct"
            or len(evaluation.get("accepted_urls", [])) < self.settings.min_accepted_sources
        )

    def _snippet_fallback_pages(self, results: list[SearchResult], seen_urls: set[str]) -> list[dict]:
        pages = []
        for result in results:
            if result.url in seen_urls or not result.snippet:
                continue
            content = " ".join(part for part in [result.title, result.snippet] if part).strip()
            if len(content) < 20:
                continue
            pages.append(
                {
                    "title": result.title,
                    "url": result.url,
                    "content": content,
                    "query": result.query,
                    "snippet": result.snippet,
                    "provider": result.provider,
                    "mode": result.mode,
                    "purpose": result.purpose,
                    "content_source": "search_snippet",
                }
            )
        return pages

    def _ensure_original_query(self, query: str, queries: list[PlannedQuery]) -> list[PlannedQuery]:
        normalized_query = " ".join(query.split()).lower()
        for planned in queries:
            if " ".join(planned.query.split()).lower() == normalized_query:
                return queries
        return [
            *queries,
            PlannedQuery(query=query, mode="broad", purpose="保留原始问题检索，避免规划 query 漏掉用户真实意图"),
        ]
