"""LLM 抽象接口

定义 LLM Provider 必须实现的抽象基类 BaseLLM。
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from src.llm.models import LLMResponse


class BaseLLM(ABC):
    """LLM Provider 抽象基类

    所有 LLM Provider 必须实现 stream 方法。
    """

    @abstractmethod
    async def stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> AsyncIterator[LLMResponse]:
        """流式调用 LLM

        Args:
            messages: OpenAI 格式的对话历史
            tools: OpenAI 格式的工具定义列表（可选）

        Yields:
            LLMResponse: 流式响应块（文本增量或工具调用）
        """
        ...
