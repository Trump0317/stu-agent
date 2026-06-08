"""agent_loop 纯函数 — 单元测试

审核人: Trump
审核日期: 2026-06-07
审核状态: [已通过]
"""

import pytest

from src.agent.events import (
    AgentEnd,
    AgentStart,
    BeforeAgentStart,
    MessageEnd,
    MessageStart,
    MessageUpdate,
    RetryEnd,
    RetryStart,
    ToolEnd,
    ToolStart,
    TurnEnd,
    TurnStart,
)
from src.agent.loop import agent_loop
from src.agent.types import AgentContext, AgentLoopConfig, AgentMessage
from src.llm.models import LLMResponse, ToolCall


# --- Mock 助手 ---

def _text_response(text: str, finish_reason: str = "stop"):
    async def stream(messages, tools=None):
        yield LLMResponse(text=text, finish_reason=finish_reason)

    return stream


def _multi_turn_stream(turns: list):
    """支持多轮 stream 调用：每轮返回一个 LLMResponse 列表"""
    idx = 0

    async def stream(messages, tools=None):
        nonlocal idx
        if idx < len(turns):
            for resp in turns[idx]:
                yield resp
            idx += 1

    return stream


class MockRegistry:
    def __init__(self, results: dict[str, str] | None = None):
        self._results = results or {}

    async def execute(self, name: str, args: dict) -> str:
        return self._results.get(name, f"result of {name}")


def _default_context():
    return AgentContext(
        system_prompt="You are helpful.",
        messages=[AgentMessage(role="system", content="You are helpful.")],
        tools=[{"type": "function", "function": {"name": "search", "parameters": {}}}],
    )


def _default_config(stream_fn):
    return AgentLoopConfig(
        model="test-model",
        stream_fn=stream_fn,
        convert_to_llm=lambda msgs: msgs,
        max_tool_rounds=5,
        max_retries=2,
    )


# --- 用例 ---

class TestAgentLoopText:
    @pytest.mark.asyncio
    async def test_pure_text_response(self):
        """纯文本响应 → 完整事件链"""
        context = _default_context()
        config = _default_config(_text_response("你好，有什么可以帮你的？"))

        events = [e async for e in agent_loop("帮我写论文", context, config, MockRegistry())]

        types = [type(e) for e in events]
        assert types == [
            BeforeAgentStart,
            AgentStart,
            TurnStart,
            MessageStart,
            MessageUpdate,
            MessageEnd,
            TurnEnd,
            AgentEnd,
        ]

    @pytest.mark.asyncio
    async def test_text_content_is_yielded(self):
        """文本增量通过 MessageUpdate.delta 传递"""
        context = _default_context()
        config = _default_config(_text_response("Hello"))

        events = [e async for e in agent_loop("hi", context, config, MockRegistry())]
        updates = [e for e in events if isinstance(e, MessageUpdate)]
        assert len(updates) == 1
        assert updates[0].delta == "Hello"
        assert updates[0].delta_type == "text_delta"


class TestAgentLoopToolCall:
    @pytest.mark.asyncio
    async def test_single_tool_call(self):
        """单工具调用 → ToolStart + ToolEnd 穿插在 MessageUpdate 之间"""
        context = _default_context()
        registry = MockRegistry({"search": "found 3 results"})
        config = _default_config(
            _multi_turn_stream([
                [LLMResponse(tool_calls=[ToolCall(id="c1", name="search", arguments={"q": "test"})],
                             is_tool_call=True, finish_reason="tool_calls")],
                [LLMResponse(text="搜索完成，找到 3 条结果", finish_reason="stop")],
            ])
        )

        events = [e async for e in agent_loop("search something", context, config,
                                                     registry)]
        tool_starts = [e for e in events if isinstance(e, ToolStart)]
        tool_ends = [e for e in events if isinstance(e, ToolEnd)]

        assert len(tool_starts) == 1
        assert len(tool_ends) == 1
        assert tool_starts[0].tool_name == "search"
        assert tool_ends[0].tool_name == "search"
        assert tool_ends[0].is_error is False

        # 验证事件顺序：ToolStart/ToolEnd 在 MessageUpdate 之前
        ts_idx = next(i for i, e in enumerate(events) if isinstance(e, ToolStart))
        te_idx = next(i for i, e in enumerate(events) if isinstance(e, ToolEnd))
        mu_idx = next(i for i, e in enumerate(events) if isinstance(e, MessageUpdate))
        assert ts_idx < te_idx < mu_idx


class TestAgentLoopBlockTool:
    @pytest.mark.asyncio
    async def test_before_tool_call_block(self):
        """before_tool_call hook 返回 block → 工具不执行，ToolEnd.is_error=True"""
        context = _default_context()
        registry = MockRegistry({"dangerous": "should not be called"})

        def before_hook(ctx):
            return {"block": True, "reason": "forbidden"}

        config = _default_config(
            _multi_turn_stream([
                [LLMResponse(tool_calls=[ToolCall(id="c1", name="dangerous", arguments={})],
                             is_tool_call=True, finish_reason="tool_calls")],
                [LLMResponse(text="操作被拦截", finish_reason="stop")],
            ])
        )
        config.before_tool_call = before_hook

        events = [e async for e in agent_loop("do dangerous", context, config,
                                                     registry)]
        tool_ends = [e for e in events if isinstance(e, ToolEnd)]
        assert len(tool_ends) == 1
        assert tool_ends[0].is_error is True
        assert "Blocked" in tool_ends[0].result.content[0]


class TestAgentLoopRetry:
    @pytest.mark.asyncio
    async def test_retry_on_stream_error(self):
        """stream_fn 抛异常 → 自动重试，emit RetryStart/RetryEnd"""

        call_count = 0

        async def failing_then_ok(messages, tools=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("timeout")
            yield LLMResponse(text="recovered", finish_reason="stop")

        context = _default_context()
        config = _default_config(failing_then_ok)

        events = [e async for e in agent_loop("test", context, config, MockRegistry())]

        retry_starts = [e for e in events if isinstance(e, RetryStart)]
        retry_ends = [e for e in events if isinstance(e, RetryEnd)]

        assert len(retry_starts) == 1
        assert len(retry_ends) == 1
        assert retry_starts[0].attempt == 1
        assert "timeout" in retry_starts[0].error

    @pytest.mark.asyncio
    async def test_retry_exhausted_raises(self):
        """重试耗尽后抛出异常，但 Retry 事件仍在抛异常前发出"""

        async def always_fail(messages, tools=None):
            raise RuntimeError("persistent error")
            yield  # 使其成为 async generator

        context = _default_context()
        config = _default_config(always_fail)
        config.max_retries = 1

        events = []
        with pytest.raises(RuntimeError, match="persistent error"):
            async for e in agent_loop("test", context, config, MockRegistry()):
                events.append(e)

        retry_starts = [e for e in events if isinstance(e, RetryStart)]
        assert len(retry_starts) >= 1
        assert "persistent error" in retry_starts[0].error


class TestAgentLoopMaxRounds:
    @pytest.mark.asyncio
    async def test_max_tool_rounds_exceeded(self):
        """持续返回 tool_call 超过 max_tool_rounds → 强制终止，以 AgentEnd 收尾"""
        tc = ToolCall(id="c1", name="search", arguments={"q": "x"})

        async def endless_tools(messages, tools=None):
            yield LLMResponse(tool_calls=[tc], is_tool_call=True, finish_reason="tool_calls")

        context = _default_context()
        config = _default_config(endless_tools)
        config.max_tool_rounds = 3

        events = [e async for e in agent_loop("test", context, config, MockRegistry())]
        tool_starts = [e for e in events if isinstance(e, ToolStart)]
        tool_ends = [e for e in events if isinstance(e, ToolEnd)]

        assert len(tool_starts) == 3
        assert len(tool_ends) == 3
        # 优雅终止
        assert isinstance(events[-1], AgentEnd)


class TestAgentLoopTokenUsage:
    @pytest.mark.asyncio
    async def test_turn_end_carries_usage(self):
        """LLM 返回 usage → TurnEnd.usage 被填充"""
        usage = {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}

        async def stream_with_usage(messages, tools=None):
            yield LLMResponse(text="ok", finish_reason="stop", usage=usage)

        context = _default_context()
        config = _default_config(stream_with_usage)
        events = [e async for e in agent_loop("test", context, config, MockRegistry())]
        turn_ends = [e for e in events if isinstance(e, TurnEnd)]
        assert len(turn_ends) == 1
        assert turn_ends[0].usage == usage

    @pytest.mark.asyncio
    async def test_turn_end_usage_none_when_not_provided(self):
        """LLM 不返回 usage → TurnEnd.usage 为 None"""
        context = _default_context()
        config = _default_config(_text_response("ok"))
        events = [e async for e in agent_loop("test", context, config, MockRegistry())]
        turn_ends = [e for e in events if isinstance(e, TurnEnd)]
        assert len(turn_ends) == 1
        assert turn_ends[0].usage is None
