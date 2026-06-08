"""Agent — 有状态编排器

对标 pi agent.ts，持有 AgentState、事件订阅、prompt 方法。
对外暴露主 API。
"""

from collections.abc import AsyncIterator, Callable

from src.agent.loop import agent_loop
from src.agent.types import AgentContext, AgentLoopConfig, AgentMessage, AgentState, AgentTool


class Agent:
    """有状态 Agent 编排器

    持有 AgentState，管理事件订阅，将 prompt 委托给 agent_loop。
    """

    def __init__(
        self,
        llm,               # BaseLLM 实例（对齐 pi streamFn 注入）
        tool_registry,
        system_prompt: str = "",
        model: str = "",
        tools: list[AgentTool] | None = None,
    ) -> None:
        self._state = AgentState(
            system_prompt=system_prompt,
            tools=tools or [],
        )
        self._model = model
        self._tool_registry = tool_registry
        self._listeners: list[Callable] = []
        self._llm = llm

    @property
    def state(self) -> AgentState:
        return self._state

    def subscribe(self, listener: Callable) -> Callable[[], None]:
        """注册事件监听器

        Args:
            listener: 接收 AgentEvent 的回调函数

        Returns:
            注销函数，调用后该 listener 不再收到事件
        """
        self._listeners.append(listener)

        def unsubscribe():
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    async def prompt(self, user_input: str) -> AsyncIterator[str]:
        """发送用户输入，流式返回 Assistant 文本

        Args:
            user_input: 用户输入文本

        Yields:
            流式文本增量
        """
        # 构建 AgentContext 快照
        context = AgentContext(
            system_prompt=self._state.system_prompt,
            messages=self._state.messages,
            tools=_tools_to_openai_format(self._state.tools),
        )

        # 构建 AgentLoopConfig（桥接 LLM）

        config = AgentLoopConfig(
            model=self._model,
            stream_fn=self._llm.stream,
            convert_to_llm=_to_llm_messages,
        )

        self._state.is_streaming = True

        try:
            async for event in agent_loop(user_input, context, config, self._tool_registry):
                # 通知所有 listener
                for listener in self._listeners:
                    try:
                        listener(event)
                    except Exception:
                        pass  # listener 异常不影响主流程

                # 流式文本输出
                from src.agent.events import MessageUpdate

                if isinstance(event, MessageUpdate) and event.delta_type == "text_delta":
                    yield event.delta

                # 更新 state
                from src.agent.events import AgentEnd, TurnEnd

                if isinstance(event, TurnEnd):
                    self._state.messages.append(event.message)
                    # 追加 tool result messages
                    for tr in event.tool_results:
                        self._state.messages.append(
                            AgentMessage(
                                role="tool",
                                content=tr["content"][0] if tr["content"] else "",
                                tool_call_id=tr["tool_call_id"],
                            )
                        )

                if isinstance(event, AgentEnd):
                    # AgentEnd 中的 messages 是完整历史，替换 state
                    self._state.messages = event.messages
        finally:
            self._state.is_streaming = False

    def reset(self) -> None:
        """重置 Agent 状态（保留 system_prompt 和 tools）"""
        self._state = AgentState(
            system_prompt=self._state.system_prompt,
            tools=self._state.tools,
        )


# --- 内部辅助 ---


def _tools_to_openai_format(tools: list[AgentTool]) -> list[dict]:
    """将 AgentTool 列表转为 OpenAI tool 格式"""
    result = []
    for t in tools:
        result.append({
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            },
        })
    return result if result else None


def _to_llm_messages(messages: list[AgentMessage]) -> list[dict]:
    """将 AgentMessage 列表转为 LLM 兼容格式"""
    result = []
    for msg in messages:
        m = {"role": msg.role}
        if msg.content is not None:
            m["content"] = msg.content
        elif msg.role == "assistant" and msg.tool_calls:
            m["content"] = ""  # DeepSeek 不接受 null
        else:
            m["content"] = ""
        if msg.tool_call_id:
            m["tool_call_id"] = msg.tool_call_id
        if msg.tool_calls:
            m["tool_calls"] = msg.tool_calls
        result.append(m)
    return result
