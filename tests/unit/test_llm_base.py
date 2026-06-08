"""LLM 抽象接口 — 单元测试

审核人: Trump
审核日期: 2026-06-07
审核状态: [已通过]
"""

import pytest

from src.llm.base import BaseLLM
from src.llm.models import LLMResponse


class TestBaseLLM:
    """BaseLLM 抽象基类测试"""

    def test_cannot_instantiate_directly(self):
        """直接实例化抽象类应抛出 TypeError"""
        with pytest.raises(TypeError):
            BaseLLM()  # type: ignore[abstract]

    def test_subclass_without_stream_cannot_instantiate(self):
        """子类未实现 stream 方法时不可实例化"""

        class IncompleteProvider(BaseLLM):
            pass

        with pytest.raises(TypeError):
            IncompleteProvider()  # type: ignore[abstract]

    def test_subclass_with_stream_can_instantiate(self):
        """正确实现 stream 的子类可实例化"""

        class ValidProvider(BaseLLM):
            async def stream(self, messages, tools=None):
                yield LLMResponse(text="ok")

            # pragma: no cover — 仅为满足抽象方法签名

        provider = ValidProvider()
        assert isinstance(provider, BaseLLM)
