### M4：写作 Agent `[~]`

> 目标：Skill 自包含。模板解析 + docx 填充 + md→word 全部作为脚本放在 `scripts/`，
> Agent 通过 bash 调用。自定义模板支持 .yaml / .md / .docx，
> .docx 填充保留原样式。移除 `src/converter/`。

| # | 任务 | 状态 |
|---|------|------|
| M4-1 | Skill 脚本：模板解析 + docx 填充 + md→word | [x] |
| M4-2 | 写作 SKILL.md 完善 | [ ] |
| M4-3 | 单元测试（脚本级） | [ ] |
| M4-4 | E2E 测试 + 边界（真实 LLM） | [ ] |

##### M4-1：Skill 脚本 `[ ]`

- **目标**：writing skill 自包含模板处理能力，均为命令行脚本。
- **文件**：`config/skills/writing/scripts/`
- **脚本**：

| 脚本 | 功能 | 用法 |
|------|------|------|
| `format.py` | Markdown 格式化 | `python scripts/format.py <in.md> [out.md]` |
| `read_template.py` | 读取模板，输出章节结构 | `python scripts/read_template.py <path>` |
| `fill_docx.py` | 填充 .docx，保留样式 | `python scripts/fill_docx.py <tmpl> '<json>' <out>` |
| `md_to_docx.py` | Markdown → .docx | `python scripts/md_to_docx.py <in.md> <out.docx>` |
| `md_to_pdf.py` | Markdown → PDF | `python scripts/md_to_pdf.py <in.md> [out.pdf]` |
| `docx_to_pdf.py` | .docx → PDF | `python scripts/docx_to_pdf.py <in.docx> [out.pdf]` |

- **实现**：
  - `read_template.py`：自动识别 `.yaml` / `.md` / `.docx`，输出 JSON `{name, sections: [{title}]}`
    - `.yaml`：读取 `sections[].title`
    - `.md`：正则提取 `#` `##` 标题行
    - `.docx`：python-docx 提取 Heading 1/2 段落文本
  - `fill_docx.py`：按位置匹配（第 N 个 Heading ← 第 N 个 `##` 章节），插入内容，继承 Normal 样式，保留图片/表格
    - 入参：`<template.docx> <content.md> <output.docx>`
    - 流程：复制模板 → 遍历 Heading 段落 → 从 .md 按 `##` 分裂章节 → 在对应 Heading 后插入
    - 图片、表格、页眉页脚原样保留
  - `md_to_docx.py`：Markdown 标题/段落/列表 → python-docx 新建文件
    - 入参：`<input.md> <output.docx>`
    - `#` → Heading 1，`##` → Heading 2，正文 → Normal，列表 → List Bullet
  - `md_to_pdf.py`：Markdown → PDF 直转
    - 入参：`<input.md> [output.pdf]`
    - 方案 A（优先）：markdown 库 + weasyprint 渲染
    - 方案 B（备选）：先转 docx 再调用 docx_to_pdf
  - `docx_to_pdf.py`：.docx → PDF
    - 入参：`<input.docx> [output.pdf]`
    - 调用 LibreOffice headless：`libreoffice --headless --convert-to pdf`
  - `format.py`：Markdown 格式化（替代 .sh）
    - 入参：`<input.md> [output.md]`
    - 功能：统一标题前空行、合并多余空行、清理行尾空格
- **验收**：三种格式模板可读取，.docx 填充后样式保留

##### M4-2：写作 SKILL.md 完善 `[ ]`

- **目标**：writing skill 引导 LLM 按模板分步写作。
- **文件**：`config/skills/writing/SKILL.md`
- **实现**：
  - 流程：用户指定模板 → `read_template.py` 获取章节 → 逐章确认+写作 → 导出
  - `.yaml` / `.md` 模板：`md_to_docx.py` 或 `md_to_pdf.py` 导出
  - `.docx` 模板：`fill_docx.py` 导出，可选 `docx_to_pdf.py` 转 PDF
- **验收**：LLM 按流程执行，不跳步

##### M4-3：单元测试（脚本级）`[ ]`

- **目标**：脚本独立可测。
- **文件**：`tests/unit/test_m4_scripts.py`
- **测试**：read_template 三种格式、fill_docx 样式保留、md_to_docx 转换正确

##### M4-4：E2E + 边界 `[ ]`

- **目标**：真实 LLM 验证完整写作流 + 边界。
- **文件**：`tests/manual/test_m4_e2e.py`
- **测试**：
  - **场景 1**：写课程论文（.docx 模板）→ 读取 → 逐章生成 → fill_docx 导出
  - **场景 2**：写实验报告（.docx 模板 + .md 模板）→ 两轮完整流
  - 闲聊不触发工具、空输入、工具异常恢复

**验收**：
- 场景 1：.docx 输出保留模板样式，内容完整
- 场景 2：.docx 和 .md 两种模板均走通
- 闲聊不误调用工具
- 264 + 新增全部通过
