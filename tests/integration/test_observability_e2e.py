"""可观测性集成测试

审核人: Trump
审核日期: 2026-06-07
审核状态: [已通过]
"""

import io
import json
import uuid
import pytest

from src.agent.agent import Agent
from src.agent.types import AgentTool
from src.llm.models import LLMResponse, ToolCall
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
    def __init__(self, results=None):
        self._results = results or {}

    async def execute(self, name, args):
        if name in self._results:
            r = self._results[name]
            if isinstance(r, Exception):
                raise r
            return r
        return f"result of {name}"


class TestObservabilityE2E:
    @pytest.mark.asyncio
    async def test_simple_text_dialog(self):
        """纯文本对话：AgentStart→AgentEnd 含耗时"""
        config = ObservabilityConfig(log_format="json")
        buf = io.StringIO()
        agent = Agent(llm=MockLLM([LLMResponse(text="hi", finish_reason="stop")]),
                      tool_registry=MockRegistry())
        obs = AgentObserver(agent, config, buf)

        async for _ in agent.prompt("hello"):
            pass

        lines = [json.loads(l) for l in buf.getvalue().strip().split("\n")]
        events = [l["event"] for l in lines]
        assert "agent_start" in events
        assert "agent_end" in events
        agent_end = lines[-1]
        assert agent_end["duration_ms"] > 0
        assert agent_end["messages"] == 2  # user + assistant

    @pytest.mark.asyncio
    async def test_tool_call_traced(self):
        """工具调用：ToolStart/ToolEnd 含 tool 名和耗时"""
        config = ObservabilityConfig(log_format="json")
        buf = io.StringIO()
        llm = MockLLM([
            LLMResponse(
                tool_calls=[ToolCall(id="t1", name="write", arguments={"path": "/f"})],
                is_tool_call=True,
                finish_reason="tool_calls",
            ),
            LLMResponse(text="done", finish_reason="stop"),
        ])
        agent = Agent(
            llm=llm,
            tool_registry=MockRegistry(),
            tools=[AgentTool(name="write", label="Write", description="写入文件", parameters={})],
        )
        obs = AgentObserver(agent, config, buf)

        async for _ in agent.prompt("write a file"):
            pass

        lines = [json.loads(l) for l in buf.getvalue().strip().split("\n")]
        tool_start = next(l for l in lines if l["event"] == "tool_start")
        tool_end = next(l for l in lines if l["event"] == "tool_end")
        assert tool_start["tool"] == "write"
        assert tool_start["args"] == {"path": "/f"}
        assert tool_end["duration_ms"] > 0
        assert tool_end["error"] is False

    @pytest.mark.asyncio
    async def test_tool_error_traced(self):
        """工具执行错误：is_error=True 被记录"""
        config = ObservabilityConfig(log_format="json")
        buf = io.StringIO()
        llm = MockLLM([
            LLMResponse(
                tool_calls=[ToolCall(id="t1", name="read", arguments={"path": "/nope"})],
                is_tool_call=True,
                finish_reason="tool_calls",
            ),
            LLMResponse(text="failed to read", finish_reason="stop"),
        ])
        agent = Agent(
            llm=llm,
            tool_registry=MockRegistry({"read": FileNotFoundError("no such file")}),
            tools=[AgentTool(name="read", label="Read", description="读取文件", parameters={})],
        )
        obs = AgentObserver(agent, config, buf)

        async for _ in agent.prompt("read missing file"):
            pass

        lines = [json.loads(l) for l in buf.getvalue().strip().split("\n")]
        tool_end = next(l for l in lines if l["event"] == "tool_end")
        assert tool_end["tool"] == "read"
        assert tool_end["error"] is True

    @pytest.mark.asyncio
    async def test_multi_turn_dialog(self):
        """多轮对话：run_id 一致，turn 递增，messages 累积"""
        config = ObservabilityConfig(log_format="json")
        buf = io.StringIO()
        llm = MockLLM([
            LLMResponse(text="第一轮回复", finish_reason="stop"),
            LLMResponse(text="第二轮回复", finish_reason="stop"),
        ])
        agent = Agent(llm=llm, tool_registry=MockRegistry())
        obs = AgentObserver(agent, config, buf)

        async for _ in agent.prompt("第一问"):
            pass
        async for _ in agent.prompt("第二问"):
            pass

        lines = [json.loads(l) for l in buf.getvalue().strip().split("\n")]
        run_ids = {l["run_id"] for l in lines}
        assert len(run_ids) == 2  # 两次 prompt 各一个 run_id

        # 第二次调用的 turn 编号应从 1 开始
        last_events = [l for l in lines if l["run_id"] == list(run_ids)[1]]
        turn_starts = [l for l in last_events if l["event"] == "turn_start"]
        assert len(turn_starts) == 1
        assert turn_starts[0]["turn"] == 1

        # AgentEnd messages 累积
        agent_ends = [l for l in lines if l["event"] == "agent_end"]
        assert len(agent_ends) == 2
        assert agent_ends[1]["messages"] == 4  # 第二轮后累积 4 条

    @pytest.mark.asyncio
    async def test_retry_traced(self):
        """LLM 重试：RetryStart/RetryEnd 记录重试信息"""
        config = ObservabilityConfig(log_format="json")
        buf = io.StringIO()
        call_count = [0]

        async def flaky_stream(self, messages, tools=None):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("API timeout")
            yield LLMResponse(text="ok", finish_reason="stop")

        class FlakyLLM:
            stream = flaky_stream

        agent = Agent(llm=FlakyLLM(), tool_registry=MockRegistry())
        obs = AgentObserver(agent, config, buf)

        async for _ in agent.prompt("test"):
            pass

        lines = [json.loads(l) for l in buf.getvalue().strip().split("\n")]
        retry_start = next((l for l in lines if l["event"] == "retry_start"), None)
        retry_end = next((l for l in lines if l["event"] == "retry_end"), None)
        assert retry_start is not None, "应记录 retry_start"
        assert retry_end is not None, "应记录 retry_end"
        assert retry_start["attempt"] == 1
        assert "API timeout" in retry_start["error"]

    @pytest.mark.asyncio
    async def test_json_output_parseable(self):
        """每行 json 可解析且同一 run_id 为合法 UUID"""
        config = ObservabilityConfig(log_format="json")
        buf = io.StringIO()
        agent = Agent(llm=MockLLM([LLMResponse(text="hi", finish_reason="stop")]),
                      tool_registry=MockRegistry())
        obs = AgentObserver(agent, config, buf)

        async for _ in agent.prompt("test"):
            pass

        lines = buf.getvalue().strip().split("\n")
        assert len(lines) >= 2
        run_ids = set()
        for line in lines:
            obj = json.loads(line)
            assert "event" in obj
            assert "ts" in obj
            assert "run_id" in obj
            uuid.UUID(obj["run_id"])  # 合法 UUID
            run_ids.add(obj["run_id"])
        assert len(run_ids) == 1

    @pytest.mark.asyncio
    async def test_text_output_human_readable(self):
        """text 格式含事件顺序"""
        config = ObservabilityConfig(log_format="text")
        buf = io.StringIO()
        agent = Agent(llm=MockLLM([LLMResponse(text="hi", finish_reason="stop")]),
                      tool_registry=MockRegistry())
        obs = AgentObserver(agent, config, buf)

        async for _ in agent.prompt("hello"):
            pass

        output = buf.getvalue()
        # 验证事件顺序
        pos_as = output.index("agent_start")
        pos_ts = output.index("turn_start")
        pos_te = output.index("turn_end")
        pos_ae = output.index("agent_end")
        assert pos_as < pos_ts < pos_te < pos_ae

    @pytest.mark.asyncio
    async def test_file_output(self, tmp_path):
        """指定 log_file 则写入文件，全部行可解析"""
        log_path = tmp_path / "obs.log"
        config = ObservabilityConfig(log_format="json", log_file=str(log_path))
        agent = Agent(llm=MockLLM([LLMResponse(text="hi", finish_reason="stop")]),
                      tool_registry=MockRegistry())
        obs = AgentObserver(agent, config)

        async for _ in agent.prompt("test"):
            pass

        assert log_path.exists()
        content = log_path.read_text().strip()
        assert len(content) > 0
        for line in content.split("\n"):
            json.loads(line)  # 每行可解析
