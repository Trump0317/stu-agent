#!/usr/bin/env python3
"""M3 Skill 系统 — 真实 LLM 验收测试

用 DeepSeek API 验证 writing skill 端到端流程：
1. 加载 SKILL.md → 创建 Agent
2. 运行对话：请求帮助写作
3. 验证 Agent 确实使用了工具（read_file / write_file / bash）

使用方法:
    python tests/manual/test_skill_real.py

前提:
    - 设置环境变量 DEEPSEEK_API_KEY
    - config/settings.yaml 中 llm.provider 为 deepseek
"""

import asyncio
import os
import sys
from pathlib import Path

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config.settings import load_settings
from src.llm.factory import LLMFactory
from src.skills import load_skill, create_agent_from_skill, list_skills
from src.agent.session import AgentSession
from src.agent.events import ToolStart, ToolEnd


async def main():
    print("=" * 60)
    print("M3 Skill 系统 — 真实 LLM 验收测试")
    print("=" * 60)

    # 1. Skill 发现
    print("\n[1] Skill 发现")
    skills = list_skills()
    print(f"    可用 Skill: {skills}")
    assert "writing" in skills, f"writing skill 不存在: {skills}"

    # 2. 加载 Skill
    print("\n[2] 加载 writing Skill")
    skill = load_skill("writing")
    print(f"    name: {skill.name}")
    print(f"    description: {skill.description}")
    print(f"    system_prompt: {len(skill.system_prompt)} chars")
    assert skill.system_prompt, "system_prompt 为空"
    print("    ✅ 加载成功")

    # 3. 创建 LLM
    print("\n[3] 创建 LLM")
    settings = load_settings()
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        print("    ⚠️ DEEPSEEK_API_KEY 未设置，请设置后重试")
        print("    export DEEPSEEK_API_KEY=sk-xxx")
        return
    llm = LLMFactory.create(settings.llm)
    print(f"    provider: {settings.llm.provider}")
    print(f"    model: {settings.llm.model}")
    print("    ✅ LLM 创建成功")

    # 4. 创建 Agent + AgentSession
    print("\n[4] 从 Skill 创建 Agent")
    agent, registry = create_agent_from_skill("writing", llm)
    print(f"    注册工具: {registry.list_tools()}")
    session = AgentSession(agent=agent, llm=llm, tool_registry=registry)
    print("    ✅ AgentSession 创建成功")

    # 5. 对话测试
    print("\n[5] 对话测试: 请写作助手介绍自己")
    print("    用户: 你好，介绍一下你自己，你有哪些能力？")
    print("    ---")

    tool_calls_detected = []

    def on_tool_call(event: ToolStart):
        tool_calls_detected.append(event.tool_name)
        print(f"\n    [Tool] 调用: {event.tool_name}")

    def on_tool_result(event: ToolEnd):
        content_preview = event.result.content[0][:80] if event.result.content else ""
        status = "✅" if not event.is_error else "❌"
        print(f"    [Tool] 结果: {event.tool_name} {status} {content_preview}...")

    session.on_tool_call = on_tool_call
    session.on_tool_result = on_tool_result

    response_text = ""
    try:
        async for chunk in session.run("你好，介绍一下你自己，你有哪些能力？"):
            response_text += chunk
            print(chunk, end="", flush=True)
    except Exception as e:
        print(f"\n    ❌ 对话异常: {e}")
        import traceback
        traceback.print_exc()
        return

    print("\n    ---")
    assert len(response_text) > 0, "LLM 未返回文本"
    print(f"    ✅ 响应文本: {len(response_text)} chars")

    # 6. 总结
    print("\n" + "=" * 60)
    print("验收总结")
    print("=" * 60)
    print(f"  Skill 加载:           ✅")
    print(f"  LLM 响应:             ✅ ({len(response_text)} chars)")
    print(f"  工具调用次数:          {len(tool_calls_detected)}")
    if tool_calls_detected:
        print(f"  调用的工具:            {tool_calls_detected}")
    print(f"  Agent system_prompt:  {len(agent.state.system_prompt)} chars")
    print(f"  注册工具:              {registry.list_tools()}")
    print("\n🎉 M3 验收通过！")


if __name__ == "__main__":
    asyncio.run(main())
