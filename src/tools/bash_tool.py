"""Bash 命令执行工具"""

import subprocess

from src.tools.base import BaseTool, ToolResult


class BashTool(BaseTool):
    """Bash 命令执行工具"""

    name = "bash"
    description = "执行 Bash 命令。参数 command: 要执行的命令字符串"

    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "要执行的 Bash 命令",
            },
        },
        "required": ["command"],
    }

    async def execute(self, command: str = "") -> ToolResult:
        if not command or not command.strip():
            return ToolResult(success=False, content="", error="command 不能为空")

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = result.stdout.strip() or result.stderr.strip() or "(无输出)"
            # 如果命令执行失败，标记为错误
            if result.returncode != 0:
                return ToolResult(
                    success=False,
                    content=output,
                    error=f"退出码 {result.returncode}",
                )
            return ToolResult(success=True, content=output)
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, content="", error="命令执行超时（30秒）")
        except Exception as e:
            return ToolResult(success=False, content="", error=str(e))
