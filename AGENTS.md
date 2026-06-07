# stu-agent 项目上下文

## 项目简介

stu-agent 是一款面向中国大学生的通用桌面 Agent。MVP 阶段为**模板驱动的结构化文档编写助手**，采用对话式迭代写作模式。内置课程论文、实验报告两种模板，最终输出 Word 文档。

## 技术栈

| 层次 | 技术 |
|------|------|
| UI | NiceGUI (纯 Python，WebSocket，FastAPI 内核) |
| Agent Core | 自研，参考 pi-core 风格 |
| LLM | OpenAI SDK + 适配层，可插拔 (DeepSeek/Qwen/OpenAI) |
| 文档转换 | python-docx + markdown |
| 打包 | PyInstaller → 独立安装包 |
| 测试 | pytest + pytest-asyncio |

## 项目结构

```
stu-agent/
├── config/
│   ├── settings.yaml              # LLM 配置
│   └── templates/                 # 文档模板 (course_paper.yaml, lab_report.yaml)
├── src/
│   ├── agent/                     # Agent Core (session.py, core.py, events.py)
│   ├── tools/                     # 工具层 (每工具一文件, factory pattern)
│   ├── llm/                       # LLM 抽象层 (base.py, factory.py, providers)
│   ├── ui/                        # NiceGUI 前端 (app.py, chat_panel.py, ...)
│   ├── converter/                 # 文档转换 (markdown_to_word, template_manager)
│   └── storage/                   # 存储 (session_store, file_manager)
├── tests/                         # unit/ integration/ e2e/ fixtures/
├── main.py
└── spec.md                        # 完整开发规格说明书
```

## 开发方法：Spec + TDD

1. 所有开发以 `spec.md` 为总蓝图
2. **先写测试，再写实现** — 严格 TDD
3. 每个任务对应 spec.md 排期表中的一个条目
4. 验收标准：`pytest -q` 全部通过

## Agent Core 架构（pi-core 风格）

- **事件驱动**：`AgentSession` 暴露 `on_turn_start/end`、`on_tool_call/result` 事件回调
- **工具工厂模式**：每工具一个文件，`ToolRegistry` 按名称索引
- **核心循环**：`AgentCore.run()` → while LLM 流式响应 → 有 tool_call 就执行 → 结果喂回 → 直到 LLM 返回纯文本

## 关键设计决策

- Agent Core 不用 LangChain，完全自研，保持打包体积小、可调试
- 工具层与转换层分离：tools/ 负责 Agent 可调用的工具，converter/ 负责底层文档格式转换，未来 RAG 直接复用 converter/
- 模板驱动：新增文档类型只需在 config/templates/ 添加 YAML，不改代码
- LLM 可插拔：通过 LLMFactory + BaseLLM 抽象，配置驱动切换

## 开发约定

- 用中文写注释和文档，代码标识符用英文
- 每完成一个 spec.md 排期任务，更新对应的 `[ ]` 为 `[x]`
- 新增依赖时说明原因

### Spec + TDD 工作流（强制）

1. **分支规范**：禁止直接在 master 分支提交代码。所有开发在 feature 分支进行，经开发者审核通过后方可合并到 master
2. **SPEC 变更审核**：对 spec.md 的任何修改（新增/删除/调整需求），必须先经开发者审核通过后方可继续编码
3. **测试代码审核**：任何测试文件编写完成后，必须经开发者审核，确认测试逻辑正确后方可进入实现阶段
4. **测试文件头部规范**：每个测试文件最顶端必须包含审核信息块：
   ```
   """<测试说明>
   
   审核人: <姓名>
   审核日期: <YYYY-MM-DD>
   审核状态: [待审核] / [已通过] / [需修改]
   """
   ```

### 分支命名规范

- 阶段开发：`phase-<字母>`（如 `phase-b`）
- 功能开发：`feat-<功能名>`（如 `feat-rag-integration`）
- 修复：`fix-<描述>`
