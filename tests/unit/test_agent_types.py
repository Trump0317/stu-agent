"""Agent 类型定义 — 单元测试

审核人: Trump
审核日期: 2026-06-07
审核状态: [已通过]
"""

import pytest

from src.agent.types import (
    AgentContext,
    AgentLoopConfig,
    AgentMessage,
    AgentState,
    AgentTool,
    AgentToolResult,
)


class TestAgentToolResult:
    def test_success_result(self):
        result = AgentToolResult(content=["file content"])
        assert result.content == ["file content"]
        assert result.details is None
        assert result.is_error is False

    def test_error_result(self):
        result = AgentToolResult(
            content=["error message"],
            details={"traceback": "..."},
            is_error=True,
        )
        assert result.is_error is True
        assert result.details == {"traceback": "..."}


class TestAgentTool:
    def test_tool_definition(self):
        tool = AgentTool(
            name="read_file",
            label="读文件",
            description="读取指定路径的文件内容",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        )
        assert tool.name == "read_file"
        assert tool.label == "读文件"
        assert tool.parameters["required"] == ["path"]


class TestAgentMessage:
    def test_user_message(self):
        msg = AgentMessage(role="user", content="你好")
        assert msg.role == "user"
        assert msg.content == "你好"
        assert msg.tool_call_id is None
        assert msg.tool_calls is None

    def test_assistant_message(self):
        msg = AgentMessage(role="assistant", content="你好！有什么可以帮你？")
        assert msg.role == "assistant"

    def test_tool_result_message(self):
        msg = AgentMessage(
            role="tool",
            content="file content here",
            tool_call_id="call_abc",
        )
        assert msg.role == "tool"
        assert msg.tool_call_id == "call_abc"

    def test_assistant_with_tool_calls(self):
        msg = AgentMessage(
            role="assistant",
            content=None,
            tool_calls=[
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "read_file", "arguments": '{"path": "/tmp/a.txt"}'},
                }
            ],
        )
        assert msg.role == "assistant"
        assert msg.content is None
        assert len(msg.tool_calls) == 1
        assert msg.tool_calls[0]["id"] == "call_1"


class TestAgentState:
    def test_default_state(self):
        state = AgentState(system_prompt="You are helpful.")
        assert state.system_prompt == "You are helpful."
        assert state.tools == []
        assert state.messages == []
        assert state.is_streaming is False
        assert state.error_message is None

    def test_state_with_tools_and_messages(self):
        tool = AgentTool(name="search", label="搜索", description="搜索", parameters={})
        msg = AgentMessage(role="user", content="hello")
        state = AgentState(
            system_prompt="prompt",
            tools=[tool],
            messages=[msg],
        )
        assert len(state.tools) == 1
        assert len(state.messages) == 1
        assert state.messages[0].content == "hello"


class TestAgentContext:
    def test_from_state_snapshot(self):
        """AgentContext 从 AgentState 构建快照"""
        state = AgentState(
            system_prompt="You are helpful.",
            messages=[AgentMessage(role="user", content="hi")],
            tools=[AgentTool(name="t", label="T", description="D", parameters={})],
        )
        ctx = AgentContext(
            system_prompt=state.system_prompt,
            messages=state.messages,
            tools=[{"type": "function", "function": {"name": "t", "parameters": {}}}],
        )
        assert ctx.system_prompt == "You are helpful."
        assert len(ctx.messages) == 1
        assert ctx.tools is not None
        assert len(ctx.tools) == 1


class TestAgentLoopConfig:
    def test_default_config(self):
        def dummy_stream(messages, tools=None):
            pass

        config = AgentLoopConfig(
            model="test-model",
            stream_fn=dummy_stream,
            convert_to_llm=lambda msgs: msgs,
        )
        assert config.model == "test-model"
        assert config.stream_fn is dummy_stream
        assert config.max_tool_rounds == 5
        assert config.max_retries == 2
        assert config.transform_context is None
        assert config.before_tool_call is None
        assert config.after_tool_call is None

    def test_custom_limits(self):
        config = AgentLoopConfig(
            model="test",
            stream_fn=lambda m, t=None: None,
            convert_to_llm=lambda m: m,
            max_tool_rounds=5,
            max_retries=3,
        )
        assert config.max_tool_rounds == 5
        assert config.max_retries == 3

    def test_with_hooks(self):
        """transform_context, before_tool_call, after_tool_call 自定义赋值"""
        tx = lambda msgs, sig=None: msgs
        before = lambda ctx, sig=None: None
        after = lambda ctx, sig=None: None
        config = AgentLoopConfig(
            model="test",
            stream_fn=lambda m, t=None: None,
            convert_to_llm=lambda m: m,
            transform_context=tx,
            before_tool_call=before,
            after_tool_call=after,
        )
        assert config.transform_context is tx
        assert config.before_tool_call is before
        assert config.after_tool_call is after


class TestAgentContextEdgeCases:
    def test_tools_none(self):
        """tools 为 None（默认值）"""
        ctx = AgentContext(
            system_prompt="prompt",
            messages=[AgentMessage(role="user", content="hi")],
        )
        assert ctx.tools is None

    def test_empty_messages(self):
        """空 messages 列表"""
        ctx = AgentContext(system_prompt="prompt", messages=[])
        assert ctx.messages == []


class TestAgentMessageEdgeCases:
    def test_empty_content(self):
        """content 为空字符串"""
        msg = AgentMessage(role="user", content="")
        assert msg.content == ""

    def test_system_message(self):
        """system 角色消息"""
        msg = AgentMessage(role="system", content="You are helpful.")
        assert msg.role == "system"
