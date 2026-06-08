"""LLM 工厂路由 — 单元测试

审核人: Trump
审核日期: 2026-06-07
审核状态: [已通过]
"""

from unittest.mock import MagicMock, patch

import pytest

from src.config.settings import LLMConfig
from src.llm.factory import LLMFactory


class TestLLMFactoryErrors:
    """错误处理测试（不依赖 B5/B6）"""

    def test_empty_provider_raises(self):
        """空字符串 provider 抛出 ValueError"""
        config = LLMConfig(provider="", model="test", api_key="sk-test")
        with pytest.raises(ValueError, match="provider"):
            LLMFactory.create(config)

    def test_unknown_provider_raises(self):
        """不支持的 provider 抛出 ValueError"""
        config = LLMConfig(provider="unknown-vendor", model="test", api_key="sk-test")
        with pytest.raises(ValueError, match="不支持的.*provider"):
            LLMFactory.create(config)

    def test_whitespace_only_provider_raises(self):
        """只有空格的 provider 视为空"""
        config = LLMConfig(provider="   ", model="test", api_key="sk-test")
        with pytest.raises(ValueError, match="provider"):
            LLMFactory.create(config)


class TestLLMFactoryRouting:
    """路由逻辑测试（Mock 延迟导入，不依赖 B5/B6 文件）"""

    @pytest.fixture
    def deepseek_config(self) -> LLMConfig:
        return LLMConfig(
            provider="deepseek",
            model="deepseek-chat",
            api_key="sk-test",
            base_url="https://api.deepseek.com/v1",
        )

    @pytest.fixture
    def qwen_config(self) -> LLMConfig:
        return LLMConfig(
            provider="qwen",
            model="qwen-turbo",
            api_key="sk-test",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

    @pytest.fixture
    def openai_config(self) -> LLMConfig:
        return LLMConfig(
            provider="openai",
            model="gpt-4o-mini",
            api_key="sk-test",
            base_url="https://api.openai.com/v1",
        )

    def test_deepseek_routes_to_compat(self, deepseek_config):
        """deepseek 路由到 OpenAICompatProvider"""
        with patch("importlib.import_module") as mock_import:
            mock_module = MagicMock()
            mock_import.return_value = mock_module
            LLMFactory.create(deepseek_config)
            mock_import.assert_called_once_with("src.llm.openai_compat")

    def test_qwen_routes_to_compat(self, qwen_config):
        """qwen 路由到 OpenAICompatProvider"""
        with patch("importlib.import_module") as mock_import:
            mock_module = MagicMock()
            mock_import.return_value = mock_module
            LLMFactory.create(qwen_config)
            mock_import.assert_called_once_with("src.llm.openai_compat")

    def test_openai_routes_to_native(self, openai_config):
        """openai 路由到 OpenAINativeProvider"""
        with patch("importlib.import_module") as mock_import:
            mock_module = MagicMock()
            mock_import.return_value = mock_module
            LLMFactory.create(openai_config)
            mock_import.assert_called_once_with("src.llm.openai_provider")

    def test_provider_case_insensitive(self):
        """provider 名称大小写不敏感"""
        config = LLMConfig(provider="DeepSeek", model="test", api_key="sk-test",
                           base_url="https://api.deepseek.com/v1")
        with patch("importlib.import_module") as mock_import:
            mock_module = MagicMock()
            mock_import.return_value = mock_module
            LLMFactory.create(config)
            mock_import.assert_called_once_with("src.llm.openai_compat")

    def test_provider_with_extra_spaces(self):
        """provider 前后空格被去除"""
        config = LLMConfig(provider="  qwen  ", model="test", api_key="sk-test",
                           base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")
        with patch("importlib.import_module") as mock_import:
            mock_module = MagicMock()
            mock_import.return_value = mock_module
            LLMFactory.create(config)
            mock_import.assert_called_once_with("src.llm.openai_compat")
