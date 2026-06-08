"""BaseTool + ToolRegistry 单元测试

审核人: Trump
审核日期: 2026-06-07
审核状态: [已通过]
"""

import pytest
from src.tools.base import BaseTool, ToolResult
from src.tools.registry import ToolRegistry


class TestToolResult:
    def test_success_result(self):
        r = ToolResult(success=True, content="done")
        assert r.success is True
        assert r.content == "done"
        assert r.error is None

    def test_error_result(self):
        r = ToolResult(success=False, content="", error="not found")
        assert r.success is False
        assert r.error == "not found"

    def test_default_values(self):
        r = ToolResult(success=True, content="ok")
        assert r.error is None


class TestBaseTool:
    def test_to_openai_schema(self):
        """to_openai_schema 返回合法 OpenAI function 格式"""

        class MyTool(BaseTool):
            name = "search"
            description = "搜索文档"
            parameters = {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            }

            async def execute(self, **kwargs):
                return ToolResult(success=True, content="result")

        tool = MyTool()
        schema = tool.to_openai_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "search"
        assert schema["function"]["description"] == "搜索文档"
        assert "parameters" in schema["function"]
        assert schema["function"]["parameters"]["type"] == "object"

    def test_missing_name_raises(self):
        """缺少 name 的 BaseTool 子类定义时抛 TypeError"""
        with pytest.raises(TypeError):
            class BadTool(BaseTool):
                description = "bad"
                async def execute(self, **kwargs):
                    return ToolResult(success=True, content="")

    def test_execute_is_abstract(self):
        """不实现 execute 无法实例化"""
        with pytest.raises(TypeError):
            BaseTool()


class ToolA(BaseTool):
    name = "tool_a"
    description = "A tool"
    parameters = {"type": "object", "properties": {}}

    async def execute(self, **kwargs):
        return ToolResult(success=True, content="a")


class ToolB(BaseTool):
    name = "tool_b"
    description = "B tool"
    parameters = {"type": "object", "properties": {}}

    async def execute(self, **kwargs):
        return ToolResult(success=True, content="b")


class FailingTool(BaseTool):
    name = "fail"
    description = "always fails"
    parameters = {"type": "object", "properties": {}}

    async def execute(self, **kwargs):
        raise RuntimeError("oops")


class TestToolRegistry:
    def test_register_and_list(self):
        reg = ToolRegistry()
        reg.register(ToolA())
        reg.register(ToolB())
        assert reg.list_tools() == ["tool_a", "tool_b"]

    def test_register_duplicate_raises(self):
        reg = ToolRegistry()
        reg.register(ToolA())
        with pytest.raises(ValueError, match="已注册"):
            reg.register(ToolA())

    def test_register_non_tool_raises(self):
        """注册非 BaseTool 实例抛 TypeError"""
        reg = ToolRegistry()
        with pytest.raises(TypeError):
            reg.register("not a tool")

    @pytest.mark.asyncio
    async def test_execute_tool(self):
        reg = ToolRegistry()
        reg.register(ToolA())
        result = await reg.execute("tool_a", {"key": "val"})
        assert result.content == "a"
        assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_unknown_tool_raises(self):
        reg = ToolRegistry()
        with pytest.raises(ValueError, match="不存在"):
            await reg.execute("nope", {})

    @pytest.mark.asyncio
    async def test_execute_tool_exception_returns_error(self):
        """工具执行异常 → 返回错误字符串而非抛异常"""
        reg = ToolRegistry()
        reg.register(FailingTool())
        result = await reg.execute("fail", {})
        assert "错误" in result.content
        assert "oops" in result.content
        assert result.success is False

    def test_get_schemas(self):
        reg = ToolRegistry()
        reg.register(ToolA())
        reg.register(ToolB())
        schemas = reg.get_schemas()
        assert len(schemas) == 2
        names = [s["function"]["name"] for s in schemas]
        assert "tool_a" in names
        assert "tool_b" in names

    def test_get_schemas_empty(self):
        reg = ToolRegistry()
        assert reg.get_schemas() == []
