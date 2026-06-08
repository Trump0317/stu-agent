"""agent_loop — 核心循环纯函数

对标 pi agent-loop.ts，接收 context + config + tool_registry，
返回 event stream。无内部状态。
"""

from collections.abc import AsyncIterator
import json

from src.agent.events import (
    AgentEnd,
    AgentStart,
    BeforeAgentStart,
    MessageEnd,
    MessageStart,
    MessageUpdate,
    RetryEnd,
    RetryStart,
    TurnEnd,
    TurnStart,
)
from src.agent.executor import execute_tools
from src.agent.types import AgentContext, AgentLoopConfig, AgentMessage


async def agent_loop(
    prompt: str,
    context: AgentContext,
    config: AgentLoopConfig,
    tool_registry,
    signal=None,
) -> AsyncIterator:
    """Agent 核心循环（纯函数）

    Args:
        prompt: 用户输入
        context: AgentContext 快照（不修改入参）
        config: 循环行为配置
        tool_registry: ToolRegistry 实例
        signal: 取消信号（预留，对齐 pi）

    Yields:
        AgentEvent: 生命周期事件
    """
    messages = list(context.messages)  # 拷贝，不修改入参

    # 1. BeforeAgentStart
    system_prompt = context.system_prompt
    user_input = prompt
    yield BeforeAgentStart(system_prompt=system_prompt, user_input=user_input)

    # 2. AgentStart + TurnStart
    yield AgentStart()
    turn = 1
    yield TurnStart(turn=turn)

    # 3. 构建 system + user message
    if system_prompt:
        messages.insert(0, AgentMessage(role="system", content=system_prompt))
    user_msg = AgentMessage(role="user", content=user_input)
    messages.append(user_msg)

    # 4. 核心 while 循环
    tool_round = 0
    assistant_text = ""
    tool_results = []
    last_usage: dict | None = None

    while tool_round < config.max_tool_rounds:
        # transform_context（可选）
        current_messages = messages
        if config.transform_context:
            current_messages = config.transform_context(list(messages))

        # convert_to_llm
        llm_messages = config.convert_to_llm(current_messages)

        # LLM 流式调用 + 重试
        retry_count = 0
        had_tool_call = False
        while True:
            try:
                async for response in config.stream_fn(llm_messages, context.tools):
                    if response.is_tool_call:
                        had_tool_call = True
                        # 过滤无效 tool_call（DeepSeek 偶发的 id=None / name=""）
                        valid_calls = [tc for tc in response.tool_calls if tc.id and tc.name]
                        if not valid_calls:
                            continue

                        # 先保存 assistant 消息（含 tool_calls）
                        assistant_msg_with_tools = AgentMessage(
                            role="assistant",
                            content=None,
                            tool_calls=[
                                {"id": tc.id, "type": "function",
                                 "function": {"name": tc.name, "arguments": json.dumps(tc.arguments, ensure_ascii=False)}}
                                for tc in valid_calls
                            ],
                        )
                        messages.append(assistant_msg_with_tools)

                        # 收集 executor 产生的事件
                        tool_events = []

                        def on_update(event):
                            tool_events.append(event)

                        results = await execute_tools(
                            tool_calls=valid_calls,
                            tool_registry=tool_registry,
                            before_hook=config.before_tool_call,
                            after_hook=config.after_tool_call,
                            on_update=on_update,
                        )
                        tool_round += 1

                        # Yield executor 事件
                        for ev in tool_events:
                            yield ev

                        # Emit tool result messages
                        for tc, result in zip(valid_calls, results):
                            msg = AgentMessage(
                                role="tool",
                                content=result.content[0] if result.content else "",
                                tool_call_id=tc.id,
                            )
                            yield MessageStart(message=msg)
                            yield MessageEnd(message=msg)
                            messages.append(msg)
                            tool_results.append({
                                "tool_call_id": tc.id,
                                "tool_name": tc.name,
                                "content": result.content,
                                "is_error": result.is_error,
                            })

                        if tool_round >= config.max_tool_rounds:
                            break

                    elif response.text:
                        if not assistant_text:
                            assistant_msg = AgentMessage(role="assistant", content="")
                            yield MessageStart(message=assistant_msg)
                        assistant_text += response.text
                        delta_msg = AgentMessage(role="assistant", content=assistant_text)
                        yield MessageUpdate(message=delta_msg, delta=response.text, delta_type="text_delta")

                    # 捕获 usage（通常最后一片 chunk 带）
                    if response.usage:
                        last_usage = response.usage

                # stream 正常结束
                break

            except Exception as e:
                if retry_count < config.max_retries:
                    retry_count += 1
                    yield RetryStart(attempt=retry_count, error=str(e))
                    yield RetryEnd(attempt=retry_count, error=str(e))
                    continue
                raise

        # 非 tool_call 轮次 → LLM 已给出最终响应，退出循环
        if not had_tool_call:
            break
        if tool_round >= config.max_tool_rounds:
            break

    # 5. MessageEnd
    if assistant_text:
        final_msg = AgentMessage(role="assistant", content=assistant_text)
        yield MessageEnd(message=final_msg)
        messages.append(final_msg)
    else:
        final_msg = AgentMessage(role="assistant", content="")

    # 6. TurnEnd + AgentEnd
    yield TurnEnd(turn=turn, message=final_msg, tool_results=tool_results, usage=last_usage)
    yield AgentEnd(messages=messages)
