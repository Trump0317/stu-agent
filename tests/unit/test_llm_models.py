"""LLM 数据模型 — 单元测试

审核人: Trump
审核日期: 2026-06-07
审核状态: [已通过]
"""

from src.llm.models import LLMResponse, ToolCall


class TestToolCall:
    """ToolCall 数据类测试"""

    def test_create_with_all_fields(self):
        """创建带全部字段的 ToolCall"""
        tc = ToolCall(id="call_abc", name="select_template", arguments={"template": "lab_report"})
        assert tc.id == "call_abc"
        assert tc.name == "select_template"
        assert tc.arguments == {"template": "lab_report"}

    def test_create_with_empty_arguments(self):
        """无参工具调用"""
        tc = ToolCall(id="call_1", name="ping", arguments={})
        assert tc.arguments == {}
        assert tc.name == "ping"

    def test_arguments_preserves_types(self):
        """arguments 保留字典中的原始类型"""
        tc = ToolCall(
            id="call_1",
            name="calculate",
            arguments={"x": 1, "y": 2.5, "label": "result", "flag": True},
        )
        assert tc.arguments["x"] == 1
        assert tc.arguments["y"] == 2.5
        assert tc.arguments["label"] == "result"
        assert tc.arguments["flag"] is True


class TestLLMResponse:
    """LLMResponse 数据类测试"""

    def test_default_values(self):
        """默认值正确"""
        resp = LLMResponse()
        assert resp.text == ""
        assert resp.tool_calls == []
        assert resp.is_tool_call is False
        assert resp.finish_reason == ""
        assert resp.usage is None

    def test_text_response(self):
        """文本响应模式"""
        resp = LLMResponse(text="你好，我来帮你写论文。", finish_reason="stop")
        assert resp.text == "你好，我来帮你写论文。"
        assert resp.is_tool_call is False
        assert resp.finish_reason == "stop"
        assert resp.tool_calls == []

    def test_tool_call_response(self):
        """工具调用响应模式"""
        tc = ToolCall(id="call_x", name="write_section", arguments={"section": "引言"})
        resp = LLMResponse(
            tool_calls=[tc],
            is_tool_call=True,
            finish_reason="tool_calls",
        )
        assert resp.is_tool_call is True
        assert resp.finish_reason == "tool_calls"
        assert resp.text == ""
        assert len(resp.tool_calls) == 1
        assert resp.tool_calls[0].name == "write_section"

    def test_multi_tool_calls(self):
        """单次响应包含多个工具调用"""
        tc1 = ToolCall(id="c1", name="read_file", arguments={"path": "/tmp/a.txt"})
        tc2 = ToolCall(id="c2", name="read_file", arguments={"path": "/tmp/b.txt"})
        resp = LLMResponse(tool_calls=[tc1, tc2], is_tool_call=True, finish_reason="tool_calls")
        assert len(resp.tool_calls) == 2
        assert resp.tool_calls[0].id == "c1"
        assert resp.tool_calls[1].id == "c2"

    def test_usage_field(self):
        """usage 字段可传递 token 统计"""
        resp = LLMResponse(text="完成", finish_reason="stop", usage={"prompt_tokens": 10, "completion_tokens": 5})
        assert resp.usage == {"prompt_tokens": 10, "completion_tokens": 5}
