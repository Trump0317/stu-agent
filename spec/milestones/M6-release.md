### M6：发布 `[ ]`

> 目标：可安装的独立应用，一键分发。

| # | 任务 | 状态 |
|---|------|------|
| M6-1 | Agent + UI 联调 | [ ] |
| M6-2 | E2E 测试（真实 LLM + 完整流程） | [ ] |
| M6-3 | PyInstaller 打包 | [ ] |

##### M6-1：Agent + UI 联调 `[ ]`

- - **文件**：`src/ui/`, `main.py`
- **目标**：AgentSession 接入 NiceGUI，完整交互链路。
- **实现**：用户输入 → ChatPanel → AgentSession.run() → 流式输出 → UI 更新
- **验收**：浏览器中完成一次完整写作流程

##### M6-2：E2E 测试 `[ ]`

- - **文件**：`tests/e2e/`
- **目标**：真实 LLM + 完整写作流程，全自动化验证。
- **测试**：`pytest -m slow tests/e2e/`
- **测试**：完整写作流（选模板 → 大纲 → 章节 → 导出）、多轮上下文、异常恢复

##### M6-3：PyInstaller 打包 `[ ]`

- - **文件**：`pyinstaller.spec`
- **目标**：产出单一可执行文件。
- **实现**：`pyinstaller.spec`
- **验收**：打包后文件可独立运行（无需 Python 环境），内置 settings.yaml 和 templates

**验收**：
- `python main.py` 启动完整应用
- `pytest -m slow` E2E 全部通过
- PyInstaller 产出单文件可执行包
