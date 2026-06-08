"""ToolExecutor — 工具执行器

对标 pi harness/，负责单工具/多工具执行、before/after hooks、异常处理。

核心函数：
- execute_tool: 执行单个工具
- execute_tools: 顺序执行多个工具
"""

from src.agent.events import ToolEnd, ToolStart
from src.agent.types import AgentToolResult


async def execute_tool(
    tool_call_id: str,
    tool_name: str,
    args: dict,
    tool_registry,
    before_hook=None,
    after_hook=None,
    on_update=None,
) -> AgentToolResult:
    """执行单个工具调用

    Args:
        tool_call_id: 工具调用唯一 ID
        tool_name: 工具名称
        args: 工具参数
        tool_registry: ToolRegistry 实例（需有 execute(name, args) -> str 方法）
        before_hook: 执行前回调，可返回 {"block": True, "reason": "..."} 拦截
        after_hook: 执行后回调，可返回 {"content": [...], "is_error": bool} 修改结果
        on_update: 事件回调，接收 ToolStart/ToolEnd

    Returns:
        AgentToolResult: 工具执行结果
    """
    # 构建 before_hook 上下文（对齐 pi BeforeToolCallContext）
    ctx = {"tool_call_id": tool_call_id, "tool_name": tool_name, "args": args}

    # 触发 ToolStart
    if on_update:
        on_update(ToolStart(tool_call_id=tool_call_id, tool_name=tool_name, args=args))

    # before_hook 检查
    if before_hook:
        hook_result = before_hook(ctx)
        if hook_result and hook_result.get("block"):
            reason = hook_result.get("reason", "blocked")
            result = AgentToolResult(
                content=[f"Blocked: {reason}"],
                is_error=True,
            )
            if on_update:
                on_update(ToolEnd(
                    tool_call_id=tool_call_id,
                    tool_name=tool_name,
                    result=result,
                    is_error=True,
                ))
            return result

    # 执行工具
    try:
        raw_result = await tool_registry.execute(tool_name, args)
        # 兼容 ToolResult 和 str 两种返回
        if isinstance(raw_result, str):
            result = AgentToolResult(content=[raw_result], is_error=False)
        else:
            result = AgentToolResult(
                content=[raw_result.content],
                is_error=not raw_result.success,
            )
    except Exception as e:
        result = AgentToolResult(
            content=[f"Tool error: {e}"],
            details={"traceback": str(e)},
            is_error=True,
        )

    # after_hook 修改结果（对齐 pi AfterToolCallContext）
    if after_hook:
        ctx["result"] = result
        hook_result = after_hook(ctx)
        if hook_result:
            if "content" in hook_result:
                result = AgentToolResult(
                    content=hook_result["content"],
                    details=result.details,
                    is_error=hook_result.get("is_error", result.is_error),
                )

    # 触发 ToolEnd
    if on_update:
        on_update(ToolEnd(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            result=result,
            is_error=result.is_error,
        ))

    return result


async def execute_tools(
    tool_calls: list,
    tool_registry,
    before_hook=None,
    after_hook=None,
    on_update=None,
) -> list[AgentToolResult]:
    """顺序执行多个工具调用

    Args:
        tool_calls: ToolCall 列表（需有 id, name, arguments 属性）
        tool_registry: ToolRegistry 实例
        before_hook / after_hook / on_update: 透传给每个 execute_tool 调用

    Returns:
        结果列表，顺序与 tool_calls 一致
    """
    results = []
    for tc in tool_calls:
        result = await execute_tool(
            tool_call_id=tc.id,
            tool_name=tc.name,
            args=tc.arguments,
            tool_registry=tool_registry,
            before_hook=before_hook,
            after_hook=after_hook,
            on_update=on_update,
        )
        results.append(result)
    return results
