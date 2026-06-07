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
