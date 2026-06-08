"""Agent 集成测试 — 多轮 Mock 对话

审核人: Trump
审核日期: 2026-06-07
审核状态: [已通过]
"""

import pytest

from src.agent.agent import Agent
from src.agent.types import AgentTool
from src.llm.models import LLMResponse, ToolCall


class MockLLM:
    """支持多轮对话的 Mock LLM"""

    def __init__(self, turns: list[list[LLMResponse]]):
        self._turns = turns
        self._idx = 0

    async def stream(self, messages, tools=None):
        if self._idx < len(self._turns):
            for r in self._turns[self._idx]:
                yield r
            self._idx += 1


class MockRegistry:
    def __init__(self, results: dict[str, str] | None = None):
        self._results = results or {}
        self._calls = []

    async def execute(self, name: str, args: dict) -> str:
        self._calls.append((name, args))
        return self._results.get(name, f"result of {name}")


class TestMultiTurn:
    @pytest.mark.asyncio
    async def test_two_turn_dialog(self):
        """两轮对话：消息累积、事件触发次数正确"""
        agent = Agent(
            llm=MockLLM([
                [LLMResponse(text="第一轮回复", finish_reason="stop")],
                [LLMResponse(text="第二轮回复", finish_reason="stop")],
            ]),
            tool_registry=MockRegistry(),
        )

        events_count = []
        agent.subscribe(lambda e: events_count.append(e))

        # 第一轮
        chunks1 = [c async for c in agent.prompt("第一问")]
        assert chunks1 == ["第一轮回复"]
        assert agent.state.messages[-1].content == "第一轮回复"

        # 第二轮
        chunks2 = [c async for c in agent.prompt("第二问")]
        assert chunks2 == ["第二轮回复"]
        assert agent.state.messages[-1].content == "第二轮回复"

        # 消息累积
        roles = [m.role for m in agent.state.messages]
        assert roles == ["user", "assistant", "user", "assistant"]

        # 事件触发数量：每轮 prompt 至少一对 AgentStart/AgentEnd
        assert len(events_count) >= 4

    @pytest.mark.asyncio
    async def test_tool_call_chain(self):
        """LLM → tool_call → 结果喂回 → 最终文本"""
        agent = Agent(
            llm=MockLLM([
                [
                    LLMResponse(
                        tool_calls=[ToolCall(id="c1", name="search", arguments={"q": "test"})],
                        is_tool_call=True,
                        finish_reason="tool_calls",
                    ),
                ],
                [LLMResponse(text="搜索结果：找到 3 条", finish_reason="stop")],
            ]),
            tool_registry=MockRegistry({"search": "found 3 results"}),
            tools=[AgentTool(name="search", label="Search", description="搜索", parameters={})],
        )

        chunks = [c async for c in agent.prompt("搜索 test")]
        assert "搜索结果：找到 3 条" in chunks

        # 验证 tool result 消息在 messages 中
        tool_msgs = [m for m in agent.state.messages if m.role == "tool"]
        assert len(tool_msgs) == 1
        assert tool_msgs[0].tool_call_id == "c1"

    @pytest.mark.asyncio
    async def test_reset_between_dialogs(self):
        """reset() 后新对话，状态隔离"""
        agent = Agent(
            llm=MockLLM([
                [LLMResponse(text="旧对话", finish_reason="stop")],
                [LLMResponse(text="新对话", finish_reason="stop")],
            ]),
            tool_registry=MockRegistry(),
        )

        async for _ in agent.prompt("旧问"):
            pass
        assert len(agent.state.messages) == 2

        agent.reset()
        assert agent.state.messages == []

        async for _ in agent.prompt("新问"):
            pass
        assert len(agent.state.messages) == 2
        assert agent.state.messages[0].role == "user"
        assert agent.state.messages[1].content == "新对话"
