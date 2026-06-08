"""Agent 事件类型 — 单元测试

审核人: Trump
审核日期: 2026-06-07
审核状态: [已通过]
"""

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
    ToolUpdate,
    TurnEnd,
    TurnStart,
)
from src.agent.types import AgentMessage, AgentToolResult


class TestBeforeAgentStart:
    def test_create(self):
        event = BeforeAgentStart(system_prompt="You are helpful.", user_input="帮我写论文")
        assert event.system_prompt == "You are helpful."
        assert event.user_input == "帮我写论文"
        assert isinstance(event, BeforeAgentStart)


class TestAgentStartEnd:
    def test_agent_start(self):
        event = AgentStart()
        assert isinstance(event, AgentStart)

    def test_agent_end(self):
        msg = AgentMessage(role="assistant", content="完成")
        event = AgentEnd(messages=[msg])
        assert len(event.messages) == 1
        assert event.messages[0].content == "完成"


class TestTurnStartEnd:
    def test_turn_start(self):
        event = TurnStart(turn=1)
        assert event.turn == 1
        assert isinstance(event, TurnStart)

    def test_turn_end(self):
        msg = AgentMessage(role="assistant", content="回答")
        event = TurnEnd(turn=2, message=msg, tool_results=[])
        assert event.turn == 2
        assert event.message.content == "回答"
        assert event.tool_results == []


class TestMessageEvents:
    def test_message_start(self):
        msg = AgentMessage(role="user", content="hello")
        event = MessageStart(message=msg)
        assert event.message.role == "user"
        assert event.message.content == "hello"

    def test_message_update(self):
        msg = AgentMessage(role="assistant", content="partial...")
        event = MessageUpdate(message=msg, delta="part", delta_type="text_delta")
        assert event.delta == "part"
        assert event.delta_type == "text_delta"

    def test_message_end(self):
        msg = AgentMessage(role="assistant", content="final")
        event = MessageEnd(message=msg)
        assert event.message.content == "final"
        assert isinstance(event, MessageEnd)


class TestToolEvents:
    def test_tool_start(self):
        event = ToolStart(tool_call_id="call_1", tool_name="read_file", args={"path": "/tmp/a.txt"})
        assert event.tool_call_id == "call_1"
        assert event.tool_name == "read_file"
        assert event.args == {"path": "/tmp/a.txt"}

    def test_tool_update(self):
        event = ToolUpdate(
            tool_call_id="call_1",
            tool_name="read_file",
            partial_result={"bytes_read": 100},
        )
        assert event.partial_result == {"bytes_read": 100}

    def test_tool_end_success(self):
        result = AgentToolResult(content=["file content"])
        event = ToolEnd(tool_call_id="call_1", tool_name="read_file", result=result, is_error=False)
        assert event.is_error is False
        assert event.result.content == ["file content"]

    def test_tool_end_error(self):
        result = AgentToolResult(content=["error"], is_error=True)
        event = ToolEnd(tool_call_id="call_x", tool_name="bad_tool", result=result, is_error=True)
        assert event.is_error is True
        assert isinstance(event, ToolEnd)


class TestRetryEvents:
    def test_retry_start(self):
        event = RetryStart(attempt=1, error="Connection timeout")
        assert event.attempt == 1
        assert event.error == "Connection timeout"

    def test_retry_end(self):
        event = RetryEnd(attempt=2, error="Recovered")
        assert event.attempt == 2
        assert event.error == "Recovered"
        assert isinstance(event, RetryEnd)
