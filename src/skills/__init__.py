"""Skill 加载器

从 config/skills/ 加载 YAML 定义的 skill。
每个 skill 包含：name, description, tools 列表, system_prompt。
"""

from dataclasses import dataclass, field
from pathlib import Path

import yaml


SKILLS_DIR = Path(__file__).parent.parent.parent / "config" / "skills"


@dataclass
class Skill:
    """Skill 定义"""
    name: str
    description: str = ""
    system_prompt: str = ""
    tools: list[str] = field(default_factory=list)


def load_skill(name: str) -> Skill | None:
    """加载指定 skill

    Args:
        name: skill 名称（不含 .yaml）

    Returns:
        Skill 对象，不存在则返回 None
    """
    filepath = SKILLS_DIR / f"{name}.yaml"
    if not filepath.exists():
        return None

    data = yaml.safe_load(filepath.read_text(encoding="utf-8")) or {}
    return Skill(
        name=data.get("name", name),
        description=data.get("description", ""),
        system_prompt=data.get("system_prompt", ""),
        tools=data.get("tools", []),
    )


def list_skills() -> list[str]:
    """列出所有可用 skill（不含 .yaml 后缀）"""
    if not SKILLS_DIR.exists():
        return []
    return sorted([f.stem for f in SKILLS_DIR.glob("*.yaml")])


def get_default_skill() -> Skill:
    """获取默认 skill（writing）"""
    skill = load_skill("writing")
    if skill is None:
        raise FileNotFoundError("默认 skill writing.yaml 不存在")
    return skill
