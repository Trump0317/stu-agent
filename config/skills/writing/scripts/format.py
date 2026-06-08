#!/usr/bin/env python3
"""Markdown 格式化工具

用法:
    python scripts/format.py <input.md> [output.md]

功能:
    - 标题前后补空行
    - 合并多余空行
    - 清理行尾空格
    - 不指定输出时原地修改
"""

import re
import sys
from pathlib import Path


def format_markdown(text: str) -> str:
    """格式化 Markdown 文本"""
    lines = text.splitlines()
    result = []
    prev_empty = False

    for i, line in enumerate(lines):
        # 清理行尾空格
        line = line.rstrip()

        # 标题前补空行
        if line.startswith("#") and result and result[-1] != "":
            result.append("")

        current_empty = (line == "")

        # 合并多余空行
        if current_empty and prev_empty:
            continue

        result.append(line)
        prev_empty = current_empty

    # 确保末尾有换行
    return "\n".join(result) + "\n"


def main():
    if len(sys.argv) < 2:
        print("用法: python format.py <input.md> [output.md]", file=sys.stderr)
        sys.exit(1)

    input_path = Path(sys.argv[1])
    if not input_path.exists():
        print(f"错误: 文件不存在: {input_path}", file=sys.stderr)
        sys.exit(1)

    content = input_path.read_text(encoding="utf-8")
    formatted = format_markdown(content)

    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else input_path
    output_path.write_text(formatted, encoding="utf-8")
    print(f"格式化完成 → {output_path}")


if __name__ == "__main__":
    main()
