"""AgentSession + 基础工具集成测试

审核人: Trump
审核日期: 2026-06-08
审核状态: [已通过]
"""

import os
import pytest

from src.agent.agent import Agent
from src.agent.events import ToolStart, ToolEnd
from src.agent.session import AgentSession
from src.agent.types import AgentTool
from src.llm.models import LLMResponse, ToolCall
from src.tools.bash_tool import BashTool
from src.tools.file_tools import ReadFileTool, WriteFileTool
from src.tools.registry import ToolRegistry


class MockLLM:
    """Mock LLM: 预置响应序列，记录 stream() 调用参数"""

    def __init__(self, responses: list[LLMResponse]):
        self._responses = responses
        self._idx = 0
        self.stream_calls = []

    async def stream(self, messages, tools=None):
        self.stream_calls.append((list(messages), tools))
        if self._idx < len(self._responses):
            yield self._responses[self._idx]
            self._idx += 1


def _make_session(tools: list, llm_responses: list[LLMResponse], tool_results: dict[str, str] | None = None):
    """创建 AgentSession + 真实 ToolRegistry + MockLLM"""
    # 注册工具
    reg = ToolRegistry()
    for t in tools:
        reg.register(t)

    # MockLLM
    llm = MockLLM(llm_responses)

    # Agent
    agent = Agent(
        llm=MockLLM([]),
        tool_registry=reg,
        system_prompt="你是助手，可以调用工具完成任务。",
    )
    # 注入 tools
    agent.state.tools = [
        AgentTool(name=t.name, label=t.name, description=t.description, parameters=t.parameters)
        for t in tools
    ]

    return AgentSession(agent=agent, llm=llm, tool_registry=reg)


def _to_tool_call(name: str, args: dict = None, call_id: str = "c1") -> ToolCall:
    return ToolCall(id=call_id, name=name, arguments=args or {})


class TestSessionWithBash:
    @pytest.mark.asyncio
    async def test_bash_echo(self):
        """AgentSession.run() → LLM 调用 bash echo → 返回结果"""
        session = _make_session(
            tools=[BashTool()],
            llm_responses=[
                LLMResponse(
                    tool_calls=[_to_tool_call("bash", {"command": "echo hello"})],
                    is_tool_call=True,
                    finish_reason="tool_calls",
                ),
                LLMResponse(text="命令执行成功：hello", finish_reason="stop"),
            ],
        )

        tool_calls = []
        session.on_tool_call = lambda e: tool_calls.append(e)
        session.on_tool_result = lambda e: tool_calls.append(e)

        chunks = [c async for c in session.run("执行 echo hello")]

        assert "命令执行成功" in "".join(chunks)
        assert len(tool_calls) == 2  # ToolStart + ToolEnd
        assert tool_calls[0].tool_name == "bash"
        assert tool_calls[1].is_error is False
        assert "hello" in tool_calls[1].result.content[0]

    @pytest.mark.asyncio
    async def test_bash_failure_is_reported(self):
        """bash 命令失败时 tool_result.is_error=True"""
        session = _make_session(
            tools=[BashTool()],
            llm_responses=[
                LLMResponse(
                    tool_calls=[_to_tool_call("bash", {"command": "nonexistent_cmd_xyz"})],
                    is_tool_call=True,
                    finish_reason="tool_calls",
                ),
                LLMResponse(text="命令失败了", finish_reason="stop"),
            ],
        )

        results = []
        session.on_tool_result = lambda e: results.append(e)

        chunks = [c async for c in session.run("运行不存在的命令")]
        assert "命令失败" in "".join(chunks) or len(chunks) > 0
        assert len(results) == 1
        assert results[0].is_error is True


class TestSessionWithFileTools:
    @pytest.mark.asyncio
    async def test_read_file(self):
        """read_file 读取 config/settings.yaml"""
        session = _make_session(
            tools=[ReadFileTool()],
            llm_responses=[
                LLMResponse(
                    tool_calls=[_to_tool_call("read_file", {"path": "config/settings.yaml"})],
                    is_tool_call=True,
                    finish_reason="tool_calls",
                ),
                LLMResponse(text="配置已读取", finish_reason="stop"),
            ],
        )

        results = []
        session.on_tool_result = lambda e: results.append(e)

        chunks = [c async for c in session.run("读取配置")]
        assert len(chunks) > 0
        assert len(results) == 1
        assert results[0].is_error is False
        assert "deepseek" in results[0].result.content[0].lower()

    @pytest.mark.asyncio
    async def test_write_and_read_file(self, tmp_path):
        """write_file → read_file 验证一致性"""
        test_path = str(tmp_path / "test_output.txt")
        content_to_write = "Hello from AgentSession!"

        session = _make_session(
            tools=[WriteFileTool(), ReadFileTool()],
            llm_responses=[
                LLMResponse(
                    tool_calls=[_to_tool_call("write_file", {
                        "path": test_path,
                        "content": content_to_write,
                    })],
                    is_tool_call=True,
                    finish_reason="tool_calls",
                ),
                LLMResponse(
                    tool_calls=[_to_tool_call("read_file", {"path": test_path})],
                    is_tool_call=True,
                    finish_reason="tool_calls",
                ),
                LLMResponse(text="文件已写入并读回", finish_reason="stop"),
            ],
        )

        results = []
        session.on_tool_result = lambda e: results.append(e)

        chunks = [c async for c in session.run("写入并读取文件")]
        assert len(chunks) > 0
        assert len(results) == 2  # write + read
        assert results[0].is_error is False
        assert results[1].is_error is False
        assert content_to_write in results[1].result.content[0]

        # 验证文件确实在磁盘上
        assert os.path.exists(test_path)
        assert open(test_path).read() == content_to_write


class TestSessionMultiTool:
    @pytest.mark.asyncio
    async def test_multi_tool_single_turn(self):
        """单轮内 LLM 调用多个工具"""
        session = _make_session(
            tools=[BashTool(), ReadFileTool()],
            llm_responses=[
                LLMResponse(
                    tool_calls=[
                        _to_tool_call("bash", {"command": "echo first"}, "c1"),
                        _to_tool_call("read_file", {"path": "config/settings.yaml"}, "c2"),
                    ],
                    is_tool_call=True,
                    finish_reason="tool_calls",
                ),
                LLMResponse(text="两个工具都已执行", finish_reason="stop"),
            ],
        )

        tool_starts = []
        tool_ends = []
        session.on_tool_call = lambda e: tool_starts.append(e.tool_name)
        session.on_tool_result = lambda e: tool_ends.append(e.tool_name)

        chunks = [c async for c in session.run("执行两个操作")]
        assert len(chunks) > 0
        assert tool_starts == ["bash", "read_file"]
        assert len(tool_ends) == 2
