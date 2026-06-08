#!/usr/bin/env python3
"""Markdown → PDF 直转

用法:
    python scripts/md_to_pdf.py <input.md> [output.pdf]

方案 A: markdown + weasyprint
方案 B: 先转 docx 再调用 docx_to_pdf（备选）
"""

import sys
from pathlib import Path


def main():
    if len(sys.argv) < 2:
        print("用法: python md_to_pdf.py <input.md> [output.pdf]", file=sys.stderr)
        sys.exit(1)

    md_path = Path(sys.argv[1])
    if not md_path.exists():
        print(f"错误: 文件不存在: {md_path}", file=sys.stderr)
        sys.exit(1)

    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else md_path.with_suffix(".pdf")

    # 方案 A: weasyprint
    try:
        import markdown
        from weasyprint import HTML

        md_text = md_path.read_text(encoding="utf-8")
        html = markdown.markdown(md_text, extensions=["extra", "codehilite"])
        html_doc = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>body {{ font-family: 'Noto Sans CJK SC', sans-serif; max-width: 800px; margin: auto; padding: 20px; }}</style>
</head><body>{html}</body></html>"""
        HTML(string=html_doc).write_pdf(str(output_path))
        print(f"PDF 已生成 → {output_path}")
        return
    except ImportError:
        pass

    # 方案 B: 先转 docx 再转 pdf
    try:
        import subprocess
        import tempfile

        scripts_dir = Path(__file__).parent
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
            tmp_docx = tmp.name

        # md → docx
        r = subprocess.run(
            [sys.executable, str(scripts_dir / "md_to_docx.py"), str(md_path), tmp_docx],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            print(f"错误: md→docx 失败: {r.stderr}", file=sys.stderr)
            sys.exit(1)

        # docx → pdf
        r = subprocess.run(
            [sys.executable, str(scripts_dir / "docx_to_pdf.py"), tmp_docx, str(output_path)],
            capture_output=True, text=True,
        )
        Path(tmp_docx).unlink(missing_ok=True)
        if r.returncode != 0:
            print(f"错误: docx→pdf 失败: {r.stderr}", file=sys.stderr)
            sys.exit(1)
        print(f"PDF 已生成 → {output_path}")
    except Exception as e:
        print(f"错误: PDF 生成失败，请安装 weasyprint 或 LibreOffice: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
