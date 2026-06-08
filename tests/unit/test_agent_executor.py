"""ToolExecutor — 单元测试

审核人: Trump
审核日期: 2026-06-07
审核状态: [已通过]
"""

from unittest.mock import MagicMock

import pytest

from src.agent.events import ToolEnd, ToolStart
from src.agent.executor import execute_tool, execute_tools
from src.agent.types import AgentToolResult


class MockRegistry:
    """Mock ToolRegistry（D1 未实现，用此占位）"""

    def __init__(self, results: dict[str, str] | None = None, errors: dict[str, Exception] | None = None):
        self._results = results or {}
        self._errors = errors or {}

    async def execute(self, name: str, args: dict) -> str:
        if name in self._errors:
            raise self._errors[name]
        return self._results.get(name, f"default result for {name}")


class TestExecuteTool:
    """单工具执行测试"""

    @pytest.mark.asyncio
    async def test_basic_execution(self):
        """正常执行返回成功结果"""
        registry = MockRegistry({"read_file": "file content"})
        result = await execute_tool(
            tool_call_id="call_1",
            tool_name="read_file",
            args={"path": "/tmp/a.txt"},
            tool_registry=registry,
        )
        assert isinstance(result, AgentToolResult)
        assert result.content == ["file content"]
        assert result.is_error is False

    @pytest.mark.asyncio
    async def test_tool_error_returns_error_result(self):
        """工具抛异常 → 返回 is_error=True 的结果，不向上抛"""
        registry = MockRegistry(errors={"bad_tool": ValueError("something wrong")})
        result = await execute_tool(
            tool_call_id="call_1",
            tool_name="bad_tool",
            args={},
            tool_registry=registry,
        )
        assert result.is_error is True
        assert "something wrong" in result.content[0]

    @pytest.mark.asyncio
    async def test_before_hook_block(self):
        """before_hook 返回 block → 不执行工具，返回 blocked 消息"""
        registry = MockRegistry({"read_file": "should not be called"})
        registry.execute = MagicMock()  # 用于验证未被调用

        def before_hook(ctx):
            return {"block": True, "reason": "permission denied"}

        result = await execute_tool(
            tool_call_id="call_1",
            tool_name="read_file",
            args={},
            tool_registry=registry,
            before_hook=before_hook,
        )
        assert result.is_error is True
        assert "Blocked" in result.content[0]
        assert "permission denied" in result.content[0]
        registry.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_before_hook_allow(self):
        """before_hook 返回 None → 正常执行"""
        registry = MockRegistry({"read_file": "content"})

        def before_hook(ctx):
            return None

        result = await execute_tool(
            tool_call_id="call_1",
            tool_name="read_file",
            args={},
            tool_registry=registry,
            before_hook=before_hook,
        )
        assert result.is_error is False
        assert result.content == ["content"]

    @pytest.mark.asyncio
    async def test_after_hook_modify_result(self):
        """after_hook 可修改结果"""
        registry = MockRegistry({"read_file": "original"})

        def after_hook(ctx):
            return {"content": ["modified"], "is_error": False}

        result = await execute_tool(
            tool_call_id="call_1",
            tool_name="read_file",
            args={},
            tool_registry=registry,
            after_hook=after_hook,
        )
        assert result.content == ["modified"]

    @pytest.mark.asyncio
    async def test_on_update_events(self):
        """验证 ToolStart / ToolEnd 事件通过 on_update 回调触发"""
        events = []
        registry = MockRegistry({"search": "found"})

        def on_update(event):
            events.append(event)

        result = await execute_tool(
            tool_call_id="tc_1",
            tool_name="search",
            args={"q": "test"},
            tool_registry=registry,
            on_update=on_update,
        )
        assert len(events) == 2
        assert isinstance(events[0], ToolStart)
        assert events[0].tool_name == "search"
        assert isinstance(events[1], ToolEnd)
        assert events[1].tool_name == "search"
        assert events[1].is_error is False


class TestExecuteTools:
    """多工具顺序执行测试"""

    @pytest.mark.asyncio
    async def test_sequential_execution(self):
        """多个工具按顺序执行，结果列表与输入顺序一致"""
        registry = MockRegistry({"tool_a": "result A", "tool_b": "result B", "tool_c": "result C"})

        def _tc(id, name, args):
            tc = MagicMock()
            tc.id = id
            tc.name = name
            tc.arguments = args
            return tc

        results = await execute_tools(
            tool_calls=[
                _tc("1", "tool_a", {"x": 1}),
                _tc("2", "tool_b", {"x": 2}),
                _tc("3", "tool_c", {"x": 3}),
            ],
            tool_registry=registry,
        )
        assert len(results) == 3
        assert results[0].content == ["result A"]
        assert results[1].content == ["result B"]
        assert results[2].content == ["result C"]

    @pytest.mark.asyncio
    async def test_mixed_success_and_error(self):
        """部分成功部分失败，结果列表保留顺序"""
        registry = MockRegistry(
            {"tool_a": "ok"},
            errors={"tool_b": RuntimeError("fail")},
        )

        def _tc(id, name, args):
            tc = MagicMock()
            tc.id = id
            tc.name = name
            tc.arguments = args
            return tc

        results = await execute_tools(
            tool_calls=[
                _tc("1", "tool_a", {}),
                _tc("2", "tool_b", {}),
            ],
            tool_registry=registry,
        )
        assert len(results) == 2
        assert results[0].is_error is False
        assert results[1].is_error is True

    @pytest.mark.asyncio
    async def test_empty_tool_calls(self):
        """空工具列表返回空结果列表"""
        results = await execute_tools(tool_calls=[], tool_registry=MockRegistry())
        assert results == []

    @pytest.mark.asyncio
    async def test_with_before_hook_block(self):
        """before_hook block 时该工具不执行，不影响其他工具"""
        registry = MockRegistry({"tool_a": "ok", "tool_b": "ok"})
        registry.execute = MagicMock(return_value="ok")

        def before_hook(ctx):
            return {"block": True, "reason": "no"}

        def _tc(id, name, args):
            tc = MagicMock()
            tc.id = id
            tc.name = name
            tc.arguments = args
            return tc

        results = await execute_tools(
            tool_calls=[
                _tc("1", "tool_a", {}),
                _tc("2", "tool_b", {}),
            ],
            tool_registry=registry,
            before_hook=before_hook,
        )
        assert len(results) == 2
        assert results[0].is_error is True  # blocked
        assert results[1].is_error is True  # also blocked (same hook)
        # execute should not be called since both are blocked
        assert registry.execute.call_count == 0

    @pytest.mark.asyncio
    async def test_with_on_update(self):
        """on_update 回调为每个工具触发 ToolStart/ToolEnd"""
        events = []
        registry = MockRegistry({"a": "A", "b": "B"})

        def on_update(event):
            events.append(event)

        def _tc(id, name, args):
            tc = MagicMock()
            tc.id = id
            tc.name = name
            tc.arguments = args
            return tc

        await execute_tools(
            tool_calls=[
                _tc("1", "a", {}),
                _tc("2", "b", {}),
            ],
            tool_registry=registry,
            on_update=on_update,
        )
        # 每个工具触发 ToolStart + ToolEnd = 4 个事件
        assert len(events) == 4
        assert isinstance(events[0], ToolStart)
        assert isinstance(events[1], ToolEnd)
        assert isinstance(events[2], ToolStart)
        assert isinstance(events[3], ToolEnd)
