from __future__ import annotations

from config import load_settings
from crawler import Crawler
from llm_client import LLMClient
from planner import Planner
from searcher import Searcher
from summarizer import Summarizer
from writer import Writer


class ResearchAgent:
    def __init__(self) -> None:
        self.settings = load_settings(require_api_key=True)
        self.llm = LLMClient(self.settings)
        self.planner = Planner(self.llm, self.settings)
        self.searcher = Searcher(self.settings)
        self.crawler = Crawler(self.settings)
        self.summarizer = Summarizer(self.llm)
        self.writer = Writer(self.llm)

    def run(self, query: str) -> str:
        print("开始规划研究问题...")
        sub_questions = self.planner.plan(query)
        print(f"已生成 {len(sub_questions)} 个子问题。")

        print("开始搜索资料...")
        search_results = self.searcher.search_many(sub_questions)
        print(f"搜索到 {len(search_results)} 条去重后的网页结果。")

        print("开始抓取网页...")
        pages = self.crawler.crawl_many(search_results)
        print(f"成功抓取 {len(pages)} 个网页正文。")

        print("开始总结来源...")
        summaries = self.summarizer.summarize_many(pages)
        print(f"成功生成 {len(summaries)} 条来源摘要。")

        print("开始生成报告...")
        markdown = self.writer.write(query, sub_questions, summaries)
        report_path = self.writer.save(markdown)
        print(f"报告已保存：{report_path}")
        return report_path
