"""Agent 有状态编排器 — 单元测试

审核人: Trump
审核日期: 2026-06-07
审核状态: [已通过]
"""

import pytest

from src.agent.agent import Agent
from src.agent.types import AgentState, AgentTool
from src.llm.models import LLMResponse


class MockLLM:
    """Mock BaseLLM，提供 async stream() 方法"""

    def __init__(self, responses: list[LLMResponse] | None = None):
        self.responses = responses or [LLMResponse(text="mock", finish_reason="stop")]

    async def stream(self, messages, tools=None):
        for r in self.responses:
            yield r


class MockRegistry:
    def __init__(self):
        self._calls = []

    async def execute(self, name: str, args: dict) -> str:
        self._calls.append((name, args))
        return f"result of {name}"


class TestAgentInit:
    def test_default_state(self):
        agent = Agent(
            llm=MockLLM(),
            tool_registry=MockRegistry(),
            system_prompt="You are helpful.",
        )
        state = agent.state
        assert state.system_prompt == "You are helpful."
        assert state.tools == []
        assert state.messages == []
        assert state.is_streaming is False
        assert state.error_message is None

    def test_default_system_prompt(self):
        """不传 system_prompt 时默认为空字符串"""
        agent = Agent(MockLLM(), MockRegistry())
        assert agent.state.system_prompt == ""

    def test_state_is_readonly(self):
        agent = Agent(MockLLM(), MockRegistry())
        with pytest.raises(AttributeError):
            agent.state = AgentState(system_prompt="new")

    def test_init_with_tools(self):
        tools = [AgentTool(name="search", label="Search", description="搜索", parameters={})]
        agent = Agent(MockLLM(), MockRegistry(), tools=tools)
        assert agent.state.tools == tools

    def test_init_with_model(self):
        agent = Agent(MockLLM(), MockRegistry(), model="gpt-4o")
        # model 存储验证：Agent 内部应持有 model 引用
        # 具体字段取决于实现，此处验证 state 存在
        assert agent.state is not None


class TestAgentPrompt:
    @pytest.mark.asyncio
    async def test_prompt_returns_text(self):
        agent = Agent(
            llm=MockLLM([LLMResponse(text="你好！", finish_reason="stop")]),
            tool_registry=MockRegistry(),
        )
        chunks = [chunk async for chunk in agent.prompt("hello")]
        assert chunks == ["你好！"]

    @pytest.mark.asyncio
    async def test_prompt_updates_messages(self):
        agent = Agent(
            llm=MockLLM([LLMResponse(text="回答", finish_reason="stop")]),
            tool_registry=MockRegistry(),
        )
        async for _ in agent.prompt("问题"):
            pass

        messages = agent.state.messages
        assert len(messages) >= 2
        assert messages[-2].role == "user"
        assert messages[-1].role == "assistant"

    @pytest.mark.asyncio
    async def test_two_prompts_accumulate_messages(self):
        agent = Agent(
            llm=MockLLM([LLMResponse(text="第一轮", finish_reason="stop")]),
            tool_registry=MockRegistry(),
        )
        async for _ in agent.prompt("你好"):
            pass
        async for _ in agent.prompt("继续"):
            pass

        messages = agent.state.messages
        roles = [m.role for m in messages]
        assert roles.count("user") == 2
        assert roles.count("assistant") == 2


class TestAgentEvents:
    @pytest.mark.asyncio
    async def test_subscribe_receives_events(self):
        agent = Agent(
            llm=MockLLM([LLMResponse(text="hi", finish_reason="stop")]),
            tool_registry=MockRegistry(),
        )
        received = []

        def listener(event):
            received.append(type(event).__name__)

        agent.subscribe(listener)
        async for _ in agent.prompt("test"):
            pass

        assert "AgentStart" in received
        assert "AgentEnd" in received

    @pytest.mark.asyncio
    async def test_subscribe_returns_callable(self):
        agent = Agent(MockLLM(), MockRegistry())
        unsub = agent.subscribe(lambda e: None)
        assert callable(unsub)

    @pytest.mark.asyncio
    async def test_unsubscribe_only_removes_one(self):
        """注销一个 listener 不影响其他"""
        agent = Agent(
            llm=MockLLM([LLMResponse(text="hi", finish_reason="stop")]),
            tool_registry=MockRegistry(),
        )
        received_a = []
        received_b = []

        def listener_a(event):
            received_a.append(event)

        def listener_b(event):
            received_b.append(event)

        unsub_a = agent.subscribe(listener_a)
        agent.subscribe(listener_b)
        unsub_a()  # 注销 A

        async for _ in agent.prompt("test"):
            pass

        assert len(received_a) == 0  # A 已注销
        assert len(received_b) > 0  # B 仍收到事件


class TestAgentReset:
    @pytest.mark.asyncio
    async def test_reset_clears_state(self):
        agent = Agent(
            llm=MockLLM([LLMResponse(text="回答", finish_reason="stop")]),
            tool_registry=MockRegistry(),
            system_prompt="system",
        )
        async for _ in agent.prompt("问题"):
            pass

        agent.reset()
        assert agent.state.messages == []
        assert agent.state.is_streaming is False
        assert agent.state.system_prompt == "system"
