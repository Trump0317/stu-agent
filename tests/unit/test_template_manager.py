"""TemplateManager 单元测试

审核人: Trump
审核日期: 2026-06-07
审核状态: [已通过]
"""

import pytest
from src.converter.template_manager import TemplateManager


class TestTemplateManager:
    def test_list_templates(self):
        mgr = TemplateManager()
        templates = mgr.list_templates()
        assert isinstance(templates, list)
        assert len(templates) >= 2
        for t in templates:
            assert "name" in t
            assert "type" in t
        types = [t["type"] for t in templates]
        assert "course_paper" in types
        assert "lab_report" in types

    def test_load_template_course_paper(self):
        mgr = TemplateManager()
        t = mgr.load_template("course_paper")
        assert t is not None
        assert t["name"] == "课程论文"
        assert t["type"] == "course_paper"
        assert "sections" in t
        assert len(t["sections"]) > 0
        assert t["sections"][0]["title"] == "摘要"

    def test_load_template_lab_report(self):
        mgr = TemplateManager()
        t = mgr.load_template("lab_report")
        assert t is not None
        assert t["name"] == "实验报告"
        assert t["type"] == "lab_report"
        assert "sections" in t

    def test_load_template_invalid(self):
        mgr = TemplateManager()
        t = mgr.load_template("nonexistent")
        assert t is None

    def test_get_section_titles_course_paper(self):
        mgr = TemplateManager()
        titles = mgr.get_section_titles("course_paper")
        assert len(titles) > 0
        assert "摘要" in titles
        assert "引言" in titles
        assert "结论" in titles

    def test_get_section_titles_lab_report(self):
        mgr = TemplateManager()
        titles = mgr.get_section_titles("lab_report")
        assert len(titles) > 0
        assert "实验目的" in titles

    def test_get_section_titles_invalid(self):
        mgr = TemplateManager()
        titles = mgr.get_section_titles("nonexistent")
        assert titles == []
