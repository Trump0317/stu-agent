### M0：工程骨架 `[x]`

> 目标：目录可 import、pytest 可运行、配置文件可加载。

| # | 任务 | 状态 |
|---|------|------|
| M0-1 | 目录树 + 虚拟环境 + 最小入口 | [x] |
| M0-2 | pytest 基座 + 冒烟测试 | [x] |
| M0-3 | Settings 配置加载 + 校验 | [x] |

##### M0-1：目录树 + 虚拟环境 + 最小入口

- **目标**：按 spec 目录结构创建完整骨架 + Python 虚拟环境。
- **前置依赖**：无
- **文件**：
  - `main.py` — 最小入口（`print("stu-agent starting...")`）
  - `pyproject.toml` / `requirements.txt` — 项目配置 + 依赖
  - `.gitignore` — Python 标准忽略
  - 所有 `src/**/__init__.py` — 包初始化
  - `config/settings.yaml` — 最小可解析配置
  - `config/templates/course_paper.yaml` / `lab_report.yaml` — 模板结构
- **实现**：无（仅骨架）
- **验收**：`python main.py` 可执行；所有顶层包可 import
- **测试**：`python -m compileall src` + `python main.py`

##### M0-2：pytest 基座 + 冒烟测试

- **目标**：建立三层测试目录 + pytest 运行基座。
- **前置依赖**：M0-1
- **文件**：
  - `tests/conftest.py` — pytest 配置
  - `tests/unit/test_smoke_imports.py` — 逐个 import 所有包
  - `tests/unit/__init__.py`, `tests/integration/__init__.py`, `tests/e2e/__init__.py`
- **实现**：无
- **验收**：`pytest -q` 可运行，冒烟测试通过
- **测试**：`pytest -q tests/unit/test_smoke_imports.py`

##### M0-3：Settings 配置加载 + 校验

- **目标**：读取 settings.yaml，校验必填字段，支持 `${ENV_VAR}` 环境变量替换。
- **前置依赖**：M0-1
- **文件**：`src/config/settings.py`
- **实现**：
  - `LLMConfig(provider, model, api_key, base_url)` — dataclass
  - `Settings(llm: LLMConfig)` — dataclass
  - `load_settings(path) -> Settings` — YAML → Settings
  - `validate_settings(settings)` — 必填字段检查
  - `_substitute_env_vars(value)` — `${VAR}` 替换
- **验收**：配置可加载；缺失必填字段抛明确错误；`${DEEPSEEK_API_KEY}` 正确替换
- **测试**：`pytest -q tests/unit/test_settings.py`

**验收**：
- `python main.py` 输出 "stu-agent starting..."
- `pytest -q` 冒烟测试通过
- `config/settings.yaml` 可加载，缺少字段时报明确错误
