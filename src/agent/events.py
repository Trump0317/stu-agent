"""Agent 事件类型

对标 pi types.ts 中的 AgentEvent 联合类型。
每种事件独立 dataclass，通过 isinstance 分派。
"""

from dataclasses import dataclass

from src.agent.types import AgentMessage, AgentToolResult


@dataclass
class BeforeAgentStart:
    """prompt 处理前拦截（回调可修改 system_prompt / user_input）"""

    system_prompt: str
    user_input: str


@dataclass
class AgentStart:
    """Agent 开始处理 prompt（纯信号）"""
    pass


@dataclass
class AgentEnd:
    """Agent 处理完毕"""

    messages: list[AgentMessage]


@dataclass
class TurnStart:
    """新一轮 LLM 响应开始"""

    turn: int


@dataclass
class TurnEnd:
    """一轮结束"""

    turn: int
    message: AgentMessage  # 完整 assistant 消息
    tool_results: list[dict]  # 本轮工具结果
    usage: dict | None = None  # LLM token 用量


@dataclass
class MessageStart:
    """新消息开始（user / assistant / tool）"""

    message: AgentMessage


@dataclass
class MessageUpdate:
    """流式增量"""

    message: AgentMessage
    delta: str
    delta_type: str  # "text_delta" | "thinking_delta"


@dataclass
class MessageEnd:
    """消息结束"""

    message: AgentMessage


@dataclass
class ToolStart:
    """工具开始执行"""

    tool_call_id: str
    tool_name: str
    args: dict


@dataclass
class ToolUpdate:
    """工具流式输出"""

    tool_call_id: str
    tool_name: str
    partial_result: dict


@dataclass
class ToolEnd:
    """工具执行结束（成功含 result，失败 is_error=True）"""

    tool_call_id: str
    tool_name: str
    result: AgentToolResult
    is_error: bool


@dataclass
class RetryStart:
    """LLM 调用重试开始"""

    attempt: int
    error: str


@dataclass
class RetryEnd:
    """LLM 调用重试结束"""

    attempt: int
    error: str


# 联合类型（用于类型标注，运行时 isinstance 分派）
# Python 3.10+ 支持 `X | Y` 联合类型语法
AgentEvent = (
    BeforeAgentStart
    | AgentStart
    | AgentEnd
    | TurnStart
    | TurnEnd
    | MessageStart
    | MessageUpdate
    | MessageEnd
    | ToolStart
    | ToolUpdate
    | ToolEnd
    | RetryStart
    | RetryEnd
)
