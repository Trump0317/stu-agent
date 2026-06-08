#!/usr/bin/env python3
""".docx → PDF 转换

用法:
    python scripts/docx_to_pdf.py <input.docx> [output.pdf]

依赖: LibreOffice（headless 模式）
"""

import subprocess
import sys
from pathlib import Path


def main():
    if len(sys.argv) < 2:
        print("用法: python docx_to_pdf.py <input.docx> [output.pdf]", file=sys.stderr)
        sys.exit(1)

    input_path = Path(sys.argv[1])
    if not input_path.exists():
        print(f"错误: 文件不存在: {input_path}", file=sys.stderr)
        sys.exit(1)

    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else input_path.with_suffix(".pdf")
    output_dir = output_path.parent.resolve()

    # 确保输出目录存在
    output_dir.mkdir(parents=True, exist_ok=True)

    # LibreOffice headless 转换
    # 输出到指定目录，文件名由 LibreOffice 自动生成
    r = subprocess.run(
        [
            "libreoffice",
            "--headless",
            "--convert-to", "pdf",
            "--outdir", str(output_dir),
            str(input_path.resolve()),
        ],
        capture_output=True, text=True, timeout=60,
    )

    if r.returncode != 0:
        print(f"错误: LibreOffice 转换失败: {r.stderr}", file=sys.stderr)
        sys.exit(1)

    # LibreOffice 生成的 PDF 文件名与输入同名
    generated = output_dir / f"{input_path.stem}.pdf"
    if generated != output_path and generated.exists():
        generated.rename(output_path)

    if not output_path.exists():
        print(f"错误: PDF 未生成: {output_path}", file=sys.stderr)
        sys.exit(1)

    print(f"PDF 已生成 → {output_path}")


if __name__ == "__main__":
    main()
