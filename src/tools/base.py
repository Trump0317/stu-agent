"""BaseTool + ToolResult — 工具抽象基类"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ToolResult:
    """工具执行结果

    Attributes:
        success: 执行是否成功
        content: 返回给 LLM 的文本
        error: 错误信息（成功时为 None）
    """

    success: bool
    content: str
    error: str | None = None


class BaseTool(ABC):
    """工具抽象基类

    所有工具必须继承此类，定义 name/description/parameters 并实现 execute。

    Attributes:
        name: 工具唯一名称（LLM 调用用）
        description: 工具描述（LLM 可见）
        parameters: JSON Schema 格式的参数定义
    """

    name: str
    description: str
    parameters: dict

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # 强制子类定义类属性
        if not hasattr(cls, "name") or cls.name is ...:
            raise TypeError(f"{cls.__name__} 必须定义 'name' 类属性")
        if not hasattr(cls, "description") or cls.description is ...:
            raise TypeError(f"{cls.__name__} 必须定义 'description' 类属性")
        if not hasattr(cls, "parameters") or cls.parameters is ...:
            raise TypeError(f"{cls.__name__} 必须定义 'parameters' 类属性")

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """执行工具

        Args:
            **kwargs: 工具参数（从 LLM tool_call arguments 解包）

        Returns:
            ToolResult: 执行结果
        """
        ...

    def to_openai_schema(self) -> dict:
        """转为 OpenAI function calling 格式

        Returns:
            {"type": "function", "function": {"name": ..., "description": ..., "parameters": ...}}
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
