# 开发工作流

## TDD 流程（M0-M4）

```
Step 1  编写测试文件 → 标记 [待审核]
Step 2  reviewer agent 辅助审查 → 展示审查结果
Step 3  ⚠️ 开发者回复「通过」→ 改 [待审核] 为 [已通过]
Step 4  编写实现代码 → pytest -q 全部通过
Step 5  ⚠️ 展示结果给开发者
Step 6  git add + commit
```

### SPEC 变更审核

spec 文件修改须经开发者审核通过后方可 commit。

## 前端交互流程（M5 专用）

```
Step 1  启动服务器
Step 2  开发者浏览器查看
Step 3  反馈修改意见
Step 4  修改实现代码
Step 5  重启服务器 → 回到 Step 2
```

- 不编写测试，直接写实现
- 每次重启后浏览器刷新查看效果

## 审核规则

- **reviewer agent**：辅助审查工具，其结论不等同于开发者审核通过
- **最终放行权**：始终在开发者
- **审核人姓名**：必须填人类姓名，不得填 agent/工具名称

## 参考资源

- [pi-core](https://github.com/earendil-works/pi-coding-agent) — 事件驱动 Agent 架构
- [NiceGUI](https://nicegui.io) — Python Web UI 框架
- [python-docx](https://python-docx.readthedocs.io) — Word 文档生成
