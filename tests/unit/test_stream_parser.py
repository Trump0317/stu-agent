"""流式解析引擎 — 单元测试

审核人: Trump
审核日期: 2026-06-07
审核状态: [已通过]
"""

import json
from types import SimpleNamespace

import pytest

from src.llm.models import LLMResponse, ToolCall
from src.llm.stream_parser import parse_openai_stream


# --- 辅助：构造 OpenAI 流式 chunk ---

def _chunk(content=None, tool_calls=None, finish_reason=None, usage=None):
    """构造单个 OpenAI 流式响应 chunk (SimpleNamespace)

    Args:
        usage: 可选 dict，如 {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
    """
    delta = {"content": content}
    if tool_calls is not None:
        delta["tool_calls"] = [
            SimpleNamespace(
                index=tc.get("index", 0),
                id=tc.get("id"),
                function=SimpleNamespace(
                    name=tc.get("name"),
                    arguments=tc.get("arguments", ""),
                ),
            )
            for tc in tool_calls
        ]
    ns = SimpleNamespace(
        choices=[
            SimpleNamespace(
                index=0,
                delta=SimpleNamespace(**delta),
                finish_reason=finish_reason,
            )
        ]
    )
    if usage is not None:
        ns.usage = SimpleNamespace(**usage)
    return ns


async def _stream(*chunks):
    """将 chunk 列表转为异步迭代器"""
    for c in chunks:
        yield c


# --- 用例 ---

class TestParseOpenAIStream:
    """parse_openai_stream 核心逻辑测试"""

    @pytest.mark.asyncio
    async def test_pure_text_stream(self):
        """纯文本流 → 每 chunk 一个 LLMResponse(text=...)"""
        chunks = [
            _chunk(content="你好"),
            _chunk(content="，世界"),
            _chunk(content="！", finish_reason="stop"),
        ]
        responses = [r async for r in parse_openai_stream(_stream(*chunks))]

        assert len(responses) == 3
        assert responses[0].text == "你好"
        assert responses[1].text == "，世界"
        assert responses[2].text == "！"
        assert all(not r.is_tool_call for r in responses)
        assert responses[-1].finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_tool_call_stream(self):
        """工具调用流 → 累积 arguments 并在 finish_reason=tool_calls 时输出"""
        chunks = [
            _chunk(tool_calls=[{"index": 0, "id": "call_1", "name": "write_section", "arguments": '{"sec'}]),
            _chunk(tool_calls=[{"index": 0, "id": "call_1", "arguments": 'tion": "引言"}'}]),
            _chunk(finish_reason="tool_calls"),
        ]
        responses = [r async for r in parse_openai_stream(_stream(*chunks))]

        # 最后一个应包含完整 ToolCall
        assert len(responses) == 1
        assert responses[0].is_tool_call is True
        assert responses[0].finish_reason == "tool_calls"
        assert len(responses[0].tool_calls) == 1
        tc = responses[0].tool_calls[0]
        assert tc.id == "call_1"
        assert tc.name == "write_section"
        assert tc.arguments == {"section": "引言"}

    @pytest.mark.asyncio
    async def test_multi_tool_calls(self):
        """单次响应包含多个工具调用"""
        chunks = [
            _chunk(tool_calls=[
                {"index": 0, "id": "c1", "name": "read_file", "arguments": '{"p'},
                {"index": 1, "id": "c2", "name": "read_file", "arguments": '{"p'},
            ]),
            _chunk(tool_calls=[
                {"index": 0, "id": "c1", "arguments": 'ath": "/a"}'},
                {"index": 1, "id": "c2", "arguments": 'ath": "/b"}'},
            ]),
            _chunk(finish_reason="tool_calls"),
        ]
        responses = [r async for r in parse_openai_stream(_stream(*chunks))]

        assert len(responses) == 1
        assert len(responses[0].tool_calls) == 2
        assert responses[0].finish_reason == "tool_calls"
        assert responses[0].tool_calls[0].id == "c1"
        assert responses[0].tool_calls[1].id == "c2"
        assert responses[0].tool_calls[0].arguments == {"path": "/a"}
        assert responses[0].tool_calls[1].arguments == {"path": "/b"}

    @pytest.mark.asyncio
    async def test_mixed_text_and_tool_call(self):
        """混合流：先文本，后工具调用"""
        chunks = [
            _chunk(content="好的，我来调用工具。"),
            _chunk(tool_calls=[{"index": 0, "id": "call_x", "name": "search", "arguments": '{"q":"test"}'}]),
            _chunk(finish_reason="tool_calls"),
        ]
        responses = [r async for r in parse_openai_stream(_stream(*chunks))]

        assert len(responses) == 2
        assert responses[0].text == "好的，我来调用工具。"
        assert responses[0].is_tool_call is False
        assert responses[1].is_tool_call is True
        assert responses[1].tool_calls[0].name == "search"

    @pytest.mark.asyncio
    async def test_finish_reason_stop(self):
        """finish_reason='stop' 传递到最后一个响应"""
        chunks = [
            _chunk(content="完成。", finish_reason="stop"),
        ]
        responses = [r async for r in parse_openai_stream(_stream(*chunks))]
        assert responses[-1].finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_empty_stream(self):
        """空流返回空列表"""
        responses = [r async for r in parse_openai_stream(_stream())]
        assert responses == []

    @pytest.mark.asyncio
    async def test_content_is_none(self):
        """delta.content 为 None 时不产出文本块"""
        chunks = [
            _chunk(content=None),
            _chunk(content="Hi", finish_reason="stop"),
        ]
        responses = [r async for r in parse_openai_stream(_stream(*chunks))]
        assert len(responses) == 1
        assert responses[0].text == "Hi"

    @pytest.mark.asyncio
    async def test_finish_reason_length(self):
        """finish_reason='length' 正确传递"""
        chunks = [
            _chunk(content="内容被截断...", finish_reason="length"),
        ]
        responses = [r async for r in parse_openai_stream(_stream(*chunks))]
        assert responses[-1].finish_reason == "length"

    @pytest.mark.asyncio
    async def test_malformed_tool_arguments(self):
        """非法 JSON 的 arguments → 保留原始字符串（优雅降级）"""
        chunks = [
            _chunk(tool_calls=[{"index": 0, "id": "c1", "name": "f", "arguments": "{bad json"}]),
            _chunk(finish_reason="tool_calls"),
        ]
        responses = [r async for r in parse_openai_stream(_stream(*chunks))]
        assert len(responses) == 1
        assert responses[0].is_tool_call is True
        # 优雅降级：保留原始字符串
        assert responses[0].tool_calls[0].arguments == "{bad json"


class TestParseOpenAIStreamUsage:
    @pytest.mark.asyncio
    async def test_final_chunk_usage_extracted(self):
        """最后一片 chunk 带 usage → LLMResponse.usage 被填充"""
        chunks = [
            _chunk(content="Hello"),
            _chunk(content=" World", finish_reason="stop", usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}),
        ]
        responses = [r async for r in parse_openai_stream(_stream(*chunks))]
        assert responses[-1].usage is not None
        assert responses[-1].usage["prompt_tokens"] == 10
        assert responses[-1].usage["completion_tokens"] == 5
        assert responses[-1].usage["total_tokens"] == 15

    @pytest.mark.asyncio
    async def test_no_usage_when_not_present(self):
        """无 usage chunk → LLMResponse.usage 为 None"""
        chunks = [
            _chunk(content="Hello", finish_reason="stop"),
        ]
        responses = [r async for r in parse_openai_stream(_stream(*chunks))]
        assert responses[0].usage is None
