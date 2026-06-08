"""模板管理器 — 加载 YAML 模板"""

from pathlib import Path

import yaml


TEMPLATES_DIR = Path(__file__).parent.parent.parent / "config" / "templates"


class TemplateManager:
    """模板管理器

    统一加载 YAML 模板，tools 和 converter 共用。
    """

    def __init__(self, templates_dir: Path | None = None):
        self._dir = templates_dir or TEMPLATES_DIR

    def list_templates(self) -> list[dict]:
        """列出所有可用模板（name + type）"""
        templates = []
        for f in sorted(self._dir.glob("*.yaml")):
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
            templates.append({
                "name": data.get("name", f.stem),
                "type": f.stem,
            })
        return templates

    def load_template(self, name: str) -> dict | None:
        """加载单个模板完整结构"""
        filepath = self._dir / f"{name}.yaml"
        if not filepath.exists():
            return None
        with open(filepath, encoding="utf-8") as f:
            return yaml.safe_load(f)

    def get_section_titles(self, name: str) -> list[str]:
        """获取模板章节标题列表"""
        template = self.load_template(name)
        if template is None:
            return []
        return [s["title"] for s in template.get("sections", [])]
