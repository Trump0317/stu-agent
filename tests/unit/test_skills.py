"""Skill 系统单元测试

遵循 Agent Skills 标准：SKILL.md = YAML frontmatter + Markdown 正文
- Skill = system_prompt，不声明工具列表
- 内置工具全局可用，Agent 行为由 system_prompt 决定
- 自定义脚本通过 bash 执行，不注册为独立 Tool

审核人: Trump
审核日期: 2026-06-08
审核状态: [已通过]
"""

import os
import pytest
import yaml

from src.skills import (
    Skill,
    _parse_skill_md,
    build_system_prompt,
    create_agent_from_skill,
    get_default_skill,
    list_skills,
    load_skill,
)
from src.tools.bash_tool import BashTool
from src.tools.file_tools import ReadFileTool, WriteFileTool
from src.tools.registry import ToolRegistry


# ============================================================
# helpers
# ============================================================

def _make_mock_llm(text: str = "mock"):
    """创建 MockLLM 类工厂"""
    from src.llm.models import LLMResponse

    class MockLLM:
        async def stream(self, messages, tools=None):
            yield LLMResponse(text=text, finish_reason="stop")

    return MockLLM


def _make_neutral_skill(tmp_path, name="neutral", description="不含工具名", body="你好。"):
    """在 tmp_path 中创建一个不含工具名的 skill，用于测试 build_system_prompt"""
    (tmp_path / name).mkdir()
    (tmp_path / name / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n{body}\n",
        encoding="utf-8",
    )
    import src.skills as skills_mod
    return skills_mod


# ============================================================
# M3-1: SKILL.md 格式定义
# 验收: frontmatter 可解析，正文 > 200 字符
# ============================================================

class TestSkillMdFormat:
    """M3-1: SKILL.md 格式定义

    [~]
    """

    # ---- writing skill ----

    def test_frontmatter_parsable(self):
        """SKILL.md frontmatter 可解析，name/description 与文件一致"""
        skill = load_skill("writing")
        assert skill is not None
        assert isinstance(skill, Skill)
        assert skill.name == "writing"
        assert isinstance(skill.description, str)
        assert len(skill.description) > 0
        # description 应与 SKILL.md frontmatter 中一致
        assert "模板驱动" in skill.description

    def test_body_length(self):
        """Markdown 正文长度 > 200 字符"""
        skill = load_skill("writing")
        assert len(skill.system_prompt) > 200

    def test_body_does_not_contain_frontmatter(self):
        """正文不含 YAML frontmatter 标记"""
        skill = load_skill("writing")
        assert "---" not in skill.system_prompt

    def test_skill_dir_is_set(self):
        """Skill.dir 指向 Skill 目录"""
        skill = load_skill("writing")
        assert skill.dir is not None
        assert skill.dir.is_dir()
        assert (skill.dir / "SKILL.md").exists()

    def test_skill_has_scripts(self):
        """scripts/ 目录存在，format.sh 可访问可执行"""
        skill = load_skill("writing")
        scripts_dir = skill.dir / "scripts"
        assert scripts_dir.is_dir()
        format_sh = scripts_dir / "format.sh"
        assert format_sh.is_file()
        assert os.access(format_sh, os.X_OK)

    # ---- _parse_skill_md 单元测试 ----

    def test_parse_valid_frontmatter(self, tmp_path):
        """标准 SKILL.md: frontmatter + 正文"""
        md = tmp_path / "SKILL.md"
        md.write_text(
            "---\n"
            "name: test-skill\n"
            "description: 测试用 skill\n"
            "---\n"
            "# Test Skill\n\n"
            "这是正文内容。\n",
            encoding="utf-8",
        )
        fm, body = _parse_skill_md(md)
        assert fm["name"] == "test-skill"
        assert fm["description"] == "测试用 skill"
        assert "# Test Skill" in body
        assert "这是正文内容" in body

    def test_parse_frontmatter_with_extra_fields(self, tmp_path):
        """frontmatter 含额外字段时不影响 name/description 解析"""
        md = tmp_path / "SKILL.md"
        md.write_text(
            "---\n"
            "name: test\n"
            "description: desc\n"
            "author: someone\n"
            "version: 1.0\n"
            "---\n"
            "正文\n",
            encoding="utf-8",
        )
        fm, body = _parse_skill_md(md)
        assert fm["name"] == "test"
        assert fm["description"] == "desc"
        # 额外字段保留但被 load_skill 忽略

    def test_parse_no_frontmatter(self, tmp_path):
        """无 frontmatter 时全部视为正文"""
        md = tmp_path / "SKILL.md"
        md.write_text("# Just markdown\n\nNo frontmatter.\n", encoding="utf-8")
        fm, body = _parse_skill_md(md)
        assert fm == {}
        assert "# Just markdown" in body

    def test_parse_empty_frontmatter(self, tmp_path):
        """空 frontmatter + 正文"""
        md = tmp_path / "SKILL.md"
        md.write_text("---\n---\n# Body only\n", encoding="utf-8")
        fm, body = _parse_skill_md(md)
        assert fm == {}
        assert "# Body only" in body

    def test_parse_empty_body(self, tmp_path):
        """仅 frontmatter 无正文时 system_prompt 为空"""
        md = tmp_path / "SKILL.md"
        md.write_text("---\nname: nobody\ndescription: no body\n---\n", encoding="utf-8")
        fm, body = _parse_skill_md(md)
        assert fm["name"] == "nobody"
        assert body == ""

    def test_parse_invalid_yaml_frontmatter(self, tmp_path):
        """frontmatter 中非法 YAML 抛出异常"""
        md = tmp_path / "SKILL.md"
        md.write_text(
            "---\nname: [unclosed\n  - broken\n---\nbody\n",
            encoding="utf-8",
        )
        with pytest.raises(yaml.YAMLError):
            _parse_skill_md(md)

    def test_parse_unclosed_frontmatter(self, tmp_path):
        """只有开头 --- 无结尾时，全部视为正文（不会误匹配正文中的 ---）"""
        md = tmp_path / "SKILL.md"
        md.write_text("---\nname: foo\n# No closing ---\n", encoding="utf-8")
        fm, body = _parse_skill_md(md)
        assert fm == {}
        assert "---" in body

    # ---- 边界情况 ----

    def test_load_nonexistent_skill(self):
        """不存在的 skill 返回 None"""
        assert load_skill("nonexistent_xyz") is None

    def test_load_skill_without_frontmatter(self, tmp_path):
        """SKILL.md 无 frontmatter 时使用默认值"""
        import src.skills as skills_mod

        (tmp_path / "plain").mkdir()
        md = tmp_path / "plain" / "SKILL.md"
        md.write_text("# Just markdown\n\nSome instructions.\n", encoding="utf-8")

        original = skills_mod.SKILLS_DIR
        try:
            skills_mod.SKILLS_DIR = tmp_path
            skill = load_skill("plain")
            assert skill is not None
            assert skill.name == "plain"
            assert skill.description == ""
            assert skill.dir == tmp_path / "plain"
            assert "Some instructions" in skill.system_prompt
        finally:
            skills_mod.SKILLS_DIR = original

    def test_load_skill_empty_body(self, tmp_path):
        """仅 frontmatter 无正文时 system_prompt 为空"""
        import src.skills as skills_mod

        (tmp_path / "emptybody").mkdir()
        (tmp_path / "emptybody" / "SKILL.md").write_text(
            "---\nname: emptybody\ndescription: no body\n---\n",
            encoding="utf-8",
        )

        original = skills_mod.SKILLS_DIR
        try:
            skills_mod.SKILLS_DIR = tmp_path
            skill = load_skill("emptybody")
            assert skill is not None
            assert skill.name == "emptybody"
            assert skill.system_prompt == ""
        finally:
            skills_mod.SKILLS_DIR = original


# ============================================================
# M3-2: Skill 加载 + prompt 拼装 + Agent 初始化
# ============================================================

class TestSkillDiscovery:
    """M3-2: Skill 发现与列举

    [ ]
    """

    def test_list_skills(self):
        """列出所有可用 skill"""
        skills = list_skills()
        assert isinstance(skills, list)
        assert "writing" in skills

    def test_get_default_skill(self):
        """获取默认 skill (writing)"""
        skill = get_default_skill()
        assert skill.name == "writing"
        assert skill.dir is not None

    def test_get_default_skill_raises_when_missing(self, monkeypatch):
        """writing skill 缺失时抛 FileNotFoundError"""
        monkeypatch.setattr("src.skills.load_skill", lambda name: None)
        with pytest.raises(FileNotFoundError):
            get_default_skill()

    def test_list_skills_empty_dir(self, tmp_path):
        """空目录下列出空列表"""
        import src.skills as skills_mod

        original = skills_mod.SKILLS_DIR
        try:
            skills_mod.SKILLS_DIR = tmp_path
            assert list_skills() == []
        finally:
            skills_mod.SKILLS_DIR = original


class TestBuildSystemPrompt:
    """M3-2: build_system_prompt — 拼接 system_prompt + 工具描述

    [ ]
    """

    def test_output_contains_tool_section(self, tmp_path):
        """使用不含工具名的 skill，验证工具描述来自 build_system_prompt 追加"""
        mod = _make_neutral_skill(tmp_path)
        original = mod.SKILLS_DIR
        try:
            mod.SKILLS_DIR = tmp_path
            skill = load_skill("neutral")
            registry = ToolRegistry()
            registry.register(ReadFileTool())
            registry.register(WriteFileTool())

            prompt = build_system_prompt(skill, registry)
            # tool section 来自 build_system_prompt 追加，非 skill 正文
            assert "## 可用工具" in prompt
            assert "read_file" in prompt
            assert "write_file" in prompt
            # skill 正文在前
            assert prompt.startswith(skill.system_prompt)
        finally:
            mod.SKILLS_DIR = original

    def test_output_longer_than_original(self, tmp_path):
        """拼接后 prompt 比原始 system_prompt 更长"""
        mod = _make_neutral_skill(tmp_path)
        original = mod.SKILLS_DIR
        try:
            mod.SKILLS_DIR = tmp_path
            skill = load_skill("neutral")
            registry = ToolRegistry()
            registry.register(ReadFileTool())

            prompt = build_system_prompt(skill, registry)
            assert len(prompt) > len(skill.system_prompt)
        finally:
            mod.SKILLS_DIR = original

    def test_tool_description_included(self, tmp_path):
        """工具自身的 description 属性值包含在 prompt 中（不硬编码中文）"""
        mod = _make_neutral_skill(tmp_path)
        original = mod.SKILLS_DIR
        try:
            mod.SKILLS_DIR = tmp_path
            skill = load_skill("neutral")
            registry = ToolRegistry()
            tool = ReadFileTool()
            registry.register(tool)

            prompt = build_system_prompt(skill, registry)
            assert tool.description in prompt
        finally:
            mod.SKILLS_DIR = original

    def test_required_param_marked(self, tmp_path):
        """必填参数标记 (必填)，非必填不标记"""
        mod = _make_neutral_skill(tmp_path)
        original = mod.SKILLS_DIR
        try:
            mod.SKILLS_DIR = tmp_path
            skill = load_skill("neutral")
            registry = ToolRegistry()
            registry.register(ReadFileTool())  # path 必填
            registry.register(BashTool())       # command 必填

            prompt = build_system_prompt(skill, registry)
            assert " (必填)" in prompt
            # path 是 read_file 中唯一的必填参数
            assert "path:" in prompt
        finally:
            mod.SKILLS_DIR = original

    def test_empty_registry_no_extra_section(self, tmp_path):
        """空 ToolRegistry 时不追加工具区块"""
        mod = _make_neutral_skill(tmp_path)
        original = mod.SKILLS_DIR
        try:
            mod.SKILLS_DIR = tmp_path
            skill = load_skill("neutral")
            registry = ToolRegistry()

            prompt = build_system_prompt(skill, registry)
            assert prompt == skill.system_prompt
            assert "## 可用工具" not in prompt
        finally:
            mod.SKILLS_DIR = original


class TestAgentWithSkill:
    """M3-2: Agent 按 Skill 初始化

    - 全部内置工具注册
    - Agent 行为由 system_prompt 决定
    - 自定义脚本通过 bash 执行

    [ ]
    """

    def test_agent_registers_all_builtin_tools(self):
        """Agent 初始化时注册全部内置工具"""
        MockLLM = _make_mock_llm()
        agent, registry = create_agent_from_skill("writing", MockLLM())

        registered = registry.list_tools()
        assert "read_file" in registered
        assert "write_file" in registered
        assert "bash" in registered

        agent_tool_names = [t.name for t in agent.state.tools]
        assert "read_file" in agent_tool_names
        assert "write_file" in agent_tool_names
        assert "bash" in agent_tool_names

    def test_system_prompt_from_skill(self):
        """Agent 的 system_prompt 来自 Skill 的 Markdown 正文"""
        MockLLM = _make_mock_llm()
        skill = load_skill("writing")
        agent, registry = create_agent_from_skill("writing", MockLLM())

        assert skill.system_prompt in agent.state.system_prompt
        assert "写作助手" in agent.state.system_prompt

    def test_custom_script_not_registered(self):
        """自定义脚本（format.sh）不作为独立 Tool 注册"""
        MockLLM = _make_mock_llm()
        agent, registry = create_agent_from_skill("writing", MockLLM())

        registered = registry.list_tools()
        assert "format" not in registered
        assert "format_sh" not in registered
        assert "bash" in registered  # 通过 bash 调用

    def test_system_prompt_contains_script_reference(self):
        """system_prompt 包含自定义脚本的完整路径引用"""
        MockLLM = _make_mock_llm()
        agent, registry = create_agent_from_skill("writing", MockLLM())

        assert "scripts/format.sh" in agent.state.system_prompt

    def test_nonexistent_skill_raises(self):
        """不存在的 skill 抛出 FileNotFoundError"""
        MockLLM = _make_mock_llm()
        with pytest.raises(FileNotFoundError):
            create_agent_from_skill("nonexistent_xyz", MockLLM())

    def test_different_skills_share_same_tools(self, tmp_path):
        """不同 Skill 使用相同的内置工具集，仅 system_prompt 不同"""
        import src.skills as skills_mod

        # 创建 skill-a
        (tmp_path / "skill-a").mkdir()
        (tmp_path / "skill-a" / "SKILL.md").write_text(
            "---\nname: skill-a\ndescription: A\n---\n# Skill A\n你擅长总结。\n",
            encoding="utf-8",
        )
        # 创建 skill-b
        (tmp_path / "skill-b").mkdir()
        (tmp_path / "skill-b" / "SKILL.md").write_text(
            "---\nname: skill-b\ndescription: B\n---\n# Skill B\n你擅长翻译。\n",
            encoding="utf-8",
        )

        MockLLM = _make_mock_llm()
        original = skills_mod.SKILLS_DIR
        try:
            skills_mod.SKILLS_DIR = tmp_path

            agent_a, reg_a = create_agent_from_skill("skill-a", MockLLM())
            agent_b, reg_b = create_agent_from_skill("skill-b", MockLLM())

            # 工具名称集合相同
            assert set(reg_a.list_tools()) == set(reg_b.list_tools())

            # system_prompt 不同
            assert "总结" in agent_a.state.system_prompt
            assert "翻译" in agent_b.state.system_prompt
            assert agent_a.state.system_prompt != agent_b.state.system_prompt

            # agent state tools 与 registry schemas 一致
            reg_schemas = set(s["function"]["name"] for s in reg_a.get_schemas())
            agent_tool_names = set(t.name for t in agent_a.state.tools)
            assert reg_schemas == agent_tool_names
        finally:
            skills_mod.SKILLS_DIR = original
