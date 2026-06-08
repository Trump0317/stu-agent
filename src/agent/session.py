"""AgentSession — 事件驱动会话编排器

对标 pi AgentSession，持有 Agent + LLM + ToolRegistry，
提供 on_turn_start/end, on_tool_call/result, on_chunk 回调。
run(user_input) → 委托 agent.prompt() → 分发事件 → 流式输出。
"""

from collections.abc import AsyncIterator, Callable

from src.agent.agent import Agent
from src.agent.events import (
    AgentEnd,
    MessageUpdate,
    ToolEnd,
    ToolStart,
    TurnEnd,
    TurnStart,
)
from src.agent.types import AgentMessage
from src.llm.base import BaseLLM
from src.tools.registry import ToolRegistry


class AgentSession:
    """会话编排器

    持有 Agent（状态）、LLM、ToolRegistry，驱动整个对话会话。
    通过回调属性暴露事件钩子，UI 层订阅这些回调来更新界面。

    Attributes:
        agent: 状态管理（system_prompt + messages + tools）
        on_turn_start: Callable[[int], None] — 回合开始时调用
        on_turn_end: Callable[[int, AgentMessage, list[dict]], None] — 回合结束时调用
        on_tool_call: Callable[[ToolStart], None] — 工具调用开始时调用
        on_tool_result: Callable[[ToolEnd], None] — 工具执行完成时调用
        on_chunk: Callable[[str], None] — 流式文本增量
    """

    def __init__(self, agent: Agent, llm: BaseLLM, tool_registry: ToolRegistry):
        self.agent = agent
        self._llm = llm
        self._tool_registry = tool_registry

        # 回调（对齐 pi）
        self.on_turn_start: Callable | None = None
        self.on_turn_end: Callable | None = None
        self.on_tool_call: Callable | None = None
        self.on_tool_result: Callable | None = None
        self.on_chunk: Callable | None = None

    def __repr__(self):
        return f"<AgentSession agent={self.agent}>"

    async def run(self, user_input: str) -> AsyncIterator[str]:
        """运行一次对话回合

        构建 context + config，调用 agent_loop 执行核心循环，
        分发事件到回调，流式输出文本，最终更新 agent.state.messages。

        Args:
            user_input: 用户输入文本

        Yields:
            流式文本增量
        """
        from src.agent.loop import agent_loop
        from src.agent.types import AgentContext, AgentLoopConfig

        # 构建 context 快照
        tools_openai = self._tools_to_openai_format(self.agent.state.tools)
        context = AgentContext(
            system_prompt=self.agent.state.system_prompt,
            messages=list(self.agent.state.messages),
            tools=tools_openai,
        )

        config = AgentLoopConfig(
            model="",
            stream_fn=self._llm.stream,
            convert_to_llm=lambda msgs: [
                self._agent_message_to_dict(m) for m in msgs
            ],
        )

        self.agent.state.is_streaming = True

        try:
            async for event in agent_loop(
                user_input, context, config, self._tool_registry
            ):
                # 通知 Agent 的 subscribers（保留兼容）
                for listener in self.agent._listeners:
                    try:
                        listener(event)
                    except Exception:
                        pass

                # 分发到 Session 回调
                self._dispatch_event(event)

                # 流式文本输出
                if isinstance(event, MessageUpdate) and event.delta_type == "text_delta":
                    if self.on_chunk:
                        try:
                            self.on_chunk(event.delta)
                        except Exception:
                            pass
                    yield event.delta

                # 更新 state.messages
                if isinstance(event, TurnEnd):
                    # TurnEnd 的 message 是最终 assistant 消息
                    pass
                if isinstance(event, AgentEnd):
                    self.agent.state.messages = list(event.messages)
        finally:
            self.agent.state.is_streaming = False

    @staticmethod
    def _tools_to_openai_format(tools: list) -> list[dict]:
        """将 AgentTool 列表转为 OpenAI function calling 格式"""
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
        return result

    @staticmethod
    def _agent_message_to_dict(msg) -> dict:
        """将 AgentMessage 转为 dict（给 LLM 用）"""
        m = {"role": msg.role}
        if msg.content is not None:
            m["content"] = msg.content
        elif hasattr(msg, "tool_calls") and msg.tool_calls:
            m["content"] = ""
        else:
            m["content"] = ""
        if msg.tool_call_id:
            m["tool_call_id"] = msg.tool_call_id
        if msg.tool_calls:
            m["tool_calls"] = msg.tool_calls
        return m

    def _dispatch_event(self, event) -> None:
        """将 agent_loop 事件分发到对应回调"""
        try:
            if isinstance(event, TurnStart) and self.on_turn_start:
                self.on_turn_start(event.turn)
            elif isinstance(event, TurnEnd) and self.on_turn_end:
                self.on_turn_end(event.turn, event.message, event.tool_results)
            elif isinstance(event, ToolStart) and self.on_tool_call:
                self.on_tool_call(event)
            elif isinstance(event, ToolEnd) and self.on_tool_result:
                self.on_tool_result(event)
        except Exception:
            pass  # 回调异常不影响主流程
