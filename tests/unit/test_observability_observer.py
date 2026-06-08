"""AgentObserver 单元测试

审核人: Trump
审核日期: 2026-06-07
审核状态: [已通过]
"""

import io
import json
import pytest

from src.agent.agent import Agent
from src.agent.events import (
    AgentEnd,
    AgentStart,
    BeforeAgentStart,
    MessageUpdate,
    RetryStart,
    RetryEnd,
    ToolEnd,
    ToolStart,
    TurnEnd,
    TurnStart,
)
from src.agent.types import AgentMessage, AgentToolResult
from src.llm.models import LLMResponse
from src.observability.config import ObservabilityConfig
from src.observability.observer import AgentObserver


class MockLLM:
    def __init__(self, responses=None):
        self._responses = responses or [LLMResponse(text="hi", finish_reason="stop")]
        self._idx = 0

    async def stream(self, messages, tools=None):
        if self._idx < len(self._responses):
            r = self._responses[self._idx]
            self._idx += 1
            yield r


class MockRegistry:
    async def execute(self, name, args):
        return f"result of {name}"


class TestAgentObserver:
    @pytest.mark.asyncio
    async def test_json_output_is_valid_and_run_id_consistent(self):
        """json 格式输出每行可被 json.loads 解析，且同次 prompt 共享 run_id"""
        buf = io.StringIO()
        config = ObservabilityConfig(log_format="json", log_file=None)
        agent = Agent(llm=MockLLM(), tool_registry=MockRegistry())
        observer = AgentObserver(agent, config, output=buf)

        async for _ in agent.prompt("hello"):
            pass

        lines = buf.getvalue().strip().split("\n")
        assert len(lines) > 0
        run_ids = set()
        for line in lines:
            obj = json.loads(line)
            assert "event" in obj
            assert "ts" in obj
            assert "run_id" in obj
            run_ids.add(obj["run_id"])
        assert len(run_ids) == 1  # 同次调用共享 run_id

    @pytest.mark.asyncio
    async def test_text_output_contains_keywords(self):
        """text 格式输出含关键字段和用户输入"""
        buf = io.StringIO()
        config = ObservabilityConfig(log_format="text", log_file=None)
        agent = Agent(llm=MockLLM(), tool_registry=MockRegistry())
        observer = AgentObserver(agent, config, output=buf)

        async for _ in agent.prompt("hello"):
            pass

        output = buf.getvalue()
        assert "agent_start" in output.lower()
        assert "agent_end" in output.lower()
        assert "turn" in output.lower()  # 含轮次信息

    @pytest.mark.asyncio
    async def test_disabled_observability_no_output(self):
        """enabled=False 时无输出"""
        buf = io.StringIO()
        config = ObservabilityConfig(enabled=False, log_file=None)
        agent = Agent(llm=MockLLM(), tool_registry=MockRegistry())
        observer = AgentObserver(agent, config, output=buf)

        async for _ in agent.prompt("hello"):
            pass

        assert buf.getvalue() == ""


class TestAgentObserverEventCoverage:
    """验证每种 AgentEvent 都被正确处理，且内容字段完整"""

    def _parse(self, buf):
        return [json.loads(l) for l in buf.getvalue().strip().split("\n")]

    @pytest.mark.asyncio
    async def test_covers_before_agent_start(self):
        """BeforeAgentStart 记录 user_input"""
        buf = io.StringIO()
        config = ObservabilityConfig(log_format="json")
        agent = Agent(llm=MockLLM(), tool_registry=MockRegistry(), system_prompt="你是助手")
        _ = AgentObserver(agent, config, output=buf)

        async for _ in agent.prompt("你好世界"):
            pass

        events = self._parse(buf)
        bas = [e for e in events if e["event"] == "before_agent_start"]
        assert len(bas) == 1
        assert "user_input" in bas[0]
        assert "你好世界" in bas[0]["user_input"]

    @pytest.mark.asyncio
    async def test_covers_agent_start_end(self):
        """AgentStart / AgentEnd 含 duration_ms 和 messages 数量"""
        buf = io.StringIO()
        config = ObservabilityConfig(log_format="json")
        agent = Agent(llm=MockLLM(), tool_registry=MockRegistry())
        _ = AgentObserver(agent, config, output=buf)

        async for _ in agent.prompt("test"):
            pass

        events = self._parse(buf)
        starts = [e for e in events if e["event"] == "agent_start"]
        ends = [e for e in events if e["event"] == "agent_end"]
        assert len(starts) == 1
        assert len(ends) == 1
        assert "duration_ms" in ends[0]
        assert ends[0]["duration_ms"] > 0
        assert "messages" in ends[0]

    @pytest.mark.asyncio
    async def test_covers_turn_events_with_chunks(self):
        """TurnStart / TurnEnd 含轮次、耗时、chunks 计数"""
        buf = io.StringIO()
        config = ObservabilityConfig(log_format="json")
        agent = Agent(llm=MockLLM(), tool_registry=MockRegistry())
        _ = AgentObserver(agent, config, output=buf)

        async for _ in agent.prompt("test"):
            pass

        events = self._parse(buf)
        turn_ends = [e for e in events if e["event"] == "turn_end"]
        assert len(turn_ends) == 1
        assert "turn" in turn_ends[0]
        assert turn_ends[0]["turn"] == 1
        assert "duration_ms" in turn_ends[0]
        assert "chunks" in turn_ends[0]  # MessageUpdate 增量计数

    @pytest.mark.asyncio
    async def test_covers_tool_events_with_fields(self):
        """ToolStart/ToolEnd 含 tool_name, args, duration_ms, error"""
        buf = io.StringIO()
        config = ObservabilityConfig(log_format="json")
        llm = MockLLM([
            LLMResponse(
                tool_calls=[
                    type("TC", (), {"id": "t1", "name": "search", "arguments": {"q": "x"}})()
                ],
                is_tool_call=True,
                finish_reason="tool_calls",
            ),
            LLMResponse(text="done", finish_reason="stop"),
        ])
        agent = Agent(
            llm=llm,
            tool_registry=MockRegistry(),
            tools=[type("T", (), {"name": "search", "label": "S", "description": "d", "parameters": {}})()],
        )
        _ = AgentObserver(agent, config, output=buf)

        async for _ in agent.prompt("search x"):
            pass

        events = self._parse(buf)
        tool_starts = [e for e in events if e["event"] == "tool_start"]
        tool_ends = [e for e in events if e["event"] == "tool_end"]
        assert len(tool_starts) == 1
        assert len(tool_ends) == 1
        assert "tool" in tool_starts[0]
        assert tool_starts[0]["tool"] == "search"
        assert "args" in tool_starts[0]
        assert "duration_ms" in tool_ends[0]
        assert "error" in tool_ends[0]
        assert tool_ends[0]["error"] is False

    @pytest.mark.asyncio
    async def test_covers_retry_events(self):
        """RetryStart/RetryEnd 记录重试次数和错误信息"""
        buf = io.StringIO()
        config = ObservabilityConfig(log_format="json")

        # 第一次抛异常，第二次成功
        call_count = [0]
        async def flaky_stream(self, messages, tools=None):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("API timeout")
            yield LLMResponse(text="ok", finish_reason="stop")

        class FlakyLLM:
            stream = flaky_stream

        agent = Agent(llm=FlakyLLM(), tool_registry=MockRegistry())
        _ = AgentObserver(agent, config, output=buf)

        async for _ in agent.prompt("test"):
            pass

        events = self._parse(buf)
        retry_starts = [e for e in events if e["event"] == "retry_start"]
        retry_ends = [e for e in events if e["event"] == "retry_end"]
        assert len(retry_starts) >= 1
        assert len(retry_ends) >= 1
        assert "attempt" in retry_starts[0]
        assert "error" in retry_starts[0]


class TestAgentObserverFileOutput:
    @pytest.mark.asyncio
    async def test_log_file_output(self, tmp_path):
        """log_file 指定时写入文件"""
        log_path = tmp_path / "agent.log"
        config = ObservabilityConfig(log_format="json", log_file=str(log_path))
        agent = Agent(llm=MockLLM(), tool_registry=MockRegistry())
        _ = AgentObserver(agent, config)

        async for _ in agent.prompt("hello"):
            pass

        assert log_path.exists()
        content = log_path.read_text().strip()
        assert len(content) > 0
        json.loads(content.split("\n")[0])  # 每行合法 JSON
