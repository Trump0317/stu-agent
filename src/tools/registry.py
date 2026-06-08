"""ToolRegistry — 工具注册中心

管理工具注册、查找、执行。execute 同步调用异步工具（内部 asyncio.run 桥接）。
"""

import asyncio

from src.tools.base import BaseTool


class ToolRegistry:
    """工具注册中心

    用法：
        reg = ToolRegistry()
        reg.register(SearchTool())
        result = reg.execute("search", {"query": "test"})
    """

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """注册工具

        Args:
            tool: BaseTool 子类实例

        Raises:
            TypeError: tool 不是 BaseTool 实例
            ValueError: 同名工具已注册
        """
        if not isinstance(tool, BaseTool):
            raise TypeError(f"必须注册 BaseTool 子类实例，收到: {type(tool)}")
        if tool.name in self._tools:
            raise ValueError(f"工具 '{tool.name}' 已注册")
        self._tools[tool.name] = tool

    def get_schemas(self) -> list[dict]:
        """返回所有工具的 OpenAI function schema 列表"""
        return [t.to_openai_schema() for t in self._tools.values()]

    async def execute(self, name: str, args: dict) -> "ToolResult":
        """执行指定工具（异步）

        Args:
            name: 工具名称
            args: 工具参数字典

        Returns:
            ToolResult 对象（含 success / content / error）

        Raises:
            ValueError: 工具不存在
        """
        tool = self._tools.get(name)
        if tool is None:
            raise ValueError(f"工具 '{name}' 不存在")

        try:
            return await tool.execute(**args)
        except Exception as e:
            from src.tools.base import ToolResult
            return ToolResult(success=False, content=f"工具执行错误: {e}", error=str(e))

    def list_tools(self) -> list[str]:
        """列出所有已注册工具名"""
        return list(self._tools.keys())
