"""LLM 数据模型

定义 LLM 交互的核心数据结构：ToolCall（工具调用）和 LLMResponse（流式响应）。

纯 dataclass，零外部依赖。
"""

from dataclasses import dataclass, field


@dataclass
class ToolCall:
    """LLM 返回的工具调用"""

    id: str          # 工具调用唯一 ID（OpenAI 格式）
    name: str        # 工具名称
    arguments: dict  # 工具参数（已解析为 dict）


@dataclass
class LLMResponse:
    """LLM 流式响应块

    有两种模式：
    - 文本模式：text 有值，is_tool_call=False
    - 工具调用模式：tool_calls 有值，is_tool_call=True
    """

    text: str = ""                         # 文本增量
    tool_calls: list[ToolCall] = field(default_factory=list)  # 工具调用列表
    is_tool_call: bool = False             # 是否为工具调用响应
    finish_reason: str = ""                # stop | tool_calls | length
    usage: dict | None = None              # token 使用统计
