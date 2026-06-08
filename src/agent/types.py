"""Agent 类型定义

对标 pi types.ts，定义 Agent 层所有纯数据结构：
AgentState, AgentContext, AgentTool, AgentMessage, AgentLoopConfig 等。

纯 dataclass，零外部依赖。
"""

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class AgentToolResult:
    """工具执行结果

    Attributes:
        content: 返回给 LLM 的文本内容列表
        details: 结构化详情（日志/UI 渲染）
        is_error: 是否为错误结果
    """

    content: list[str]
    details: dict | None = None
    is_error: bool = False


@dataclass
class AgentTool:
    """工具定义

    Attributes:
        name: 工具唯一名称（LLM 调用用）
        label: 人类可读标签（UI 显示）
        description: 工具描述（LLM 可见）
        parameters: JSON Schema 格式的参数定义
    """

    name: str
    label: str
    description: str
    parameters: dict


@dataclass
class AgentMessage:
    """Agent 对话消息

    对标 OpenAI 消息格式，支持四种角色：
    - system: 系统提示词
    - user: 用户输入
    - assistant: LLM 响应（可含 tool_calls，此时 content 可为 None）
    - tool: 工具执行结果

    Attributes:
        role: 消息角色
        content: 消息文本内容（assistant 带 tool_calls 时可为 None）
        tool_call_id: tool 角色时的调用 ID
        tool_calls: assistant 角色时的工具调用列表
    """

    role: str
    content: str | None
    tool_call_id: str | None = None
    tool_calls: list[dict] | None = None


@dataclass
class AgentState:
    """Agent 运行时状态

    Attributes:
        system_prompt: 系统提示词
        tools: 可用工具列表
        messages: 对话历史
        is_streaming: 是否正在流式响应（只读）
        error_message: 最近错误信息（只读）
    """

    system_prompt: str
    tools: list[AgentTool] = field(default_factory=list)
    messages: list[AgentMessage] = field(default_factory=list)
    is_streaming: bool = False
    error_message: str | None = None


@dataclass
class AgentContext:
    """loop 入参快照

    由 Agent 在 prompt() 时从 AgentState 构建，传递给 agent_loop。
    loop 不修改入参，返回新 context。

    Attributes:
        system_prompt: 系统提示词
        messages: 当前对话历史
        tools: OpenAI 格式的工具定义列表（可选）
    """

    system_prompt: str
    messages: list[AgentMessage]
    tools: list[dict] | None = None


@dataclass
class AgentLoopConfig:
    """agent_loop 行为配置

    Attributes:
        model: 模型名称
        stream_fn: LLM 流式调用函数（桥接 BaseLLM）
        convert_to_llm: 将 AgentMessage 列表转为 OpenAI 格式
        transform_context: 发 LLM 前转换上下文（可选，用于 compaction 等）
        before_tool_call: 工具执行前 hook（可返回 {"block": True} 拦截）
        after_tool_call: 工具执行后 hook（可修改 result）
        max_tool_rounds: 单轮最大工具调用次数（默认 10）
        max_retries: LLM 调用最大重试次数（默认 2）
    """

    model: str
    stream_fn: Callable
    convert_to_llm: Callable
    transform_context: Callable | None = None
    before_tool_call: Callable | None = None
    after_tool_call: Callable | None = None
    max_tool_rounds: int = 5
    max_retries: int = 2
