"""OpenAICompatProvider — 单元测试

审核人: Trump
审核日期: 2026-06-07
审核状态: [已通过]
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config.settings import LLMConfig
from src.llm.models import LLMResponse
from src.llm.openai_compat import OpenAICompatProvider


class TestOpenAICompatProviderInit:
    """初始化测试"""

    def test_client_configured_with_config(self):
        """AsyncOpenAI 客户端使用 LLMConfig 参数创建"""
        config = LLMConfig(
            provider="deepseek",
            model="deepseek-chat",
            api_key="sk-test-key",
            base_url="https://api.deepseek.com/v1",
        )

        with patch("src.llm.openai_compat.AsyncOpenAI") as mock_client_cls:
            OpenAICompatProvider(config)
            mock_client_cls.assert_called_once_with(
                api_key="sk-test-key",
                base_url="https://api.deepseek.com/v1",
            )

    def test_model_stored_from_config(self):
        """model 从 LLMConfig 读取，不硬编码"""
        config = LLMConfig(
            provider="qwen",
            model="qwen-turbo",
            api_key="sk-test",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

        with patch("src.llm.openai_compat.AsyncOpenAI"):
            provider = OpenAICompatProvider(config)
            assert provider.model == "qwen-turbo"


class TestOpenAICompatProviderStream:
    """stream() 方法测试"""

    @pytest.fixture
    def config(self) -> LLMConfig:
        return LLMConfig(
            provider="deepseek",
            model="deepseek-chat",
            api_key="sk-test",
            base_url="https://api.deepseek.com/v1",
        )

    @pytest.fixture
    def messages(self) -> list[dict]:
        return [{"role": "user", "content": "你好"}]

    @pytest.mark.asyncio
    async def test_passes_model_messages_to_api(self, config, messages):
        """stream() 正确传递 model 和 messages 到 API"""
        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = []

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_stream)

        with patch("src.llm.openai_compat.AsyncOpenAI", return_value=mock_client):
            provider = OpenAICompatProvider(config)
            async for _ in provider.stream(messages):
                pass

        mock_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "deepseek-chat"
        assert call_kwargs["messages"] == messages
        assert call_kwargs["stream"] is True

    @pytest.mark.asyncio
    async def test_passes_tools_to_api(self, config, messages):
        """有 tools 时传递到 API"""
        tools = [{"type": "function", "function": {"name": "search", "parameters": {}}}]
        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = []

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_stream)

        with patch("src.llm.openai_compat.AsyncOpenAI", return_value=mock_client):
            provider = OpenAICompatProvider(config)
            async for _ in provider.stream(messages, tools=tools):
                pass

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["tools"] == tools

    @pytest.mark.asyncio
    async def test_stream_without_tools(self, config, messages):
        """无 tools 时不传递 tools 参数"""
        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = []

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_stream)

        with patch("src.llm.openai_compat.AsyncOpenAI", return_value=mock_client):
            provider = OpenAICompatProvider(config)
            async for _ in provider.stream(messages):
                pass

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert "tools" not in call_kwargs

    @pytest.mark.asyncio
    async def test_api_error_propagates(self, config, messages):
        """API 异常向上传播，不吞没"""
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=RuntimeError("API connection failed")
        )

        with patch("src.llm.openai_compat.AsyncOpenAI", return_value=mock_client):
            provider = OpenAICompatProvider(config)
            with pytest.raises(RuntimeError, match="API connection failed"):
                async for _ in provider.stream(messages):
                    pass

    @pytest.mark.asyncio
    async def test_yields_llm_response_from_stream(self, config, messages):
        """集成 parse_openai_stream：流式 chunk 转换为 LLMResponse"""
        # 构造一个返回文本的 mock stream
        from types import SimpleNamespace

        mock_chunk = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    index=0,
                    delta=SimpleNamespace(content="你好"),
                    finish_reason="stop",
                )
            ]
        )
        mock_stream = MagicMock()
        mock_stream.__aiter__.return_value = [mock_chunk]

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_stream)

        with patch("src.llm.openai_compat.AsyncOpenAI", return_value=mock_client):
            provider = OpenAICompatProvider(config)
            responses = [r async for r in provider.stream(messages)]

        assert len(responses) == 1
        assert isinstance(responses[0], LLMResponse)
        assert responses[0].text == "你好"
        assert responses[0].finish_reason == "stop"


class TestOpenAICompatProviderBaseUrl:
    """base_url 由 LLMConfig 控制，不硬编码"""

    def test_empty_base_url_passthrough(self):
        """base_url 为空字符串时直接透传，不在 Provider 层做默认值"""
        config = LLMConfig(
            provider="deepseek",
            model="deepseek-chat",
            api_key="sk-test",
            base_url="",
        )
        with patch("src.llm.openai_compat.AsyncOpenAI") as mock_client_cls:
            OpenAICompatProvider(config)
            mock_client_cls.assert_called_once_with(
                api_key="sk-test",
                base_url="",
            )


class TestOpenAICompatProviderToolCalls:
    """工具调用集成测试"""

    @pytest.fixture
    def config(self) -> LLMConfig:
        return LLMConfig(
            provider="deepseek",
            model="deepseek-chat",
            api_key="sk-test",
            base_url="https://api.deepseek.com/v1",
        )

    @pytest.fixture
    def messages(self) -> list[dict]:
        return [{"role": "user", "content": "读文件 /tmp/a.txt"}]

    @pytest.mark.asyncio
    async def test_tool_call_integration(self, config, messages):
        """跨 chunk 拼接的工具调用 → 最终响应包含完整 ToolCall"""
        from types import SimpleNamespace

        chunks = [
            SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        index=0,
                        delta=SimpleNamespace(
                            content=None,
                            tool_calls=[
                                SimpleNamespace(
                                    index=0,
                                    id="call_x",
                                    function=SimpleNamespace(
                                        name="read_file",
                                        arguments='{"path":',
                                    ),
                                )
                            ],
                        ),
                        finish_reason=None,
                    )
                ]
            ),
            SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        index=0,
                        delta=SimpleNamespace(
                            content=None,
                            tool_calls=[
                                SimpleNamespace(
                                    index=0,
                                    id="call_x",
                                    function=SimpleNamespace(
                                        name=None,
                                        arguments='"/tmp/a.txt"}',
                                    ),
                                )
                            ],
                        ),
                        finish_reason=None,
                    )
                ]
            ),
            SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        index=0,
                        delta=SimpleNamespace(content=None),
                        finish_reason="tool_calls",
                    )
                ]
            ),
        ]
        mock_stream = MagicMock()
        mock_stream.__aiter__.return_value = chunks

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_stream)

        with patch("src.llm.openai_compat.AsyncOpenAI", return_value=mock_client):
            provider = OpenAICompatProvider(config)
            responses = [r async for r in provider.stream(messages)]

        assert len(responses) == 1
        assert responses[0].is_tool_call is True
        assert len(responses[0].tool_calls) == 1
        tc = responses[0].tool_calls[0]
        assert tc.id == "call_x"
        assert tc.name == "read_file"
        assert tc.arguments == {"path": "/tmp/a.txt"}
