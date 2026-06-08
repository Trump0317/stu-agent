"""Skill 系统集成测试 — MockLLM 端到端

验证 Skill 加载 → Agent 创建 → AgentSession 运行 的完整链路。

审核人: [待审核]
审核日期: 2026-06-08
审核状态: [待审核]
"""

import pytest

from src.agent.agent import Agent
from src.agent.session import AgentSession
from src.agent.types import AgentTool
from src.llm.models import LLMResponse, ToolCall
from src.tools.registry import ToolRegistry


class MockLLM:
    """Mock LLM: 预置响应序列，记录 stream() 调用参数"""

    def __init__(self, responses: list[LLMResponse]):
        self._responses = responses
        self._idx = 0
        self.stream_calls: list[tuple] = []

    async def stream(self, messages, tools=None):
        self.stream_calls.append((list(messages), tools))
        if self._idx < len(self._responses):
            yield self._responses[self._idx]
            self._idx += 1


def _to_tool_call(name: str, args: dict | None = None, call_id: str = "c1") -> ToolCall:
    return ToolCall(id=call_id, name=name, arguments=args or {})


# ============================================================
# Helpers: 创建临时 Skill
# ============================================================

def _make_skill(tmp_path, name="test-skill", body="你是测试助手，请用中文回复。"):
    """在 tmp_path 中创建一个临时 skill"""
    (tmp_path / name).mkdir()
    (tmp_path / name / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: 测试用\n---\n{body}\n",
        encoding="utf-8",
    )


def _make_session_from_skill(tmp_path, skill_name, llm, model=""):
    """从临时 skill 创建 AgentSession"""
    import src.skills as skills_mod
    from src.skills import create_agent_from_skill

    original = skills_mod.SKILLS_DIR
    try:
        skills_mod.SKILLS_DIR = tmp_path
        agent, registry = create_agent_from_skill(skill_name, llm, model)
        return AgentSession(agent=agent, llm=llm, tool_registry=registry)
    finally:
        skills_mod.SKILLS_DIR = original


# ============================================================
# 集成测试
# ============================================================

class TestSkillIntegration:
    """Skill → Agent → AgentSession 端到端"""

    @pytest.mark.asyncio
    async def test_skill_agent_creates_session(self, tmp_path):
        """从 Skill 创建 AgentSession，验证基础属性"""
        _make_skill(tmp_path)
        llm = MockLLM([LLMResponse(text="你好！", finish_reason="stop")])

        import src.skills as skills_mod
        from src.skills import create_agent_from_skill

        original = skills_mod.SKILLS_DIR
        try:
            skills_mod.SKILLS_DIR = tmp_path
            agent, registry = create_agent_from_skill("test-skill", llm)

            session = AgentSession(agent=agent, llm=llm, tool_registry=registry)
            assert session.agent is agent
            assert session._tool_registry is registry
            assert session._tool_registry.list_tools() == [
                "read_file", "write_file", "bash"
            ]
        finally:
            skills_mod.SKILLS_DIR = original

    @pytest.mark.asyncio
    async def test_skill_system_prompt_in_agent_state(self, tmp_path):
        """Skill 的 system_prompt 存储在 Agent.state 中"""
        body = "你是测试助手，擅长回答 Python 问题。"
        _make_skill(tmp_path, body=body)
        llm = MockLLM([LLMResponse(text="好的", finish_reason="stop")])

        session = _make_session_from_skill(tmp_path, "test-skill", llm)

        # system_prompt 在 Agent 状态中
        assert "测试助手" in session.agent.state.system_prompt
        assert "Python" in session.agent.state.system_prompt

        # 可以正常运行
        chunks = [c async for c in session.run("hello")]
        assert len(chunks) > 0

    @pytest.mark.asyncio
    async def test_skill_tools_registered_in_llm_call(self, tmp_path):
        """Skill 创建 Agent 后，LLM 调用带有完整的工具 schema"""
        _make_skill(tmp_path)
        llm = MockLLM([LLMResponse(text="ok", finish_reason="stop")])

        session = _make_session_from_skill(tmp_path, "test-skill", llm)

        chunks = [c async for c in session.run("hello")]
        assert len(chunks) > 0

        # 验证 LLM 收到的 tools 参数
        tools = llm.stream_calls[0][1]
        assert tools is not None
        tool_names = [t["function"]["name"] for t in tools]
        assert "read_file" in tool_names
        assert "write_file" in tool_names
        assert "bash" in tool_names

    @pytest.mark.asyncio
    async def test_skill_tool_call_execution(self, tmp_path):
        """Skill Agent 中 LLM 调用工具 → 真实执行 → 返回结果"""
        _make_skill(tmp_path)
        llm = MockLLM([
            LLMResponse(
                tool_calls=[
                    _to_tool_call("read_file", {"path": "config/settings.yaml"}),
                ],
                is_tool_call=True,
                finish_reason="tool_calls",
            ),
            LLMResponse(text="配置读取完毕", finish_reason="stop"),
        ])

        session = _make_session_from_skill(tmp_path, "test-skill", llm)

        tool_results = []
        session.on_tool_result = lambda e: tool_results.append(e)

        chunks = [c async for c in session.run("读配置")]
        assert len(chunks) > 0
        assert len(tool_results) == 1
        assert tool_results[0].is_error is False
        assert "deepseek" in tool_results[0].result.content[0].lower()

    @pytest.mark.asyncio
    async def test_skill_custom_script_via_bash(self, tmp_path):
        """Skill 自定义脚本通过 bash 工具执行（不注册为独立 Tool）"""
        _make_skill(tmp_path)
        # LLM 调用 bash 执行 echo（模拟自定义脚本调用）
        llm = MockLLM([
            LLMResponse(
                tool_calls=[
                    _to_tool_call("bash", {"command": "echo hello-from-script"}),
                ],
                is_tool_call=True,
                finish_reason="tool_calls",
            ),
            LLMResponse(text="脚本执行成功", finish_reason="stop"),
        ])

        session = _make_session_from_skill(tmp_path, "test-skill", llm)

        tool_results = []
        session.on_tool_result = lambda e: tool_results.append(e)

        chunks = [c async for c in session.run("执行脚本")]
        assert len(chunks) > 0
        assert len(tool_results) == 1
        assert tool_results[0].tool_name == "bash"
        assert "hello-from-script" in tool_results[0].result.content[0]

        # 确认没有叫 "format" 的工具
        assert "format" not in session._tool_registry.list_tools()

    @pytest.mark.asyncio
    async def test_two_skills_different_prompts(self, tmp_path):
        """两个 Skill 的 system_prompt 不同"""
        # Skill A
        _make_skill(tmp_path, name="skill-a", body="你是翻译助手。")
        # Skill B
        _make_skill(tmp_path, name="skill-b", body="你是代码助手。")

        import src.skills as skills_mod
        from src.skills import create_agent_from_skill

        original = skills_mod.SKILLS_DIR
        try:
            skills_mod.SKILLS_DIR = tmp_path

            llm_a = MockLLM([LLMResponse(text="translation", finish_reason="stop")])
            agent_a, _ = create_agent_from_skill("skill-a", llm_a)

            llm_b = MockLLM([LLMResponse(text="code", finish_reason="stop")])
            agent_b, _ = create_agent_from_skill("skill-b", llm_b)

            sys_a = agent_a.state.system_prompt
            sys_b = agent_b.state.system_prompt

            assert "翻译" in sys_a
            assert "代码" in sys_b
            assert sys_a != sys_b
        finally:
            skills_mod.SKILLS_DIR = original


class TestSkillEventCallbacks:
    """Skill Agent 事件回调集成测试"""

    @pytest.mark.asyncio
    async def test_callbacks_with_skill_agent(self, tmp_path):
        """Skill Agent 的 AgentSession 回调正常工作"""
        _make_skill(tmp_path)
        llm = MockLLM([
            LLMResponse(
                tool_calls=[
                    _to_tool_call("bash", {"command": "echo test"}),
                ],
                is_tool_call=True,
                finish_reason="tool_calls",
            ),
            LLMResponse(text="done", finish_reason="stop"),
        ])

        session = _make_session_from_skill(tmp_path, "test-skill", llm)

        turn_starts = []
        turn_ends = []
        tool_starts = []
        tool_ends = []
        chunks = []

        session.on_turn_start = lambda n: turn_starts.append(n)
        session.on_turn_end = lambda n, msg, results: turn_ends.append(n)
        session.on_tool_call = lambda e: tool_starts.append(e.tool_name)
        session.on_tool_result = lambda e: tool_ends.append(e.tool_name)
        session.on_chunk = lambda c: chunks.append(c)

        result = [c async for c in session.run("test")]

        assert len(turn_starts) == 1
        assert turn_starts[0] >= 1
        assert len(turn_ends) == 1
        assert tool_starts == ["bash"]
        assert tool_ends == ["bash"]
        assert len(chunks) > 0 or len(result) > 0

    @pytest.mark.asyncio
    async def test_agent_messages_updated_after_run(self, tmp_path):
        """Skill Agent 的 state.messages 在 run 后正确更新"""
        _make_skill(tmp_path)
        llm = MockLLM([LLMResponse(text="你好！", finish_reason="stop")])

        session = _make_session_from_skill(tmp_path, "test-skill", llm)

        [c async for c in session.run("用户问题")]

        messages = session.agent.state.messages
        assert len(messages) >= 2  # user + assistant at minimum
        assert messages[0].role == "user"
        assert messages[0].content == "用户问题"
        assert messages[-1].role == "assistant"
