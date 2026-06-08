## 3. 技术选型

### 3.1 总体技术栈

| 层次 | 技术 | 选型理由 |
|------|------|---------|
| **UI 层** | NiceGUI | 纯 Python、WebSocket 实时通信、FastAPI 内核 |
| **后端** | FastAPI | 轻量、异步、与 NiceGUI 天然融合 |
| **Agent Core** | 自研 | 参考 pi-core 风格，事件驱动 + 工厂模式 |
| **LLM 调用** | OpenAI SDK + 自定义适配 | 兼容 DeepSeek/Qwen/OpenAI |
| **文档转换** | python-docx + markdown | MD→Word 转换 |
| **打包** | PyInstaller | 独立可执行文件，无需安装 Python |
| **测试** | pytest + pytest-asyncio | TDD 核心工具链 |

### 3.2 Agent Core 设计（对齐 pi 架构）

```
┌─────────────────────────────────────────────────────┐
│              AgentSession (会话编排)                  │
│  on_turn_start/end, on_tool_call/result, on_chunk   │
│  run(user_input) → agent_loop → 事件分发 → 流式输出  │
└────────┬───────────────────────────┬────────────────┘
         │                           │
┌────────▼──────────┐    ┌───────────▼──────────────┐
│   Agent (状态)     │    │   agent_loop (纯函数)     │
│  system_prompt    │    │  while tool_round<max:   │
│  messages[]       │    │    LLM stream            │
│  tools[]          │    │    if tool_call: execute  │
└───────────────────┘    │    else: yield text,break │
                         └──────────┬───────────────┘
                                    │
┌───────────────────────────────────▼───────────────┐
│            ToolExecutor + ToolRegistry              │
│  before_hook → execute → after_hook                 │
│  read_file / write_file / bash                      │
└────────────────────────────────────────────────────┘
```

**关键设计原则（对齐 pi）：**
- **AgentSession 事件驱动**：对标 pi AgentSession，回调属性 on_turn_start/end, on_tool_call/result，UI 层通过 callback 订阅。
- **Agent 纯状态**：持有 system_prompt + messages + tools，不含编排逻辑。
- **agent_loop 纯函数**：接收 context + config，返回 event stream。可独立测试。
- **事件联合类型**：每种事件独立 dataclass，isinstance 分派。
- **hooks 注入**：before_tool_call/after_tool_call 作为 loop config 回调。
- **可插拔 LLM**：通过 stream_fn 注入（桥接 BaseLLM），loop 不依赖具体 Provider。

### 3.3 项目目录结构

```
stu-agent/
├── config/
│   ├── settings.yaml              # LLM 配置
│   ├── templates/                 # 文档模板 (course_paper / lab_report)
│   └── skills/                    # Skill 定义 (writing.yaml)
│
├── src/
│   ├── agent/                     # Agent Core
│   │   ├── types.py               # 类型定义
│   │   ├── events.py              # 事件联合类型
│   │   ├── executor.py            # ToolExecutor
│   │   ├── loop.py                # agent_loop 纯函数
│   │   ├── agent.py               # Agent 状态管理
│   │   └── session.py             # AgentSession 会话编排
│   ├── tools/                     # 基础工具
│   │   ├── base.py                # BaseTool + ToolResult
│   │   ├── registry.py            # ToolRegistry
│   │   ├── file_tools.py          # read_file + write_file
│   │   └── bash_tool.py           # bash 命令执行
│   ├── skills/                    # Skill 系统
│   │   └── __init__.py            # load_skill / list_skills / build_system_prompt
│   ├── llm/                       # LLM 抽象层
│   ├── observability/             # 可观测性
│   ├── ui/                        # NiceGUI 前端 (M5)
│   ├── converter/                 # 文档转换 (M4)
│   └── storage/                   # 存储层
│
├── tests/
│   ├── unit/
│   └── integration/
│
├── main.py
└── spec/
```

## 5. 系统架构与模块设计

### 5.1 整体架构图

```
┌─────────────────────────────────────────────────────────┐
│                     NiceGUI UI 层 (M5)                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │  Chat Panel  │  │ MD Preview   │  │ Settings     │   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘   │
│         └─────────────────┼─────────────────┘           │
│                           │ WebSocket                   │
└───────────────────────────┼─────────────────────────────┘
                            │
┌───────────────────────────┼─────────────────────────────┐
│                      Agent 层                             │
│                           │                              │
│  ┌────────────────────────▼──────────────────────────┐  │
│  │               AgentSession (会话编排)                │  │
│  │  on_turn_start / on_turn_end                       │  │
│  │  on_tool_call / on_tool_result / on_chunk          │  │
│  │  run(user_input) → agent_loop → 分发事件            │  │
│  └──────┬───────────────────────────────┬─────────────┘  │
│         │                               │                │
│  ┌──────▼──────────┐          ┌─────────▼─────────────┐  │
│  │   Agent (状态)   │          │   agent_loop (纯函数)  │  │
│  │  system_prompt  │          │  while tool_round     │  │
│  │  messages       │          │    LLM stream          │  │
│  │  tools          │          │    execute_tools       │  │
│  └─────────────────┘          │    emit events         │  │
│                               └────────┬──────────────┘  │
│         ┌─────────────────────────────┼──────────────┐  │
│  ┌──────▼──────┐  ┌────────────┐  ┌───▼─────────────┐  │
│  │ ToolRegistry│  │ LLM Provider│  │ Skill 系统      │  │
│  │ read_file   │  │ DeepSeek    │  │ writing.yaml    │  │
│  │ write_file  │  │ Qwen        │  │ → prompt+tools  │  │
│  │ bash        │  │ OpenAI      │  │                 │  │
│  └─────────────┘  └─────────────┘  └─────────────────┘  │
└──────────────────────────────────────────────────────────┘
                            │
┌───────────────────────────┼─────────────────────────────┐
│                      存储层                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ Session Store│  │ File Manager │  │ Settings     │   │
│  └──────────────┘  └──────────────┘  └──────────────┘   │
└──────────────────────────────────────────────────────────┘
```

### 5.2 核心模块说明

#### AgentSession (session.py) — 对标 pi

事件驱动会话编排器。持有回调，管理 Agent 生命周期，委托 agent_loop 执行。

```python
class AgentSession:
    agent: Agent              # 状态管理
    llm: BaseLLM              # LLM 实例
    tool_registry: ToolRegistry

    # 回调（对齐 pi）
    on_turn_start: Callable | None
    on_turn_end: Callable | None
    on_tool_call: Callable | None
    on_tool_result: Callable | None

    async def run(user_input: str) -> AsyncIterator[str]
        # 回调: on_chunk(callable) — 流式文本增量
```

**职责**：构建 AgentContext + AgentLoopConfig → 调用 agent_loop → 分发事件到回调 → 流式输出文本。

**与 pi 对比**：
- pi：AgentSession 在 `agent.ts` 中，`AgentSession` 类持有 events 对象
- stu-agent：AgentSession 单独文件，回调属性直接暴露

#### Agent (agent.py)

有状态 Agent，持有 system_prompt + messages + tools。

```python
class Agent:
    state: AgentState         # 只读
    subscribe(listener) -> Callable  # 返回注销函数
    reset()                   # 清空 messages，保留 prompt + tools
```

#### agent_loop (loop.py)

核心循环纯函数。接收 context + config + tool_registry，返回 event stream。

```python
async def agent_loop(
    prompt: str,
    context: AgentContext,
    config: AgentLoopConfig,
    tool_registry: ToolRegistry,
    signal=None,
) -> AsyncIterator[AgentEvent]
```

#### ToolRegistry (registry.py)

基础工具注册中心，仅注册通用工具。

| 工具 | 说明 |
|------|------|
| `read_file` | 读取文件内容 |
| `write_file` | 写入文件内容 |
| `bash` | 执行 Shell 命令（30s 超时） |

#### Skill 系统 (skills/)

YAML 定义的业务能力，包含 system_prompt + 工具列表。

```python
@dataclass
class Skill:
    name: str
    description: str
    system_prompt: str
    tools: list[str]  # ["read_file", "write_file", "bash"]

def load_skill(name) -> Skill
def list_skills() -> list[str]
def build_system_prompt(skill, tools) -> str
```

初始化时：加载 Skill YAML → 实例化工具 → 注册到 ToolRegistry → 拼装 system_prompt → 创建 Agent + AgentSession。

#### Observability (observability/)

纯 subscriber 模式，零侵入 Agent/agent_loop。AgentSession 携带 Observer。

- `ObservabilityConfig`：开关、日志级别、格式
- `TraceContext`：run_id + 耗时追踪
- `AgentObserver`：订阅 AgentSession 回调，生成结构化日志

### 5.3 数据流

```
用户输入 "写实验报告"
    │
    ▼
AgentSession.run(user_input)
    │
    ▼ 构建 AgentContext(system_prompt, messages, tools)
    ▼ 构建 AgentLoopConfig(stream_fn=llm.stream, ...)
    │
    ▼ agent_loop(prompt, context, config, tool_registry):
    │   while tool_round < max_tool_rounds:
    │       stream_fn(messages, tools) → 流式响应
    │       ├─ is_tool_call:
    │       │   ToolStart → execute_tools → ToolEnd
    │       │   结果喂回 messages → continue
    │       └─ text:
    │           MessageUpdate(delta) → yield delta
    │           finish_reason=stop → break
    │
    ▼ AgentSession.run() 内部:
    │   分发事件到 on_turn_start/end, on_tool_call/result, on_chunk
    │   流式 yield text → AgentEnd → 更新 agent.state.messages
    │
    ▼
UI / 调用方 流式渲染文本
```

---

