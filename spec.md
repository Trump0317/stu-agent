# stu-agent 开发规格说明书 (SPEC)

> 版本：0.2 — MVP 范围：模板驱动的结构化文档编写（课程论文 + 实验报告）

## 目录

- [1. 项目概述](#1-项目概述)
- [2. 核心功能](#2-核心功能)
- [3. 技术选型](#3-技术选型)
- [4. 测试方案](#4-测试方案)
- [5. 系统架构与模块设计](#5-系统架构与模块设计)
- [6. 项目排期](#6-项目排期)

---

## 1. 项目概述

stu-agent 是一款面向中国大学生的通用桌面 Agent。MVP 阶段定位为**模板驱动的结构化文档编写助手**，采用对话式迭代写作模式。内置课程论文、实验报告等多种模板，学生选择模板后，Agent 按模板结构引导写作，最终输出 Word 文档。

核心理念：课程论文和实验报告本质是同一件事——「按模板结构、逐章填充、最终导出」。统一为模板驱动后，新增文档类型只需新增模板，无需改动 Agent 逻辑。

### 设计理念

本项目既是实用工具，也是**学习与实战项目**：
- **教是最好的学**：通过自研 Agent Core，深入理解 LLM Agent 的底层原理
- **简约但不简陋**：参考 pi-core 的架构风格——事件驱动、工厂模式工具、每工具一文件
- **开箱即用**：PyInstaller 打包为独立安装包，学生双击即可使用

### 核心交互流程

```
学生选择模板（课程论文 / 实验报告 / ...）
    ↓
学生输入主题
    ↓
Agent 生成大纲 → 学生确认/修改
    ↓
逐章节写作 → 学生逐章审查
    ↓
全文润色 → 学生最终确认
    ↓
一键导出 Word (.docx)
```

---

## 2. 核心功能

### 2.1 MVP 功能清单

| 功能 | 描述 | 优先级 |
|------|------|--------|
| **模板选择** | 内置课程论文、实验报告两种模板，按模板结构写作 | P0 |
| **对话式写作** | 多轮对话，Agent 按模板引导完成文档 | P0 |
| **大纲生成** | 根据模板+主题生成结构化大纲 | P0 |
| **章节写作** | 按大纲逐节撰写正文 | P0 |
| **文本润色** | 改写、精简、学术化表达 | P0 |
| **Markdown 渲染** | 实时预览草稿 | P0 |
| **Word 导出** | Markdown → Word (.docx) 一键导出 | P0 |
| **多模型切换** | 支持 DeepSeek / Qwen / OpenAI | P0 |
| **对话历史** | 保存和恢复写作会话 | P1 |

### 2.2 内置模板

#### 课程论文模板
```
摘要 → 关键词 → 引言 → 文献综述 → 正文（多章）→ 结论 → 参考文献
```

#### 实验报告模板
```
实验目的 → 实验原理 → 实验器材 → 实验步骤 → 实验数据 → 结果分析 → 结论
```

> **扩展性**：未来新增「文献综述」「开题报告」「简历」等模板，只需在 `config/templates/` 下添加 YAML 文件，无需改动 Agent 代码。

### 2.3 用户故事

1. **学生 A**（大三，写期末课程论文）：打开 stu-agent → 选择「课程论文」模板 → 输入「帮我写一篇关于人工智能伦理的论文」→ Agent 按论文结构生成大纲 → 逐章写作 → 润色 → 导出 Word 提交。

2. **学生 B**（大一，写实验报告）：打开 stu-agent → 选择「实验报告」模板 → 输入「牛顿第二定律验证实验」→ Agent 按实验报告结构生成大纲 → 学生提供数据 → Agent 撰写步骤与结果分析 → 导出 Word。

---

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

### 3.2 Agent Core 设计（参考 pi-core 风格）

```
┌─────────────────────────────────────────────┐
│              AgentSession                     │
│  • 对话历史 (messages)                        │
│  • turn 计数器                               │
│  • 事件回调 (on_turn_start/end 等)            │
│  • 系统提示词管理                             │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│              AgentCore (核心循环)              │
│                                              │
│  async def run(self, user_input: str):       │
│      messages.append({"role": "user", ...})  │
│      while True:                             │
│          response = await llm.stream(...)    │
│          if response.tool_calls:             │
│              for tc in response.tool_calls:  │
│                  result = execute_tool(tc)   │
│                  messages.append(result)     │
│          else:                               │
│              yield response.text             │
│              break                           │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│              ToolRegistry (工具注册中心)       │
│  {                                           │
│    "select_template":  TemplateTool(),        │
│    "generate_outline": OutlineTool(),        │
│    "write_section":   WriteSectionTool(),    │
│    "polish_text":     PolishTool(),          │
│    "export_word":     ExportWordTool(),      │
│    "read_file":       ReadFileTool(),        │
│    "write_file":      WriteFileTool(),       │
│  }                                           │
└─────────────────────────────────────────────┘
```

**关键设计原则（来自 pi-core）：**
- **事件驱动**：Agent 生命周期事件（`turn_start/end`、`tool_call/result`）通过回调暴露
- **工具工厂模式**：每工具一文件，ToolRegistry 统一管理，通过名称索引
- **异步流式**：LLM 调用使用流式输出，工具调用支持并行执行
- **可插拔 LLM**：通过 Provider 抽象层切换模型，配置驱动

### 3.3 项目目录结构

```
stu-agent/
├── config/
│   ├── settings.yaml              # 主配置文件 (LLM provider/model)
│   └── templates/                 # 文档模板目录
│       ├── course_paper.yaml      # 课程论文模板
│       └── lab_report.yaml        # 实验报告模板
│
├── src/
│   ├── agent/                     # Agent Core 层
│   │   ├── __init__.py
│   │   ├── session.py             # AgentSession (对话历史、事件管理)
│   │   ├── core.py                # AgentCore (核心循环)
│   │   └── events.py              # AgentEvent 类型定义
│   │
│   ├── tools/                     # 工具层 (每工具一文件)
│   │   ├── __init__.py
│   │   ├── registry.py            # ToolRegistry (工具注册与路由)
│   │   ├── base.py                # BaseTool 抽象基类
│   │   ├── select_template.py     # 模板选择工具
│   │   ├── generate_outline.py    # 大纲生成工具（模板感知）
│   │   ├── write_section.py       # 章节写作工具
│   │   ├── polish_text.py         # 文本润色工具
│   │   ├── export_word.py         # Word 导出工具
│   │   ├── read_file.py           # 文件读取工具
│   │   └── write_file.py          # 文件写入工具
│   │
│   ├── llm/                       # LLM 抽象层
│   │   ├── __init__.py
│   │   ├── base.py                # BaseLLM 抽象
│   │   ├── factory.py             # LLMFactory (配置驱动)
│   │   ├── openai_compat.py       # OpenAI-Compatible (DeepSeek/Qwen)
│   │   └── openai_provider.py     # OpenAI 原生
│   │
│   ├── ui/                        # NiceGUI 前端
│   │   ├── __init__.py
│   │   ├── app.py                 # NiceGUI 应用入口
│   │   ├── chat_panel.py          # 聊天面板组件
│   │   ├── markdown_preview.py    # Markdown 实时预览
│   │   └── settings_panel.py      # 设置面板
│   │
│   ├── converter/                 # 文档转换层
│   │   ├── __init__.py
│   │   ├── markdown_to_word.py    # MD → Word 转换
│   │   └── template_manager.py    # 模板加载与渲染
│   │
│   └── storage/                   # 存储层
│       ├── __init__.py
│       ├── session_store.py       # 对话历史持久化
│       └── file_manager.py        # 文件管理
│
├── tests/
│   ├── unit/                      # 单元测试
│   │   ├── test_agent_core.py
│   │   ├── test_tool_registry.py
│   │   ├── test_select_template.py
│   │   ├── test_generate_outline.py
│   │   ├── test_write_section.py
│   │   ├── test_polish_text.py
│   │   ├── test_export_word.py
│   │   ├── test_llm_factory.py
│   │   └── test_agent_session.py
│   ├── integration/               # 集成测试
│   │   ├── test_agent_e2e.py      # Agent 完整写作流程
│   │   └── test_ui_chat.py        # UI 集成测试
│   └── fixtures/                  # 测试数据
│       ├── sample_papers/         # 示例文档
│       └── mock_responses/        # Mock LLM 响应
│
├── main.py                        # 应用入口
├── pyproject.toml                 # 项目配置
├── requirements.txt               # 依赖
├── spec.md                        # 本文件
└── README.md
```

---

## 4. 测试方案

### 4.1 设计理念：测试驱动开发 (TDD)

采用 **Spec + TDD** 开发范式：
- **先写测试，再写实现**
- **测试即文档**：测试用例 = 组件行为规范
- **每个任务 5 步**：明确目标 → 写测试 → 写实现 → 跑测试 → 通过

### 4.2 测试分层

```
        /\
       /E2E\         <- 少量：完整写作流程验证
      /------\
     /Integration\   <- 中量：Agent + 工具 + LLM mock
    /------------\
   /  Unit Tests  \  <- 大量：每个工具/函数独立测试
  /________________\
```

### 4.3 测试策略

| 层级 | 范围 | Mock 策略 | 数量目标 |
|------|------|----------|---------|
| **单元测试** | 每个工具、Agent Core、LLM Factory | Mock LLM 响应，不调真实 API | ~50+ |
| **集成测试** | Agent 完整写作流程 | Mock LLM 流式输出 | ~10+ |
| **E2E 测试** | UI 交互 + 导出 Word | 可选真实 LLM | ~5+ |

### 4.4 关键测试场景

1. **Agent Core 循环**：验证工具调用的正确循环与终止
2. **工具注册**：验证 ToolRegistry 的注册、查找、执行
3. **模板选择**：验证模板加载和结构解析
4. **大纲生成**：验证给定模板+主题产出结构化大纲
5. **章节写作**：验证按大纲和上下文生成章节内容
6. **文本润色**：验证输入文本的改写质量
7. **Word 导出**：验证 MD→Word 格式正确性
8. **LLM 切换**：验证工厂根据配置返回正确的 Provider
9. **对话历史**：验证多轮对话上下文累积

---

## 5. 系统架构与模块设计

### 5.1 整体架构图

```
┌─────────────────────────────────────────────────────────┐
│                     NiceGUI UI 层                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │  Chat Panel  │  │ MD Preview   │  │ Settings     │   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘   │
│         │                 │                 │           │
│         └─────────────────┼─────────────────┘           │
│                           │ WebSocket                   │
└───────────────────────────┼─────────────────────────────┘
                            │
┌───────────────────────────┼─────────────────────────────┐
│                      Agent 层                             │
│                           │                              │
│  ┌────────────────────────▼──────────────────────────┐  │
│  │                  AgentSession                       │  │
│  │  messages: list | turn: int | events: callbacks    │  │
│  └────────────────────────┬──────────────────────────┘  │
│                           │                              │
│  ┌────────────────────────▼──────────────────────────┐  │
│  │                  AgentCore                          │  │
│  │  while True:                                        │  │
│  │    resp = await llm.stream(messages, tools)         │  │
│  │    if resp.tool_calls: execute_tools(tool_calls)    │  │
│  │    else: yield text; break                          │  │
│  └──────────┬───────────────────────┬─────────────────┘  │
│             │                       │                    │
│  ┌──────────▼──────────┐  ┌─────────▼────────────────┐  │
│  │    ToolRegistry      │  │    LLM Provider          │  │
│  │  - select_template   │  │  - DeepSeek              │  │
│  │  - generate_outline  │  │  - Qwen                  │  │
│  │  - write_section     │  │  - OpenAI                │  │
│  │  - polish_text       │  │                          │  │
│  │  - export_word       │  │                          │  │
│  │  - read_file         │  │                          │  │
│  │  - write_file        │  │                          │  │
│  └──────────────────────┘  └──────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
                            │
┌───────────────────────────┼─────────────────────────────┐
│                      存储层                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ Session Store│  │ File Manager │  │ Settings     │   │
│  │ (JSON 文件)  │  │ (本地文件系统)│  │ (YAML 配置)  │   │
│  └──────────────┘  └──────────────┘  └──────────────┘   │
└──────────────────────────────────────────────────────────┘
```

### 5.2 核心模块说明

#### AgentSession

| 字段/方法 | 说明 |
|-----------|------|
| `messages: list[dict]` | OpenAI 格式的对话历史 |
| `turn: int` | 当前 turn 计数 |
| `system_prompt: str` | 系统提示词 |
| `on_turn_start(callback)` | turn 开始事件 |
| `on_turn_end(callback)` | turn 结束事件 |
| `on_tool_call(callback)` | 工具调用事件 |
| `on_tool_result(callback)` | 工具结果事件 |
| `add_message(msg)` | 追加消息 |
| `clear()` | 清空对话 |

#### AgentCore

```python
class AgentCore:
    def __init__(self, session: AgentSession, llm: BaseLLM, registry: ToolRegistry):
        ...

    async def run(self, user_input: str) -> AsyncIterator[str]:
        """核心循环：接收用户输入，流式返回 Agent 响应"""
        ...
```

#### ToolRegistry

```python
class ToolRegistry:
    def register(self, tool: BaseTool) -> None: ...
    def get_schemas(self) -> list[dict]:           # 返回 OpenAI tool 格式
    def execute(self, name: str, args: dict) -> str: ...
```

#### BaseTool

```python
class BaseTool:
    name: str
    description: str
    parameters: dict          # JSON Schema 格式

    async def execute(self, **kwargs) -> ToolResult: ...
```

### 5.3 数据流

```
用户输入 "帮我写一篇关于区块链的论文"
    │
    ▼
AgentSession.add_message(user_msg)
    │
    ▼
AgentCore.run()
    │ while True:
    │   LLM.stream(messages, tools=[outline, write_section, ...])
    │   ├─ LLM 返回 tool_call: generate_outline("topic"="区块链")
    │   │   → ToolRegistry.execute("generate_outline", ...)
    │   │   → 返回大纲文本
    │   │   → messages.append(tool_result)
    │   │
    │   ├─ LLM 返回 tool_call: write_section("section"="引言", "outline"=...)
    │   │   → ToolRegistry.execute("write_section", ...)
    │   │   → 返回章节内容
    │   │   → messages.append(tool_result)
    │   │
    │   └─ LLM 返回纯文本 "引言部分已完成，请您审阅..."
    │       → yield text
    │       → break
    │
    ▼
NiceGUI 流式渲染 → 用户看到 Markdown 预览
```

---

## 6. 项目排期

> **排期原则**：每阶段 ~1h 可验收增量，严格 TDD（先测试后实现），目录树 = 交付清单。

### 阶段总览

| 阶段 | 目标 | 预计任务数 |
|------|------|-----------|
| **A** | 工程骨架与测试基座 | 3 |
| **B** | LLM 抽象层 (Factory + Provider) | 3 |
| **C** | Agent Core (Session + Core + Events) | 4 |
| **D** | 工具层 (ToolRegistry + 7 个工具) | 8 |
| **E** | 文档转换层 (模板 + MD→Word) | 2 |
| **F** | NiceGUI 前端 (Chat + Preview) | 4 |
| **G** | 集成与打包 (PyInstaller + E2E) | 3 |

---

### 📊 进度跟踪表

> `[ ]` 未开始 | `[~]` 进行中 | `[x]` 已完成

---

## 阶段 A：工程骨架与测试基座（目标：先可导入，再可测试）

| # | 任务 | 状态 |
|---|------|------|
| A1 | 初始化目录树与最小可运行入口 | [x] |
| A2 | 引入 pytest 并建立测试目录约定 | [x] |
| A3 | 配置加载与校验（Settings） | [x] |

### A1：初始化目录树与最小可运行入口

- **目标**：按 spec.md 3.3 节目录结构创建完整目录骨架与空模块文件（可 import），并建立 Python 虚拟环境。
- **修改文件**：
  - `main.py`（最小入口：打印 'stu-agent starting...'）
  - `pyproject.toml`（项目元数据 + 依赖声明）
  - `requirements.txt`（依赖列表：nicegui, openai, python-docx, markdown, pyyaml, pytest, pytest-asyncio）
  - `.gitignore`（Python 标准忽略：`__pycache__`、`.venv`、`.env`、`*.pyc`、IDE 配置等）
  - `README.md`（项目简介占位）
  - `src/**/__init__.py`（按目录树补齐所有包的 `__init__.py`，内容为空）
  - `config/settings.yaml`（最小可解析配置，含 llm/provider/model/api_key/base_url 字段）
  - `config/templates/course_paper.yaml`（课程论文模板结构定义）
  - `config/templates/lab_report.yaml`（实验报告模板结构定义）
  - `tests/__init__.py`
- **实现类/函数**：无（仅骨架）。
- **验收标准**：
  - 目录结构与 spec.md 3.3 节一致。
  - `config/templates/` 目录存在，且两个模板 YAML 可被读取。
  - 能从根目录导入所有关键顶层包：
    - `python -c "from src.agent import session; from src.tools import registry; from src.llm import factory; from src.ui import app; from src.converter import markdown_to_word; from src.storage import session_store"`
  - `python main.py` 可执行，输出 'stu-agent starting...'
  - 虚拟环境已创建（`.venv/`），依赖已安装。
- **测试方法**：
  - `python -m compileall src`（语法/可导入性检查）
  - `python main.py`

### A2：引入 pytest 并建立测试目录约定

- **目标**：建立 `tests/unit|integration|e2e|fixtures` 目录与 pytest 运行基座，编写冒烟测试验证所有包可导入。
- **修改文件**：
  - `pyproject.toml`（添加 `[tool.pytest.ini_options]` 配置：`testpaths = ["tests"]`，`asyncio_mode = "auto"`）
  - `tests/unit/test_smoke_imports.py`（冒烟测试：逐个 import 所有包，验证可导入性）
  - `tests/unit/__init__.py`
  - `tests/integration/__init__.py`
  - `tests/e2e/__init__.py`
  - `tests/fixtures/__init__.py`
  - `tests/conftest.py`（pytest 根级 fixture 配置）
- **实现类/函数**：无（仅测试文件）。
- **验收标准**：
  - `pytest -q` 可运行并通过（至少冒烟测试通过）。
  - 冒烟测试覆盖所有 A1 中创建的关键包。
  - 测试目录结构符合三层分层：unit/、integration/、e2e/。
- **测试方法**：`pytest -q tests/unit/test_smoke_imports.py`

### A3：配置加载与校验（Settings）

- **目标**：实现读取 `config/settings.yaml` 的配置加载器，支持启动时校验关键字段存在，缺失时给出明确错误信息。
- **修改文件**：
  - `src/core/settings.py`（新增：`Settings` dataclass + `load_settings()` + `validate_settings()`）
  - `src/core/__init__.py`
  - `main.py`（启动时调用 `load_settings()`，校验失败则 fail-fast 退出）
  - `tests/unit/test_settings.py`（配置加载与校验单元测试）
- **实现类/函数**：
  - `Settings`（dataclass，字段：`llm.provider`, `llm.model`, `llm.api_key`, `llm.base_url`）
  - `load_settings(path: str) -> Settings`（读取 YAML → 解析为 Settings）
  - `validate_settings(settings: Settings) -> None`（必填字段检查，错误信息包含字段路径）
- **验收标准**：
  - `main.py` 启动时成功加载 `config/settings.yaml` 并拿到 `Settings` 对象。
  - 缺失必填字段时（如 `llm.provider`），`load_settings()` 抛出 `ValueError` 且信息包含缺失字段名。
  - 配置文件语法错误时，给出包含文件名和行号的错误信息。
- **测试方法**：`pytest -q tests/unit/test_settings.py`

#### 阶段 B：LLM 抽象层

| # | 任务 | 状态 | 备注 |
|---|------|------|------|
| B1 | BaseLLM 抽象 + LLMFactory | [ ] | 抽象接口 + 工厂路由 |
| B2 | OpenAI-Compatible Provider | [ ] | DeepSeek / Qwen 适配 |
| B3 | OpenAI Native Provider | [ ] | OpenAI 原生适配 |

#### 阶段 C：Agent Core

| # | 任务 | 状态 | 备注 |
|---|------|------|------|
| C1 | AgentEvent 类型定义 | [ ] | turn_start/end, tool_call/result |
| C2 | AgentSession（对话历史 + 事件） | [ ] | 消息管理、事件回调 |
| C3 | AgentCore（核心 while 循环） | [ ] | LLM 流式 + 工具调用循环 |
| C4 | AgentCore 集成测试 | [ ] | Mock LLM，验证完整循环 |

#### 阶段 D：工具层

| # | 任务 | 状态 | 备注 |
|---|------|------|------|
| D1 | BaseTool + ToolRegistry | [ ] | 工具抽象 + 注册中心 |
| D2 | read_file / write_file | [ ] | 文件读写工具 |
| D3 | select_template | [ ] | 模板选择工具 |
| D4 | generate_outline | [ ] | 大纲生成工具（模板感知） |
| D5 | write_section | [ ] | 章节写作工具 |
| D6 | polish_text | [ ] | 文本润色工具 |
| D7 | export_word | [ ] | Word 导出工具 |
| D8 | Agent + Tools 集成测试 | [ ] | 完整写作流程 Mock |

#### 阶段 E：文档转换层

| # | 任务 | 状态 | 备注 |
|---|------|------|------|
| E1 | 模板管理 (YAML 加载) | [ ] | 从 config/templates/ 加载模板结构 |
| E2 | Markdown → Word 转换 | [ ] | python-docx + markdown 解析 |

#### 阶段 F：NiceGUI 前端

| # | 任务 | 状态 | 备注 |
|---|------|------|------|
| F1 | NiceGUI 应用骨架 | [ ] | 页面路由 + FastAPI 集成 |
| F2 | 聊天面板 (Chat Panel) | [ ] | 流式消息渲染 |
| F3 | Markdown 实时预览 | [ ] | 文档草稿预览 |
| F4 | 设置面板 (Settings) | [ ] | LLM 配置、模板选择 |

#### 阶段 G：集成与打包

| # | 任务 | 状态 | 备注 |
|---|------|------|------|
| G1 | Agent + UI 联调 | [ ] | 端到端写作流程 |
| G2 | E2E 测试 (含真实 LLM) | [ ] | 完整场景验证 |
| G3 | PyInstaller 打包 | [ ] | .exe/.dmg 安装包 |

---

### 总体进度

| 阶段 | 任务数 | 已完成 | 进度 |
|------|--------|--------|------|
| A | 3 | 3 | 100% |
| B | 3 | 0 | 0% |
| C | 4 | 0 | 0% |
| D | 8 | 0 | 0% |
| E | 2 | 0 | 0% |
| F | 4 | 0 | 0% |
| G | 3 | 0 | 0% |
| **总计** | **27** | **3** | **11%** |

---

## 附录：参考资源

- pi-core 架构：事件驱动 Agent + 工厂模式工具系统
- [pi 扩展文档](https://github.com/earendil-works/pi-coding-agent)
- NiceGUI 文档：https://nicegui.io
- python-docx 文档：https://python-docx.readthedocs.io
