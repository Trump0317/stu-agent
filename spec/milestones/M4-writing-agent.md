### M4：写作 Agent `[ ]`

> 目标：真实 LLM + 写作 Skill 完成端到端写作流。

| # | 任务 | 状态 |
|---|------|------|
| M4-1 | TemplateManager（YAML 模板加载） | [x] |
| M4-2 | Markdown → Word 转换 | [x] |
| M4-3 | 写作 Skill 完善 | [ ] |
| M4-4 | 真实 LLM E2E 测试 | [ ] |
| M4-5 | 边界场景验证 | [ ] |

##### M4-1：TemplateManager `[x]`

- **文件**：`src/converter/template_manager.py`
- **实现**：`TemplateManager` → `list_templates()`, `load_template(name)`
- **测试**：`pytest -q tests/unit/test_template_manager.py`

##### M4-2：Markdown → Word 转换 `[x]`

- **文件**：`src/converter/markdown_to_word.py`
- **实现**：`convert_markdown_to_word(md, output_path)` — 标题/段落/列表 → Word
- **测试**：`pytest -q tests/unit/test_markdown_to_word.py`

##### M4-3：写作 Skill 完善 `[ ]`

- **目标**：完善 writing skill 的 system_prompt，让 LLM 看懂模板、按章节写作、导出。
- **文件**：`config/skills/writing.yaml`
- **实现**：
  - 明确流程步骤编号（1/2/3/4）
  - 每步只调一次工具，拿结果后立即下一步
  - 完成写作后必须调用 write_file 保存为 .md
  - 在返回结果中包含 next_step 提示
- **验收**：LLM 按流程执行，不重复调用工具，末尾导出 .md

##### M4-4：真实 LLM E2E 测试 `[ ]`

- **目标**：真实 DeepSeek LLM + writing skill 走通完整流。
- **文件**：`tests/integration/test_real_e2e.py`
- **测试**：
  - 输入"写实验报告"→ read_file 读模板 → 生成内容 → write_file 导出 .md
  - 闲聊不触发工具
  - 无关话题不循环
- **测试**：`pytest -m slow tests/integration/test_real_e2e.py`

##### M4-5：边界场景验证 `[ ]`

- **目标**：确保 Agent 在非写作场景下行为正常。
- **测试**：空输入、纯闲聊、工具异常恢复
- **测试**：合并到 M4-4 的测试文件中

**验收**：
- 输入"写实验报告"→ LLM 调用 read_file 读模板 → 逐章生成 → write_file 导出 .md
- 导出的 .md 文件内容完整（> 500 字符）
- 闲聊不误调用工具
- `pytest -m slow` 端到端测试通过
