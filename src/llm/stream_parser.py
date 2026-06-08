"""流式解析引擎

将 OpenAI 兼容 API 的流式 chunk 转换为 LLMResponse 序列。
B5 (OpenAICompatProvider) 和 B6 (OpenAINativeProvider) 共用此模块。
"""

import json
from collections.abc import AsyncIterator

from src.llm.models import LLMResponse, ToolCall


async def parse_openai_stream(stream) -> AsyncIterator[LLMResponse]:
    """解析 OpenAI 兼容的流式响应

    遍历 stream 的每个 chunk，处理以下情况：
    - delta.content 非空 → yield LLMResponse(text=content)
    - delta.tool_calls 非空 → 按 id 累积 function.name 和 function.arguments
    - finish_reason == "tool_calls" → yield LLMResponse(tool_calls=[...], is_tool_call=True)
    - 最终 chunk 的 finish_reason 传递到最后一个 LLMResponse

    Args:
        stream: OpenAI AsyncChatCompletion 流式响应（async iterable）

    Yields:
        LLMResponse: 流式响应块
    """
    # 累积中的工具调用: id -> {id, name, arguments_raw}
    pending_tool_calls: dict[str, dict] = {}
    pending_usage: dict | None = None
    _current_tc_id: str | None = None  # DeepSeek: 后续块的 id 为 None

    async for chunk in stream:
        if not chunk.choices:
            continue

        choice = chunk.choices[0]
        delta = choice.delta
        finish_reason = choice.finish_reason

        # 捕获 usage（通常出现在最后一个 chunk）
        if hasattr(chunk, "usage") and chunk.usage is not None:
            pending_usage = _extract_usage(chunk.usage)

        # 处理文本内容
        if delta.content:
            resp = LLMResponse(
                text=delta.content,
                finish_reason=finish_reason or "",
                usage=pending_usage,
            )
            pending_usage = None
            yield resp

        # 处理工具调用
        if hasattr(delta, "tool_calls") and delta.tool_calls:
            for tc in delta.tool_calls:
                # DeepSeek: 第一个 chunk 有 id，后续 chunk id=None
                tc_id = tc.id if tc.id else _current_tc_id
                if tc_id and tc_id not in pending_tool_calls:
                    pending_tool_calls[tc_id] = {
                        "id": tc_id,
                        "name": "",
                        "arguments_raw": "",
                    }
                if tc.id:
                    _current_tc_id = tc.id
                if tc_id is None:
                    continue  # 无法确定归属，跳过
                # 累积 function.name（通常只在第一个 chunk 出现）
                if hasattr(tc.function, "name") and tc.function.name:
                    pending_tool_calls[tc_id]["name"] = tc.function.name
                # 累积 function.arguments（跨 chunk 拼接）
                if hasattr(tc.function, "arguments") and tc.function.arguments:
                    pending_tool_calls[tc_id]["arguments_raw"] += tc.function.arguments

        # 工具调用结束：解析 arguments 并输出
        if finish_reason == "tool_calls" and pending_tool_calls:
            tool_calls = []
            for tc_data in pending_tool_calls.values():
                arguments = _safe_json_parse(tc_data["arguments_raw"])
                tool_calls.append(
                    ToolCall(
                        id=tc_data["id"],
                        name=tc_data["name"],
                        arguments=arguments,
                    )
                )
            yield LLMResponse(
                tool_calls=tool_calls,
                is_tool_call=True,
                finish_reason=finish_reason,
                usage=pending_usage,
            )
            pending_usage = None
            pending_tool_calls.clear()


def _safe_json_parse(raw: str):
    """安全解析 JSON 字符串，非法时返回原始字符串"""
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw


def _extract_usage(usage_obj) -> dict:
    """从 OpenAI usage 对象提取字典"""
    if isinstance(usage_obj, dict):
        return usage_obj
    return {
        "prompt_tokens": getattr(usage_obj, "prompt_tokens", 0),
        "completion_tokens": getattr(usage_obj, "completion_tokens", 0),
        "total_tokens": getattr(usage_obj, "total_tokens", 0),
    }
