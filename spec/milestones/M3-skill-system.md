### M3：Skill 系统 `[x]`

> 目标：业务能力与基础工具解耦。参照 pi Agent Skills 标准，
> Skill = SKILL.md（YAML frontmatter + Markdown 正文）。
> 内置工具全局可用，Agent 行为由 system_prompt 决定。
> 自定义脚本通过 bash 执行，不注册为独立 Tool。

| # | 任务 | 状态 |
|---|------|------|
| M3-1 | SKILL.md 格式定义 + writing skill | [x] |
| M3-2 | Skill 加载 + prompt 拼装 + Agent 初始化 | [x] |
| M3-3 | Skill 单元测试 | [x] |

##### M3-1：SKILL.md 格式定义

- **目标**：遵循 Agent Skills 标准，定义 SKILL.md 格式，创建 writing skill。
- **文件**：`config/skills/writing/SKILL.md`
- **格式**：

```markdown
---
name: writing
description: 模板驱动文档写作（课程论文 / 实验报告）
---

# 写作助手

你是写作助手...
流程：
1. read_file 读取模板
2. 逐章节生成内容
3. bash scripts/format.sh 格式化
4. write_file 导出
```

- **设计要点**：
  - YAML frontmatter 仅含 `name` + `description`
  - Markdown 正文 = system_prompt（含自定义脚本的 bash 调用说明）
  - 无 `tools` 字段——内置工具全局可用
  - 自定义脚本放在 `scripts/` 目录，通过 bash 执行
- **验收**：SKILL.md 可解析，正文 > 200 字符

##### M3-2：Skill 加载 + Agent 初始化流程

- **目标**：加载 SKILL.md，拼装 system_prompt，创建 Agent。
- **文件**：`src/skills/__init__.py`
- **实现**：
  - `_parse_skill_md(path) -> (frontmatter, body)`：解析 YAML frontmatter + Markdown 正文
  - `load_skill(name) -> Skill | None`：加载 SKILL.md
  - `list_skills() -> list[str]`：扫描 `config/skills/*/SKILL.md`
  - `build_system_prompt(skill, registry) -> str`：拼接 system_prompt + 工具 schema
  - `create_agent_from_skill(name, llm) -> (Agent, ToolRegistry)`：创建 Agent
- **流程**：
  1. `load_skill("writing")` → Skill(name, description, system_prompt, dir)
  2. 注册全部内置工具（read_file, write_file, bash）到 ToolRegistry
  3. `build_system_prompt(skill, registry)` → 传入 `Agent(system_prompt=...)`
  4. 返回 Agent + ToolRegistry
- **验收**：不同 Skill 产出不同 system_prompt → Agent 行为不同

##### M3-3：Skill 单元测试

- **目标**：验证 SKILL.md 解析、prompt 拼装、Agent 初始化。
- **文件**：`tests/unit/test_skills.py`
- **测试**：
  - `TestSkillMdFormat`：SKILL.md 解析（frontmatter + 正文 + 边界情况）
  - `TestSkillDiscovery`：skill 列举、默认 skill
  - `TestBuildSystemPrompt`：prompt 拼接含工具描述
  - `TestAgentWithSkill`：Agent 初始化、自定义脚本不注册为 Tool、不同 Skill = 不同 system_prompt

**验收**：
- `config/skills/writing/SKILL.md` 可加载
- 内置工具全部注册，与 Skill 无关
- `build_system_prompt()` 产出包含工具描述的完整 prompt
- 切换 Skill = 切换 system_prompt = Agent 行为不同
- 自定义脚本（format.sh）通过 bash 执行，不注册为独立 Tool
