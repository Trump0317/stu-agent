#!/usr/bin/env python3
"""Markdown → PDF 直转

用法:
    python scripts/md_to_pdf.py <input.md> [output.pdf]

方案 A: weasyprint（CJK 字体可用时）
方案 B: reportlab（内置 CJK 字体）
方案 C: md→docx→LibreOffice（备选）
"""

import sys
from pathlib import Path


def _pdf_via_weasyprint(md_path: Path, output_path: Path) -> bool:
    """方案 A: weasyprint"""
    try:
        import markdown
        from weasyprint import HTML

        md_text = md_path.read_text(encoding="utf-8")
        html = markdown.markdown(md_text, extensions=["extra", "codehilite"])
        html_doc = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>body {{ font-family: sans-serif; max-width: 800px; margin: auto; padding: 20px; }}</style>
</head><body>{html}</body></html>"""
        HTML(string=html_doc).write_pdf(str(output_path))
        return True
    except Exception:
        return False


def _pdf_via_reportlab(md_path: Path, output_path: Path) -> bool:
    """方案 B: reportlab + 内置 CJK 字体"""
    import re
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont

    try:
        # 注册 CJK 字体
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))

        styles = getSampleStyleSheet()
        # 正文：五号字，1.5 倍行距
        styles.add(ParagraphStyle(
            "CJK_Normal",
            parent=styles["Normal"],
            fontName="STSong-Light",
            fontSize=10.5,
            leading=22,
            firstLineIndent=21,  # 首行缩进两个字符
            spaceAfter=4,
        ))
        # 一级标题：三号，居中
        styles.add(ParagraphStyle(
            "CJK_Heading1",
            parent=styles["Heading1"],
            fontName="STSong-Light",
            fontSize=16,
            leading=28,
            spaceBefore=20,
            spaceAfter=12,
            alignment=1,  # 居中
        ))
        # 二级标题：四号
        styles.add(ParagraphStyle(
            "CJK_Heading2",
            parent=styles["Heading2"],
            fontName="STSong-Light",
            fontSize=14,
            leading=24,
            spaceBefore=16,
            spaceAfter=8,
        ))
        # 三级标题：小四
        styles.add(ParagraphStyle(
            "CJK_Heading3",
            parent=styles["Heading3"],
            fontName="STSong-Light",
            fontSize=12,
            leading=20,
            spaceBefore=12,
            spaceAfter=6,
        ))

        text = md_path.read_text(encoding="utf-8")
        lines = text.splitlines()

        doc = SimpleDocTemplate(
            str(output_path), pagesize=A4,
            leftMargin=30*mm, rightMargin=25*mm,
            topMargin=25*mm, bottomMargin=20*mm,
        )
        story = []

        for line in lines:
            line = line.strip()
            if not line:
                story.append(Spacer(1, 6))
                continue

            if line.startswith("### "):
                story.append(Paragraph(line[4:], styles["CJK_Heading3"]))
            elif line.startswith("## "):
                story.append(Paragraph(line[3:], styles["CJK_Heading2"]))
            elif line.startswith("# "):
                story.append(Paragraph(line[2:], styles["CJK_Heading1"]))
            elif line.startswith("- "):
                story.append(Paragraph("• " + line[2:], styles["CJK_Normal"]))
            else:
                story.append(Paragraph(line, styles["CJK_Normal"]))

        doc.build(story)
        return True
    except Exception:
        return False


def _pdf_via_libreoffice(md_path: Path, output_path: Path) -> bool:
    """方案 C: md→docx→LibreOffice"""
    import subprocess
    import tempfile

    scripts_dir = Path(__file__).parent
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        tmp_docx = tmp.name

    try:
        r = subprocess.run(
            [sys.executable, str(scripts_dir / "md_to_docx.py"),
             str(md_path), tmp_docx],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            return False

        r = subprocess.run(
            [sys.executable, str(scripts_dir / "docx_to_pdf.py"),
             tmp_docx, str(output_path)],
            capture_output=True, text=True,
        )
        return r.returncode == 0
    finally:
        Path(tmp_docx).unlink(missing_ok=True)


def main():
    if len(sys.argv) < 2:
        print("用法: python md_to_pdf.py <input.md> [output.pdf]", file=sys.stderr)
        sys.exit(1)

    md_path = Path(sys.argv[1])
    if not md_path.exists():
        print(f"错误: 文件不存在: {md_path}", file=sys.stderr)
        sys.exit(1)

    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else md_path.with_suffix(".pdf")

    for name, fn in [
        ("reportlab", _pdf_via_reportlab),
        ("weasyprint", _pdf_via_weasyprint),
        ("LibreOffice", _pdf_via_libreoffice),
    ]:
        if fn(md_path, output_path):
            print(f"PDF 已生成 → {output_path}")
            return
        print(f"  方案 {name} 不可用，尝试下一个...", file=sys.stderr)

    print("错误: 所有 PDF 方案均失败，请安装 weasyprint 或 reportlab", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
