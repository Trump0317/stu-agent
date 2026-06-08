"""Skill 加载器

从 config/skills/ 加载 Skill，遵循 Agent Skills 标准。

Skill 格式：目录 + SKILL.md（YAML frontmatter + Markdown 正文）

```
config/skills/writing/
├── SKILL.md              # frontmatter(name, description) + Markdown 指令
└── scripts/              # 自定义脚本（通过 bash 执行）
    └── format.py
```

参照 pi 设计：
- 内置工具全局可用，Skill 不声明工具列表
- Skill = system_prompt（Markdown 正文），靠指令改变 Agent 行为
- 自定义脚本不注册为独立 Tool，通过 bash 执行

提供函数：
- load_skill(name) -> Skill | None
- list_skills() -> list[str]
- get_default_skill() -> Skill
- build_system_prompt(skill, registry) -> str
- create_agent_from_skill(skill_name, llm) -> (Agent, ToolRegistry)
"""

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from src.tools.bash_tool import BashTool
from src.tools.file_tools import ReadFileTool, WriteFileTool
from src.tools.registry import ToolRegistry


SKILLS_DIR = Path(__file__).parent.parent.parent / "config" / "skills"

# 所有内置工具（全局可用，Skill 不声明工具列表）
_BUILTIN_TOOLS = [ReadFileTool, WriteFileTool, BashTool]


@dataclass
class Skill:
    """Skill 定义

    Attributes:
        name: skill 名称（来自 frontmatter.name）
        description: 简述（来自 frontmatter.description，渐进式加载用）
        system_prompt: Markdown 正文（完整指令 + 脚本调用说明）
        dir: Skill 目录路径（用于解析 scripts/ 等相对路径）
    """
    name: str
    description: str = ""
    system_prompt: str = ""
    dir: Path | None = None


def _parse_skill_md(filepath: Path) -> tuple[dict, str]:
    """解析 SKILL.md 的 YAML frontmatter + Markdown 正文

    格式:
        ---
        name: foo
        description: bar
        ---
        # 正文（Markdown）

    Returns:
        (frontmatter_dict, body_text)
    """
    text = filepath.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}, text.strip()

    # 找独立行的 --- 作为 frontmatter 结束标记
    # 匹配: \n---\n 或 \n---（文件末尾，后面只有空白）
    first_nl = text.find("\n", 3)
    if first_nl == -1:
        return {}, text.strip()

    end = text.find("\n---\n", first_nl)
    if end != -1:
        # 标准: \n---\n
        frontmatter_text = text[3:end].strip()
        body = text[end + 5:].strip()
    else:
        end = text.find("\n---", first_nl)
        if end != -1 and text[end + 4:].strip() == "":
            # 文件末尾: \n--- 后只有空白
            frontmatter_text = text[3:end].strip()
            body = ""
        else:
            # 无匹配的结束 ---，全文视为正文
            return {}, text.strip()

    frontmatter = yaml.safe_load(frontmatter_text) or {}
    return frontmatter, body


def _resolve_skill_path(name: str) -> tuple[Path | None, Path | None]:
    """解析 skill 路径

    Returns:
        (md_path, dir_path):
          md_path 是 SKILL.md 路径，
          dir_path 是 skill 目录
    """
    dir_path = SKILLS_DIR / name
    md_path = dir_path / "SKILL.md"
    if md_path.exists():
        return md_path, dir_path
    return None, None


def load_skill(name: str) -> Skill | None:
    """加载指定 skill

    查找 config/skills/{name}/SKILL.md。

    Args:
        name: skill 名称

    Returns:
        Skill 对象，不存在则返回 None
    """
    md_path, skill_dir = _resolve_skill_path(name)
    if md_path is None:
        return None

    frontmatter, body = _parse_skill_md(md_path)
    return Skill(
        name=frontmatter.get("name", name),
        description=frontmatter.get("description", ""),
        system_prompt=body,
        dir=skill_dir,
    )


def list_skills() -> list[str]:
    """列出所有可用 skill

    扫描 config/skills/ 下包含 SKILL.md 的子目录。
    """
    if not SKILLS_DIR.exists():
        return []
    skills = []
    for d in sorted(SKILLS_DIR.iterdir()):
        if d.is_dir() and (d / "SKILL.md").exists():
            skills.append(d.name)
    return skills


def get_default_skill() -> Skill:
    """获取默认 skill（writing）"""
    skill = load_skill("writing")
    if skill is None:
        raise FileNotFoundError("默认 skill writing 不存在")
    return skill


def build_system_prompt(skill: Skill, registry: ToolRegistry) -> str:
    """拼接 skill.system_prompt + 已注册工具的 schema 描述

    Args:
        skill: Skill 对象
        registry: 已注册内置工具的 ToolRegistry

    Returns:
        完整的 system_prompt
    """
    parts = [skill.system_prompt]
    schemas = registry.get_schemas()
    if schemas:
        parts.append("\n\n## 可用工具")
        for schema in schemas:
            func = schema["function"]
            parts.append(f"\n### {func['name']}")
            parts.append(func["description"])
            props = func.get("parameters", {}).get("properties", {})
            required = func.get("parameters", {}).get("required", [])
            if props:
                parts.append("参数:")
                for pname, pinfo in props.items():
                    req_mark = " (必填)" if pname in required else ""
                    parts.append(
                        f"  - {pname}: {pinfo.get('type', 'string')}"
                        f" - {pinfo.get('description', '')}{req_mark}"
                    )
    return "\n".join(parts)


def create_agent_from_skill(
    skill_name: str, llm, model: str = ""
) -> "tuple":
    """从 skill 创建配置好的 Agent 和 ToolRegistry

    注册全部内置工具（read_file, write_file, bash），
    Agent 行为由 Skill 的 system_prompt 决定。

    Args:
        skill_name: skill 名称
        llm: BaseLLM 实例
        model: 模型名称（可选）

    Returns:
        (Agent, ToolRegistry) 元组

    Raises:
        FileNotFoundError: skill 不存在
    """
    from src.agent.agent import Agent
    from src.agent.types import AgentTool

    skill = load_skill(skill_name)
    if skill is None:
        raise FileNotFoundError(f"Skill '{skill_name}' 不存在")

    # 注册全部内置工具
    registry = ToolRegistry()
    for tool_cls in _BUILTIN_TOOLS:
        registry.register(tool_cls())

    system_prompt = build_system_prompt(skill, registry)

    # 从 registry schema 构建 AgentTool 列表
    tool_schemas = registry.get_schemas()
    agent_tools = []
    for schema in tool_schemas:
        func = schema["function"]
        agent_tools.append(
            AgentTool(
                name=func["name"],
                label=func["name"],
                description=func["description"],
                parameters=func["parameters"],
            )
        )

    agent = Agent(
        llm=llm,
        tool_registry=registry,
        system_prompt=system_prompt,
        model=model,
        tools=agent_tools,
    )

    return agent, registry
