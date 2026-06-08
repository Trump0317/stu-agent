#!/bin/bash
# 格式化 Markdown 文档
# 用法: bash scripts/format.sh <input.md> [output.md]
# 功能: 统一标题格式、清理多余空行、添加分隔线

INPUT="$1"
OUTPUT="${2:-${INPUT}}"

if [ ! -f "$INPUT" ]; then
    echo "错误: 文件不存在: $INPUT"
    exit 1
fi

echo "正在格式化 $INPUT ..."

# 管道处理:
# 1. 标题前后加空行
# 2. 多个连续空行合并为一个
# 3. 清理行尾空格
sed -e 's/^##/\n##/' \
    -e 's/^#/\n#/' \
    -e '/^$/N;/^\n$/D' \
    -e 's/[[:space:]]*$//' \
    "$INPUT" > "$OUTPUT"

echo "格式化完成 → $OUTPUT"
