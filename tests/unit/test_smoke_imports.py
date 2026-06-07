"""冒烟测试：验证所有包可导入

审核人: 待审核
审核日期: -
审核状态: [待审核]
"""


def test_can_import_agent():
    import src.agent


def test_can_import_tools():
    import src.tools


def test_can_import_llm():
    import src.llm


def test_can_import_ui():
    import src.ui


def test_can_import_converter():
    import src.converter


def test_can_import_storage():
    import src.storage


def test_can_import_core():
    import src.core


def test_main_runs(project_root):
    """验证 main.py 可执行并加载配置"""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, str(project_root / "main.py")],
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "DEEPSEEK_API_KEY": "test-key"},
    )
    assert "stu-agent starting..." in result.stdout
    assert "LLM Provider: deepseek" in result.stdout
    assert result.returncode == 0


def test_config_files_exist(project_root):
    """验证关键配置文件存在"""
    assert (project_root / "config" / "settings.yaml").exists()
    assert (project_root / "config" / "templates" / "course_paper.yaml").exists()
    assert (project_root / "config" / "templates" / "lab_report.yaml").exists()
