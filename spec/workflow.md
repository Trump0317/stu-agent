# 开发工作流

## 分支规范

```
master          ← 里程碑稳定分支（每个 M 完成后合入）
dev             ← 开发集成分支
M1, M2, M3 ...  ← 里程碑阶段分支（从 dev 拉出）
docs/xxx        ← 文档修改分支（从 dev 拉出）
fix/xxx         ← Bug 修复分支（从 dev 拉出）
```

**流程**：
1. 从 dev 拉 `M3` 分支 → 开发里程碑任务
2. 完成后合并 `M3 → dev`
3. M3 稳定后合并 `dev → master`
4. 文档/Bug 从 dev 拉分支 → 合回 dev

## TDD 流程（M0-M4）

```
Step 0  更新里程碑任务状态 [ ] → [~]
Step 1  编写测试文件 → 标记 [待审核]
Step 2  ⚠️ 自动调用 reviewer agent（subagent）审查测试 → 展示审查结果
Step 3  ⚠️ 开发者回复「通过」→ 改 [待审核] 为 [已通过]
Step 4  编写实现代码 → pytest -q 全部通过
Step 5  ⚠️ 展示结果给开发者
Step 6  更新任务状态 [~] → [x]，git add + commit
```

### SPEC 变更审核

spec 文件修改须经开发者审核通过后方可 commit。

**新增功能流程**：
1. 确定归属里程碑（如已有里程碑中新增任务 N+1，或新增里程碑 M7）
2. 修改对应 milestone .md 文件：表格加一行 + 补 `##### Mx-N：任务名` 详情
3. 更新 `milestones.md` 进度统计
4. 展示变更 → 开发者审核 → 通过后 commit
5. 按 TDD 流程执行任务

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
