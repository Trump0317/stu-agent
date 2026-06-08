"""AgentSession 事件驱动编排器 — 单元测试

审核人: Trump
审核日期: 2026-06-08
审核状态: [待审核]
"""

import pytest

from src.agent.agent import Agent
from src.agent.events import ToolStart, ToolEnd, TurnStart, TurnEnd
from src.agent.types import AgentTool
from src.llm.models import LLMResponse, ToolCall


class MockLLM:
    """Mock LLM，支持多轮工具调用。记录每次 stream() 的 messages 参数供验证。"""

    def __init__(self, responses: list[LLMResponse]):
        self._responses = responses
        self._idx = 0
        self.stream_calls: list[list[dict]] = []

    async def stream(self, messages, tools=None):
        self.stream_calls.append(messages)
        if self._idx < len(self._responses):
            yield self._responses[self._idx]
            self._idx += 1


class MockRegistry:
    def __init__(self, results: dict[str, str] | None = None):
        self._results = results or {}
        self.calls = []

    async def execute(self, name: str, args: dict) -> str:
        self.calls.append((name, args))
        return self._results.get(name, f"result of {name}")


def _make_agent(system_prompt="你是助手"):
    """创建最小 Agent 实例。传入的 llm/tool_registry 仅用于 Agent 构造，
    实际会话由 AgentSession 持有的 llm/tool_registry 驱动。"""
    return Agent(
        llm=MockLLM([]),
        tool_registry=MockRegistry(),
        system_prompt=system_prompt,
    )


class TestAgentSessionInit:
    def test_create_with_agent(self):
        """创建 AgentSession 并持有 Agent/LLM/ToolRegistry 引用"""
        from src.agent.session import AgentSession

        agent = _make_agent()
        llm = MockLLM([LLMResponse(text="hi", finish_reason="stop")])
        reg = MockRegistry()

        session = AgentSession(agent=agent, llm=llm, tool_registry=reg)
        assert session.agent is agent
        assert str(session)

    def test_callbacks_are_none_by_default(self):
        """所有回调默认为 None"""
        from src.agent.session import AgentSession

        agent = _make_agent()
        session = AgentSession(agent=agent, llm=MockLLM([]), tool_registry=MockRegistry())

        assert session.on_turn_start is None
        assert session.on_turn_end is None
        assert session.on_tool_call is None
        assert session.on_tool_result is None
        assert session.on_chunk is None

    def test_callbacks_can_be_set(self):
        """回调属性可赋值"""
        from src.agent.session import AgentSession

        session = AgentSession(agent=_make_agent(), llm=MockLLM([]), tool_registry=MockRegistry())

        def dummy(*args): pass

        session.on_turn_start = dummy
        session.on_turn_end = dummy
        session.on_tool_call = dummy
        session.on_tool_result = dummy
        session.on_chunk = dummy

        assert session.on_chunk is dummy


class TestAgentSessionRunText:
    @pytest.mark.asyncio
    async def test_run_returns_text(self):
        """run() 流式返回 LLM 文本"""
        from src.agent.session import AgentSession

        agent = _make_agent()
        llm = MockLLM([LLMResponse(text="你好，有什么可以帮你的？", finish_reason="stop")])
        session = AgentSession(agent=agent, llm=llm, tool_registry=MockRegistry())

        chunks = [c async for c in session.run("你好")]
        assert "".join(chunks) == "你好，有什么可以帮你的？"

    @pytest.mark.asyncio
    async def test_run_accumulates_messages(self):
        """run() 后 agent.messages 正确累积"""
        from src.agent.session import AgentSession

        agent = _make_agent()
        llm = MockLLM([LLMResponse(text="回复", finish_reason="stop")])
        session = AgentSession(agent=agent, llm=llm, tool_registry=MockRegistry())

        async for _ in session.run("问题"):
            pass

        messages = agent.state.messages
        roles = [m.role for m in messages]
        assert "user" in roles
        assert "assistant" in roles

    @pytest.mark.asyncio
    async def test_multiple_runs_context_passing(self):
        """第二轮 LLM 调用收到第一轮的对话历史"""
        from src.agent.session import AgentSession

        agent = _make_agent()
        llm = MockLLM([
            LLMResponse(text="第一轮回复", finish_reason="stop"),
            LLMResponse(text="第二轮回复", finish_reason="stop"),
        ])
        session = AgentSession(agent=agent, llm=llm, tool_registry=MockRegistry())

        async for _ in session.run("q1"):
            pass
        async for _ in session.run("q2"):
            pass

        # 验证消息累积
        user_count = sum(1 for m in agent.state.messages if m.role == "user")
        assistant_count = sum(1 for m in agent.state.messages if m.role == "assistant")
        assert user_count == 2
        assert assistant_count == 2

        # 第二轮 LLM 调用收到了包含第一轮内容的 messages
        assert len(llm.stream_calls) == 2, f"LLM 应被调用 2 次，实际 {len(llm.stream_calls)} 次"
        # 第二轮 messages 应至少有 user:q1 + assistant:第一轮 + user:q2 = 3 条
        assert len(llm.stream_calls[1]) >= 3


class TestAgentSessionCallbacks:
    @pytest.mark.asyncio
    async def test_turn_start_callback_fires(self):
        """on_turn_start 接收 turn 编号"""
        from src.agent.session import AgentSession

        agent = _make_agent()
        llm = MockLLM([LLMResponse(text="ok", finish_reason="stop")])
        session = AgentSession(agent=agent, llm=llm, tool_registry=MockRegistry())

        received = []
        session.on_turn_start = lambda turn: received.append(turn)

        async for _ in session.run("hello"):
            pass

        assert received == [1]

    @pytest.mark.asyncio
    async def test_turn_end_callback_fires(self):
        """on_turn_end 接收 turn + message + tool_results"""
        from src.agent.session import AgentSession

        agent = _make_agent()
        llm = MockLLM([LLMResponse(text="ok", finish_reason="stop")])
        session = AgentSession(agent=agent, llm=llm, tool_registry=MockRegistry())

        received = []
        session.on_turn_end = lambda turn, message, results: received.append(turn)

        async for _ in session.run("hello"):
            pass

        assert received == [1]

    @pytest.mark.asyncio
    async def test_tool_callbacks_fire_with_event_objects(self):
        """工具调用时回调接收完整事件对象（对齐 agent_loop yield）"""
        from src.agent.session import AgentSession

        agent = Agent(
            llm=MockLLM([]),
            tool_registry=MockRegistry(),
            system_prompt="你是助手",
        )
        reg = MockRegistry({"search": "found results"})
        llm = MockLLM([
            LLMResponse(
                tool_calls=[ToolCall(id="c1", name="search", arguments={"q": "test"})],
                is_tool_call=True,
                finish_reason="tool_calls",
            ),
            LLMResponse(text="搜索完成", finish_reason="stop"),
        ])
        # 注入 tools 到 agent state
        agent.state.tools = [AgentTool(name="search", label="search", description="搜索", parameters={})]

        session = AgentSession(agent=agent, llm=llm, tool_registry=reg)

        tool_starts = []
        tool_ends = []
        session.on_tool_call = lambda event: tool_starts.append(event.tool_name)
        session.on_tool_result = lambda event: tool_ends.append((event.tool_name, event.is_error))

        async for _ in session.run("搜索 test"):
            pass

        assert "search" in tool_starts
        assert len(tool_ends) == 1
        assert tool_ends[0] == ("search", False)

    @pytest.mark.asyncio
    async def test_on_chunk_callback(self):
        """on_chunk 回调接收流式文本增量"""
        from src.agent.session import AgentSession

        agent = _make_agent()
        llm = MockLLM([LLMResponse(text="你好世界", finish_reason="stop")])
        session = AgentSession(agent=agent, llm=llm, tool_registry=MockRegistry())

        chunks = []
        session.on_chunk = lambda text: chunks.append(text)

        async for _ in session.run("hello"):
            pass

        assert "你好世界" in "".join(chunks)


class TestAgentSessionEdgeCases:
    @pytest.mark.asyncio
    async def test_empty_input(self):
        """空输入不崩溃"""
        from src.agent.session import AgentSession

        agent = _make_agent()
        llm = MockLLM([LLMResponse(text="请问有什么可以帮你？", finish_reason="stop")])
        session = AgentSession(agent=agent, llm=llm, tool_registry=MockRegistry())

        chunks = [c async for c in session.run("")]
        assert len("".join(chunks)) > 0

    @pytest.mark.asyncio
    async def test_llm_exception_graceful(self):
        """LLM 抛异常时 Session 不崩溃，传播异常"""
        from src.agent.session import AgentSession

        agent = _make_agent()

        async def failing_stream(messages, tools=None):
            raise RuntimeError("LLM connection failed")
            yield  # 使其成为 async generator

        # 用自定义 stream 包装
        class FailingLLM:
            async def stream(self, messages, tools=None):
                raise RuntimeError("LLM connection failed")
                yield

        session = AgentSession(agent=agent, llm=FailingLLM(), tool_registry=MockRegistry())

        with pytest.raises(RuntimeError, match="LLM connection failed"):
            async for _ in session.run("test"):
                pass

    @pytest.mark.asyncio
    async def test_max_tool_rounds_enforced(self):
        """max_tool_rounds 到达后停止，不无限循环"""
        from src.agent.session import AgentSession

        agent = Agent(
            llm=MockLLM([]),
            tool_registry=MockRegistry(),
            system_prompt="你是助手",
        )
        reg = MockRegistry({"search": "result"})

        async def endless_tools(self, messages, tools=None):
            yield LLMResponse(
                tool_calls=[ToolCall(id="c1", name="search", arguments={"q": "x"})],
                is_tool_call=True,
                finish_reason="tool_calls",
            )

        agent.state.tools = [AgentTool(name="search", label="search", description="搜索", parameters={})]
        session = AgentSession(agent=agent, llm=MockLLM([]), tool_registry=reg)
        # 注入自定义 stream 绕过 MockLLM
        session._llm = type("LLM", (), {"stream": endless_tools})()

        tool_count = [0]
        session.on_tool_call = lambda e: tool_count.__setitem__(0, tool_count[0] + 1)

        async for _ in session.run("search"):
            pass

        # 默认 max_tool_rounds=5
        assert tool_count[0] <= 5
        assert tool_count[0] >= 1
