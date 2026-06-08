"""文件读写工具"""

from pathlib import Path

from src.tools.base import BaseTool, ToolResult


class ReadFileTool(BaseTool):
    """读取文件内容"""

    name = "read_file"
    description = "读取指定路径的文件内容，返回文件全文"
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "文件路径",
            },
        },
        "required": ["path"],
    }

    async def execute(self, path: str) -> ToolResult:
        p = Path(path)
        if not p.exists():
            return ToolResult(success=False, content="", error=f"文件不存在: {path}")
        try:
            content = p.read_text(encoding="utf-8")
            return ToolResult(success=True, content=content)
        except Exception as e:
            return ToolResult(success=False, content="", error=str(e))


class WriteFileTool(BaseTool):
    """写入内容到文件"""

    name = "write_file"
    description = "将指定内容写入文件，如果文件已存在则覆盖"
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "文件路径",
            },
            "content": {
                "type": "string",
                "description": "要写入的内容",
            },
        },
        "required": ["path", "content"],
    }

    async def execute(self, path: str, content: str) -> ToolResult:
        try:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return ToolResult(success=True, content=f"文件已写入: {path}")
        except Exception as e:
            return ToolResult(success=False, content="", error=str(e))
