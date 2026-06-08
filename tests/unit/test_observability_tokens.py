"""LLM Token 用量透传测试

审核人: 待填写
审核日期: 2026-06-07
审核状态: [待审核]
"""

import io
import json
import pytest

from src.agent.agent import Agent
from src.agent.events import TurnEnd
from src.llm.models import LLMResponse
from src.observability.config import ObservabilityConfig
from src.observability.observer import AgentObserver


class MockLLM:
    def __init__(self, responses):
        self._responses = responses
        self._idx = 0

    async def stream(self, messages, tools=None):
        if self._idx < len(self._responses):
            r = self._responses[self._idx]
            self._idx += 1
            yield r


class MockRegistry:
    async def execute(self, name, args):
        return f"result of {name}"


def _last_turn_event(events):
    """从 observer 输出中提取最后一个 TurnEnd 事件"""
    lines = [json.loads(l) for l in events.getvalue().strip().split("\n")]
    for line in reversed(lines):
        if line["event"] == "turn_end":
            return line
    return None


class TestTokenUsageInObserver:
    @pytest.mark.asyncio
    async def test_usage_in_turn_end(self):
        """LLM 返回 usage 时，TurnEnd 日志包含 token 用量"""
        usage = {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
        config = ObservabilityConfig(log_format="json")
        buf = io.StringIO()

        llm = MockLLM([LLMResponse(text="hi", finish_reason="stop", usage=usage)])
        agent = Agent(llm=llm, tool_registry=MockRegistry())
        obs = AgentObserver(agent, config, buf)

        async for _ in agent.prompt("hello"):
            pass

        turn_end = _last_turn_event(buf)
        assert turn_end is not None
        assert "usage" in turn_end
        assert turn_end["usage"]["prompt_tokens"] == 100
        assert turn_end["usage"]["completion_tokens"] == 50
        assert turn_end["usage"]["total_tokens"] == 150

    @pytest.mark.asyncio
    async def test_no_usage_when_not_provided(self):
        """LLM 不返回 usage 时，日志不含 usage 字段"""
        config = ObservabilityConfig(log_format="json")
        buf = io.StringIO()

        llm = MockLLM([LLMResponse(text="hi", finish_reason="stop")])
        agent = Agent(llm=llm, tool_registry=MockRegistry())
        obs = AgentObserver(agent, config, buf)

        async for _ in agent.prompt("hello"):
            pass

        turn_end = _last_turn_event(buf)
        assert turn_end is not None
        assert turn_end.get("usage") is None
