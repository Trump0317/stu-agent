### M2：工具 Agent `[x]`

> 目标：Agent 可调用基础工具，LLM 返回 tool_call 时自动执行并喂回结果。

| # | 任务 | 状态 |
|---|------|------|
| M2-1 | BaseTool + ToolResult + ToolRegistry | [x] |
| M2-2 | ReadFileTool | [x] |
| M2-3 | WriteFileTool | [x] |
| M2-4 | BashTool（30s 超时） | [x] |
| M2-5 | 工具集成测试（Mock LLM + AgentSession） | [x] |
| M2-6 | Agent loop 无效 tool_call 过滤 | [x] |
| M2-7 | DeepSeek content=None 兼容 | [x] |

##### M2-1：BaseTool + ToolRegistry `[x]`

- **目标**：定义工具基类和注册中心，Agent 通过 ToolRegistry 调用工具。

- **文件**：`src/tools/base.py`, `src/tools/registry.py`
- **实现**：`ToolResult(success, content, error)`, `BaseTool(name, description, parameters)`, `ToolRegistry(register, execute, get_schemas)`
- **验收**：execute 返回 ToolResult，不存在的工具抛 ValueError

##### M2-2：ReadFileTool `[x]`

- **目标**：实现文件读取工具，LLM 可读取项目文件内容。

- **文件**：`src/tools/file_tools.py`
- **实现**：`path` → 文件内容，不存在时 success=False
- **测试**：`pytest -q tests/unit/test_file_tools.py`

##### M2-3：WriteFileTool `[x]`

- **目标**：实现文件写入工具，LLM 可将内容写入磁盘。

- **文件**：`src/tools/file_tools.py`
- **实现**：`path + content` → 写入文件，覆盖已有
- **测试**：`pytest -q tests/unit/test_file_tools.py`

##### M2-4：BashTool `[x]`

- **目标**：实现 Shell 命令执行工具，30s 超时，捕获 stdout/stderr。

- **文件**：`src/tools/bash_tool.py`
- **实现**：`command` → 30s 超时执行，退出码 != 0 时 success=False
- **测试**：`pytest -q tests/unit/test_bash_tool.py`

##### M2-5：工具集成测试 `[x]`

- **目标**：验证 AgentSession + 真实工具 + MockLLM 的完整工具调用链路。

- **文件**：`tests/integration/test_agent_session_tools.py`
- **测试**：bash echo → 返回正确 / 失败命令 is_error / read_file 读取 / write_file 后读回 / 多工具单轮
- **测试**：`pytest -q tests/integration/test_agent_session_tools.py`

##### M2-6：无效 tool_call 过滤 `[x]`

- **目标**：过滤 DeepSeek 偶发的 id=null / name="" 无效 tool_call。

- **文件**：`src/agent/loop.py`
- **实现**：过滤 `id=None, name=""` 的无效 tool_call（DeepSeek 偶发）
- **验收**：无效 tool_call 不执行，不报 400

##### M2-7：content=None 兼容 `[x]`

- **目标**：兼容 DeepSeek 不接受 content=null 的限制。

- **文件**：`src/agent/agent.py` (`_to_llm_messages`)
- **实现**：assistant + tool_calls 时 `content=None` → `""`，避免 DeepSeek 400

**验收**：
- Agent 可调用 read_file 读取文件
- Agent 可调用 write_file 写入文件
- Agent 可调用 bash 执行命令
- 工具异常不中断对话
- 无效 tool_call 被过滤
