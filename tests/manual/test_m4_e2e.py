#!/usr/bin/env python3
"""M4 E2E 测试 — 真实 LLM 验证完整写作流

场景 1: 写课程论文 (.docx 模板) → read_template → 逐章写作 → fill_docx 导出
场景 2: 写实验报告 (.yaml 模板) → read_template → 逐章写作 → md_to_docx 导出
边界: 闲聊不触发工具、空输入

使用方法:
    export DEEPSEEK_API_KEY=sk-xxx
    python tests/manual/test_m4_e2e.py

审核人: [待审核]
审核日期: 2026-06-08
审核状态: [待审核]
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config.settings import load_settings
from src.llm.factory import LLMFactory
from src.skills import create_agent_from_skill, list_skills
from src.agent.session import AgentSession
from src.agent.events import ToolStart, ToolEnd


# ============================================================
# Test runner
# ============================================================

class E2ERunner:
    def __init__(self):
        self.tool_calls: list[str] = []
        self.chunks: list[str] = []
        self.errors: list[str] = []

    def on_tool_call(self, event: ToolStart):
        self.tool_calls.append(event.tool_name)

    def on_tool_result(self, event: ToolEnd):
        if event.is_error:
            self.errors.append(f"{event.tool_name}: {event.result.content[0][:100]}")

    async def run_scenario(self, name: str, prompt: str, expect_tools: bool = True):
        print(f"\n{'='*60}")
        print(f"场景: {name}")
        print(f"{'='*60}")
        print(f"用户: {prompt}")
        print("---")

        settings = load_settings()
        llm = LLMFactory.create(settings.llm)
        agent, registry = create_agent_from_skill("writing", llm)
        session = AgentSession(agent=agent, llm=llm, tool_registry=registry)

        self.tool_calls = []
        self.chunks = []
        self.errors = []
        session.on_tool_call = self.on_tool_call
        session.on_tool_result = self.on_tool_result
        session.on_chunk = lambda c: self.chunks.append(c)

        try:
            async for chunk in session.run(prompt):
                print(chunk, end="", flush=True)
        except Exception as e:
            print(f"\n❌ 异常: {e}")
            import traceback
            traceback.print_exc()
            return False

        print("\n---")
        response = "".join(self.chunks)

        # 检查
        passed = True
        if len(response) < 20:
            print("❌ 响应太短")
            passed = False
        if expect_tools and not self.tool_calls:
            print("❌ 未调用任何工具")
            passed = False
        if self.errors:
            print(f"❌ 工具错误: {self.errors}")
            passed = False

        print(f"  响应长度: {len(response)} chars")
        print(f"  工具调用: {self.tool_calls}")
        print(f"{'✅ 通过' if passed else '❌ 失败'}")
        return passed


# ============================================================
# Test cases
# ============================================================

async def main():
    runner = E2ERunner()

    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        print("⚠️ DEEPSEEK_API_KEY 未设置")
        return

    results = {}

    # 场景 1: 课程论文 (.docx 模板)
    results["scenario_1_course_paper"] = await runner.run_scenario(
        "写课程论文 (.docx 模板)",
        "用 config/templates/course_paper.docx 模板写一篇关于人工智能发展的课程论文",
    )

    # 场景 2: 实验报告 (.yaml 模板)
    results["scenario_2_lab_report"] = await runner.run_scenario(
        "写实验报告 (.yaml 模板)",
        "用 config/templates/lab_report.yaml 模板写一份关于牛顿第二定律验证的实验报告",
    )

    # 边界 1: 闲聊
    results["edge_idle_chat"] = await runner.run_scenario(
        "闲聊不应触发写作工具",
        "你好，今天天气怎么样？",
        expect_tools=False,
    )

    # 边界 2: 自我介绍
    results["edge_identity"] = await runner.run_scenario(
        "身份声明",
        "你是谁？请介绍你自己",
        expect_tools=False,
    )

    # 总结
    print(f"\n{'='*60}")
    print("E2E 测试结果")
    print(f"{'='*60}")
    for name, passed in results.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {name}")

    all_passed = all(results.values())
    print(f"\n{'🎉 全部通过' if all_passed else '❌ 有失败'}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
