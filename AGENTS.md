# stu-agent

> 基于里程碑的精简 Agent 开发项目。自研 Agent Core，参考 pi 架构。

## 开发入口

读 [spec/index.md](spec/index.md)，完整规格在其中。

## 关键规则

- **分支**：master(稳定) ← dev(集成) ← M3(里程碑) | docs/xxx | fix/xxx
- **开发方法**：TDD，详见 [spec/workflow.md](spec/workflow.md)
- **里程碑状态**：`[ ]` → `[~]` → `[x]`
- **语言**：中文回复，代码标识符英文
- **测试**：`pytest -q` 全部通过方可提交
- **当前**：M0+M1+M2 完成（226 tests），下一步 M3
