#!/usr/bin/env python3
"""模板读取工具

用法:
    python scripts/read_template.py <path>

支持 .yaml / .md / .docx 三种格式。
输出 JSON: {"name": "...", "sections": [{"title": "..."}]}
"""

import json
import sys
from pathlib import Path


def read_yaml(path: Path) -> dict:
    import yaml
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    sections = [{"title": s["title"]} for s in data.get("sections", [])]
    return {"name": data.get("name", path.stem), "sections": sections}


def read_md(path: Path) -> dict:
    import re
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    name = path.stem
    sections = []
    for line in lines:
        # ## 或 ### 标题作为章节
        m = re.match(r"^#{2,3}\s+(.+)", line)
        if m:
            sections.append({"title": m.group(1).strip()})
        # # 一级标题作为文档名
        elif re.match(r"^#\s+(.+)", line):
            name = re.match(r"^#\s+(.+)", line).group(1).strip()
    return {"name": name, "sections": sections}


def read_docx(path: Path) -> dict:
    from docx import Document
    doc = Document(str(path))
    sections = []
    for para in doc.paragraphs:
        if para.style.name.startswith("Heading"):
            sections.append({"title": para.text.strip()})
    return {"name": path.stem, "sections": sections}


READERS = {
    ".yaml": read_yaml,
    ".yml": read_yaml,
    ".md": read_md,
    ".docx": read_docx,
}


def main():
    if len(sys.argv) < 2:
        print("用法: python read_template.py <path>", file=sys.stderr)
        sys.exit(1)

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"错误: 文件不存在: {path}", file=sys.stderr)
        sys.exit(1)

    ext = path.suffix.lower()
    reader = READERS.get(ext)
    if reader is None:
        print(f"错误: 不支持的格式 '{ext}'，支持: {list(READERS.keys())}", file=sys.stderr)
        sys.exit(1)

    result = reader(path)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
