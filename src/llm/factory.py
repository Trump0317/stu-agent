"""LLM 工厂路由

根据配置中的 provider 字段，延迟导入并创建对应的 LLM Provider 实例。
"""

import importlib

from src.config.settings import LLMConfig
from src.llm.base import BaseLLM


class LLMFactory:
    """LLM Provider 工厂

    路由规则：
    - deepseek / qwen → OpenAICompatProvider
    - openai           → OpenAINativeProvider
    """

    # provider → (module_path, class_name)
    _provider_map: dict[str, tuple[str, str]] = {
        "deepseek": ("src.llm.openai_compat", "OpenAICompatProvider"),
        "qwen": ("src.llm.openai_compat", "OpenAICompatProvider"),
        "openai": ("src.llm.openai_provider", "OpenAINativeProvider"),
    }

    @classmethod
    def create(cls, config: LLMConfig) -> BaseLLM:
        """根据配置创建 LLM Provider 实例

        Args:
            config: LLM 配置（provider, model, api_key, base_url）

        Returns:
            BaseLLM 实例

        Raises:
            ValueError: provider 为空或不支持
        """
        provider = config.provider.strip().lower()

        if not provider:
            raise ValueError("缺少必填配置: llm.provider")

        if provider not in cls._provider_map:
            raise ValueError(f"不支持的 LLM provider: {config.provider}")

        module_path, class_name = cls._provider_map[provider]
        module = importlib.import_module(module_path)
        provider_class = getattr(module, class_name)
        return provider_class(config)
