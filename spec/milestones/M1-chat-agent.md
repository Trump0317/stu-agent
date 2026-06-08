### M1：闲聊 Agent `[x]`

> 目标：LLM 流式对话。命令行输入，逐字输出，支持多轮。

| # | 任务 | 状态 |
|---|------|------|
| M1-1 | 数据模型（ToolCall + LLMResponse） | [x] |
| M1-2 | BaseLLM 抽象接口 | [x] |
| M1-3 | LLMFactory 工厂路由 | [x] |
| M1-4 | 流式解析引擎（parse_openai_stream） | [x] |
| M1-5 | OpenAICompatProvider（DeepSeek / Qwen） | [x] |
| M1-6 | OpenAINativeProvider（OpenAI） | [x] |
| M1-7 | types.py — AgentState / AgentMessage / AgentContext | [x] |
| M1-8 | events.py — AgentEvent 联合类型 | [x] |
| M1-9 | executor.py — ToolExecutor | [x] |
| M1-10 | loop.py — agent_loop 纯函数 | [x] |
| M1-11 | agent.py — Agent 状态管理 | [x] |
| M1-12 | session.py — AgentSession 事件驱动编排器 | [x] |
| M1-13 | Observability（Config / Tracer / Observer / Token） | [x] |
| M1-14 | AgentCore 单元 + 集成测试 | [x] |

##### M1-1：数据模型

- **目标**：定义 LLM 交互的纯数据结构。
- **文件**：`src/llm/models.py`
- **实现**：
  - `ToolCall(id, name, arguments)` — 工具调用
  - `LLMResponse(text, tool_calls, is_tool_call, finish_reason, usage)` — 流式响应
- **验收**：ToolCall 可创建；LLMResponse 默认值正确，可表示文本/工具两种模式
- **测试**：`pytest -q tests/unit/test_llm_models.py`

##### M1-2：BaseLLM 抽象接口

- **目标**：定义 LLM Provider 必须实现的抽象接口。
- **文件**：`src/llm/base.py`
- **实现**：`BaseLLM(ABC)` — 抽象方法 `async stream(messages, tools) -> AsyncIterator[LLMResponse]`
- **验收**：BaseLLM 不可直接实例化；子类未实现 stream 不可实例化
- **测试**：`pytest -q tests/unit/test_llm_base.py`

##### M1-3：LLMFactory 工厂路由

- **目标**：根据配置 provider 字段路由到正确的 Provider。
- **文件**：`src/llm/factory.py`
- **实现**：`LLMFactory.create(config: LLMConfig) -> BaseLLM`
  - `deepseek`/`qwen` → `OpenAICompatProvider`；`openai` → `OpenAINativeProvider`
  - 未知 provider → `ValueError`
- **验收**：provider 路由正确；名称大小写不敏感；空字符串抛 ValueError
- **测试**：`pytest -q tests/unit/test_llm_factory.py`

##### M1-4：流式解析引擎

- **目标**：将 OpenAI 兼容 API 的流式 chunk 转换为 LLMResponse 序列。
- **文件**：`src/llm/stream_parser.py`
- **实现**：`async parse_openai_stream(stream) -> AsyncIterator[LLMResponse]`
  - `delta.content` → text；`delta.tool_calls` → 按 id 累积；`finish_reason` → 最终响应
- **验收**：纯文本/工具调用/混合流均正确解析；finish_reason 传递正确
- **测试**：`pytest -q tests/unit/test_stream_parser.py`

##### M1-5：OpenAICompatProvider（DeepSeek / Qwen）

- **前置依赖**：B1 + B2 + B4
- **目标**：封装 `AsyncOpenAI`，适配 DeepSeek / Qwen。
- **文件**：`src/llm/openai_compat.py`
- **实现**：`OpenAICompatProvider(BaseLLM)` — `stream()` 委托 `parse_openai_stream()`
- **验收**：正确传递 model/messages/tools；base_url 由 config 控制
- **测试**：`pytest -q tests/unit/test_openai_compat.py`

##### M1-6：OpenAINativeProvider（OpenAI）

- **前置依赖**：同 M1-5
- **目标**：封装 `AsyncOpenAI` 连接 OpenAI 原生 API。
- **文件**：`src/llm/openai_provider.py`
- **实现**：`OpenAINativeProvider(BaseLLM)` — 与 M1-5 逻辑一致
- **验收**：功能等价 M1-5；共享 parse_openai_stream
- **测试**：`pytest -q tests/unit/test_openai_provider.py`

##### M1-7：types.py

- **目标**：定义 Agent 层所有纯数据结构。
- **文件**：`src/agent/types.py`
- **实现**：
  - `AgentTool(name, label, description, parameters)` — 工具定义
  - `AgentToolResult(content, details, is_error)` — 工具执行结果
  - `AgentMessage(role, content, tool_call_id, tool_calls)` — 对话消息
  - `AgentState(system_prompt, tools, messages, is_streaming)` — 运行时状态
  - `AgentContext(system_prompt, messages, tools)` — loop 入参快照
  - `AgentLoopConfig(model, stream_fn, convert_to_llm, max_tool_rounds=5, max_retries=2)` — 循环配置
- **验收**：所有类型可创建并访问字段；State 默认值正确
- **测试**：`pytest -q tests/unit/test_agent_types.py`

##### M1-8：events.py

- **目标**：定义事件联合类型，每种事件独立 dataclass。
- **文件**：`src/agent/events.py`
- **实现**：
  - 生命周期：`BeforeAgentStart`, `AgentStart`, `AgentEnd`
  - 回合：`TurnStart(turn)`, `TurnEnd(turn, message, tool_results, usage)`
  - 消息：`MessageStart`, `MessageUpdate(delta, delta_type)`, `MessageEnd`
  - 工具：`ToolStart(tool_call_id, tool_name, args)`, `ToolEnd(tool_call_id, tool_name, result, is_error)`
  - 重试：`RetryStart(attempt, error)`, `RetryEnd`
- **验收**：每种事件可独立创建；isinstance 可用于类型判断
- **测试**：`pytest -q tests/unit/test_agent_events.py`

##### M1-9：executor.py

- **目标**：实现工具执行器，支持 before/after hooks、顺序执行。
- **文件**：`src/agent/executor.py`
- **实现**：
  - `async execute_tool(tool_call_id, tool_name, args, tool_registry, before_hook, after_hook, on_update) -> AgentToolResult`
  - `async execute_tools(tool_calls, tool_registry, ...) -> list[AgentToolResult]`
- **实现**：ToolStart → before_hook（可 block）→ 执行 → after_hook → ToolEnd
- **验收**：正常执行返回结果；before_hook 返回 block 时跳过；异常不抛
- **测试**：`pytest -q tests/unit/test_agent_executor.py`

##### M1-10：loop.py

- **目标**：纯函数 Agent 核心循环，接收 context + config，返回 event stream。
- **文件**：`src/agent/loop.py`
- **实现**：`async agent_loop(prompt, context, config, tool_registry, signal) -> AsyncIterator[AgentEvent]`
- **实现**：BeforeAgentStart → AgentStart → TurnStart → while tool_round < max → LLM stream → tool_call → execute_tools → 结果喂回 → 否则 yield text → break → TurnEnd → AgentEnd
- **实现**：无状态（context 不修改）、max_tool_rounds + max_retries 双重保护、tool_registry 独立参数
- **测试**：`pytest -q tests/unit/test_agent_loop.py`

##### M1-11：agent.py

- **目标**：有状态 Agent 类，持有 system_prompt + messages + tools。
- **文件**：`src/agent/agent.py`
- **实现**：`Agent` — `state(只读)`, `subscribe(listener) -> 注销函数`, `reset()`
- **验收**：subscribe 注册的 listener 收到事件；reset() 后恢复初始
- **测试**：`pytest -q tests/unit/test_agent.py`

##### M1-12：AgentSession

- **目标**：对标 pi，事件驱动会话编排器，UI 通过回调订阅。
- **文件**：`src/agent/session.py`
- **实现**：`AgentSession(agent, llm, tool_registry)`
  - 回调：`on_turn_start`, `on_turn_end`, `on_tool_call`, `on_tool_result`, `on_chunk`
  - `run(user_input) -> AsyncIterator[str]`：构建 context → agent_loop → 分发事件 → 流式输出
- **验收**：Session 可独立于 UI 运行；回调在正确时机触发
- **测试**：`pytest -q tests/unit/test_agent_session.py`

##### M1-13：Observability

- **目标**：纯 subscriber 模式，零侵入 Agent/agent_loop。
- **文件**：`src/observability/config.py`, `tracer.py`, `observer.py`
- **实现**：
  - `ObservabilityConfig(enabled, log_level, log_format, log_file, trace_enabled)`
  - `TraceContext(run_id, started_at, events)` — 耗时追踪
  - `AgentObserver(agent, config)` — 订阅 Agent 事件，生成结构化日志
- **验收**：observer 挂载后 prompt() 产生完整日志；json 格式可解析
- **测试**：`pytest -q tests/unit/test_observability_*.py`

##### M1-14：AgentCore 测试

- **目标**：Mock LLM + Mock ToolRegistry 验证所有分支。
- **测试**：
  - 纯文本 → 事件链完整
  - 工具调用 → ToolStart/ToolEnd 正确
  - 重试 → RetryStart/RetryEnd
  - max_tool_rounds 超限 → 强制终止
  - 多轮对话 → 消息累积
- **测试**：`pytest -q tests/unit/test_agent_loop.py tests/unit/test_agent.py`

**验收**：
- `python main.py` 进入 REPL，输入文本得到流式回复
- 支持多轮对话（messages 累积）
- Tools 参数为空列表时，Agent 正常工作
