"""OpenAINativeProvider — 单元测试

审核人: Trump
审核日期: 2026-06-07
审核状态: [已通过]
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config.settings import LLMConfig
from src.llm.models import LLMResponse
from src.llm.openai_provider import OpenAINativeProvider


class TestOpenAINativeProviderInit:
    """初始化测试"""

    def test_client_configured_with_config(self):
        """AsyncOpenAI 使用 LLMConfig 显式 base_url 创建"""
        config = LLMConfig(
            provider="openai",
            model="gpt-4o-mini",
            api_key="sk-openai-key",
            base_url="https://api.openai.com/v1",
        )

        with patch("src.llm.openai_provider.AsyncOpenAI") as mock_client_cls:
            OpenAINativeProvider(config)
            mock_client_cls.assert_called_once_with(
                api_key="sk-openai-key",
                base_url="https://api.openai.com/v1",
            )

    def test_model_stored_from_config(self):
        """model 从 LLMConfig 读取"""
        config = LLMConfig(
            provider="openai",
            model="gpt-4o",
            api_key="sk-test",
            base_url="https://api.openai.com/v1",
        )

        with patch("src.llm.openai_provider.AsyncOpenAI"):
            provider = OpenAINativeProvider(config)
            assert provider.model == "gpt-4o"


class TestOpenAINativeProviderDefaultBaseUrl:
    """base_url 默认值测试（B6 与 B5 的唯一差异点）"""

    def test_defaults_to_openai_when_empty(self):
        """base_url 为空时，Provider 层默认使用 https://api.openai.com/v1"""
        config = LLMConfig(
            provider="openai",
            model="gpt-4o-mini",
            api_key="sk-test",
            base_url="",
        )

        with patch("src.llm.openai_provider.AsyncOpenAI") as mock:
            OpenAINativeProvider(config)
            mock.assert_called_once_with(
                api_key="sk-test",
                base_url="https://api.openai.com/v1",
            )


class TestOpenAINativeProviderStream:
    """stream() 方法测试"""

    @pytest.fixture
    def config(self) -> LLMConfig:
        return LLMConfig(
            provider="openai",
            model="gpt-4o-mini",
            api_key="sk-test",
            base_url="https://api.openai.com/v1",
        )

    @pytest.fixture
    def messages(self) -> list[dict]:
        return [{"role": "user", "content": "Hello"}]

    @pytest.mark.asyncio
    async def test_passes_params_to_api(self, config, messages):
        """stream() 传递 model, messages 到 API"""
        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = []

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_stream)

        with patch("src.llm.openai_provider.AsyncOpenAI", return_value=mock_client):
            provider = OpenAINativeProvider(config)
            async for _ in provider.stream(messages):
                pass

        mock_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "gpt-4o-mini"
        assert call_kwargs["messages"] == messages
        assert call_kwargs["stream"] is True

    @pytest.mark.asyncio
    async def test_passes_tools_to_api(self, config, messages):
        """有 tools 时精确传递到 API"""
        tools = [{"type": "function", "function": {"name": "search"}}]
        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = []

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_stream)

        with patch("src.llm.openai_provider.AsyncOpenAI", return_value=mock_client):
            provider = OpenAINativeProvider(config)
            async for _ in provider.stream(messages, tools=tools):
                pass

        mock_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["tools"] == tools

    @pytest.mark.asyncio
    async def test_stream_without_tools(self, config, messages):
        """无 tools 时不传递 tools 参数"""
        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = []

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_stream)

        with patch("src.llm.openai_provider.AsyncOpenAI", return_value=mock_client):
            provider = OpenAINativeProvider(config)
            async for _ in provider.stream(messages):
                pass

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert "tools" not in call_kwargs

    @pytest.mark.asyncio
    async def test_api_error_propagates(self, config, messages):
        """API 异常向上传播"""
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=RuntimeError("Auth failed")
        )

        with patch("src.llm.openai_provider.AsyncOpenAI", return_value=mock_client):
            provider = OpenAINativeProvider(config)
            with pytest.raises(RuntimeError, match="Auth failed"):
                async for _ in provider.stream(messages):
                    pass

    @pytest.mark.asyncio
    async def test_yields_llm_response(self, config, messages):
        """集成 parse_openai_stream：文本响应"""
        mock_chunk = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    index=0,
                    delta=SimpleNamespace(content="Hi"),
                    finish_reason="stop",
                )
            ]
        )
        mock_stream = MagicMock()
        mock_stream.__aiter__.return_value = [mock_chunk]

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_stream)

        with patch("src.llm.openai_provider.AsyncOpenAI", return_value=mock_client):
            provider = OpenAINativeProvider(config)
            responses = [r async for r in provider.stream(messages)]

        assert len(responses) == 1
        assert isinstance(responses[0], LLMResponse)
        assert responses[0].text == "Hi"


class TestOpenAINativeProviderToolCalls:
    """工具调用集成测试"""

    @pytest.fixture
    def config(self) -> LLMConfig:
        return LLMConfig(
            provider="openai",
            model="gpt-4o-mini",
            api_key="sk-test",
            base_url="https://api.openai.com/v1",
        )

    @pytest.fixture
    def messages(self) -> list[dict]:
        return [{"role": "user", "content": "search"}]

    @pytest.mark.asyncio
    async def test_tool_call_integration(self, config, messages):
        """跨 chunk 拼接的工具调用 → 最终响应包含完整 ToolCall"""
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
                                    id="tc_1",
                                    function=SimpleNamespace(
                                        name="search",
                                        arguments='{"query":',
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
                                    id="tc_1",
                                    function=SimpleNamespace(
                                        name=None,
                                        arguments='"hello"}',
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

        with patch("src.llm.openai_provider.AsyncOpenAI", return_value=mock_client):
            provider = OpenAINativeProvider(config)
            responses = [r async for r in provider.stream(messages)]

        assert len(responses) == 1
        assert responses[0].is_tool_call is True
        assert len(responses[0].tool_calls) == 1
        assert responses[0].tool_calls[0].name == "search"
        assert responses[0].tool_calls[0].arguments == {"query": "hello"}
