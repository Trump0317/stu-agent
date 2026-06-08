"""OpenAI Native Provider

适配 OpenAI 原生 API（api.openai.com）。
与 OpenAICompatProvider 共享 parse_openai_stream() 解析流式响应。
"""

from openai import AsyncOpenAI

from src.config.settings import LLMConfig
from src.llm.base import BaseLLM
from src.llm.stream_parser import parse_openai_stream


class OpenAINativeProvider(BaseLLM):
    """OpenAI 原生 API Provider"""

    def __init__(self, config: LLMConfig) -> None:
        self.model = config.model
        self.client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url or "https://api.openai.com/v1",
        )

    async def stream(self, messages: list[dict], tools: list[dict] | None = None):
        """流式调用 LLM

        Args:
            messages: OpenAI 格式的对话历史
            tools: 工具定义列表（可选）

        Yields:
            LLMResponse: 流式响应块
        """
        kwargs: dict = dict(
            model=self.model,
            messages=messages,
            stream=True,
        )
        if tools:
            kwargs["tools"] = tools

        stream = await self.client.chat.completions.create(**kwargs)
        async for response in parse_openai_stream(stream):
            yield response
