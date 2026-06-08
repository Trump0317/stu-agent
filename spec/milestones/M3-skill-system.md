### M3：Skill 系统 `[ ]`

> 目标：业务能力与基础工具解耦。Skill = YAML（system_prompt + 工具列表）。
> 通过系统提示词实现业务逻辑，不内置业务工具。

| # | 任务 | 状态 |
|---|------|------|
| M3-1 | Skill YAML 格式定义 + writing.yaml | [ ] |
| M3-2 | Skill 加载 + 工具注册 + prompt 拼装 | [ ] |
| M3-3 | Skill 单元测试 | [ ] |

##### M3-1：Skill YAML 格式定义

- **目标**：定义 Skill YAML 格式，创建 writing skill 作为示例。
- **文件**：`config/skills/writing.yaml`
- **实现**：

```yaml
name: writing
description: 模板驱动文档写作
tools:
  - read_file
  - write_file
  - bash
system_prompt: |
  你是写作助手...
  流程：
  1. read_file 读取模板
  2. 逐章节生成内容
  3. write_file 导出
```

- **验收**：YAML 可解析，tools 列表正确，prompt 长度 > 200 字符

##### M3-2：Skill 加载 + Agent 初始化流程

- **目标**：实现 Skill 加载函数和 Agent 初始化流程（按 Skill 注册工具 + 拼装 prompt）。
- **文件**：`src/skills/__init__.py`
- **实现**：
  - `load_skill(name) -> Skill`：从 `config/skills/` 加载 YAML
  - `list_skills() -> list[str]`：列出所有 skill
  - `build_system_prompt(skill, tools) -> str`：拼接 skill.system_prompt + 工具 schema 描述
- **实现**：
  1. `load_skill("writing")` → Skill 对象
  2. 遍历 `Skill.tools` → 实例化对应 BaseTool → `ToolRegistry.register()`
  3. `build_system_prompt(skill, tools)` → 传入 `Agent(system_prompt=...)`
  4. 创建 `AgentSession(agent, llm, tool_registry)`
- **验收**：根据 Skill 选择不同 tools → Agent 行为不同

##### M3-3：Skill 单元测试

- **目标**：验证 Skill 加载和 prompt 拼装的正确性。
- **文件**：`tests/unit/test_skills.py`
- **测试**：
  - `test_load_writing_skill`：YAML 可解析，字段正确
  - `test_list_skills`：列出所有 skill
  - `test_build_system_prompt`：输出含工具描述
  - `test_agent_with_skill`：Agent 初始化时按 Skill 注册工具
- **测试**：`pytest -q tests/unit/test_skills.py`

**验收**：
- `config/skills/writing.yaml` 可加载
- 根据 Skill.tools 自动注册对应 BaseTool
- `build_system_prompt()` 产出包含工具描述的完整 prompt
- 切换 Skill = 切换 Agent 行为
