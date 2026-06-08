"""配置加载与校验

从 config/settings.yaml 读取配置，校验必填字段，支持 ${ENV_VAR} 环境变量替换。
"""

import os
import re
from dataclasses import dataclass

import yaml


@dataclass
class LLMConfig:
    """LLM 提供者配置"""

    provider: str      # deepseek | qwen | openai
    model: str         # 模型名称
    api_key: str       # API Key
    base_url: str = "" # API 基础地址


@dataclass
class Settings:
    """全局配置"""

    llm: LLMConfig


def _substitute_env_vars(value: str) -> str:
    """替换 ${ENV_VAR} 为环境变量值"""
    pattern = re.compile(r"\$\{(\w+)\}")
    if isinstance(value, str):
        return pattern.sub(lambda m: os.environ.get(m.group(1), ""), value)
    return value


def _walk_and_substitute(obj):
    """递归替换 dict 中所有字符串的 ${ENV_VAR}"""
    if isinstance(obj, dict):
        return {k: _walk_and_substitute(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_walk_and_substitute(item) for item in obj]
    if isinstance(obj, str):
        return _substitute_env_vars(obj)
    return obj


def load_settings(path: str = "config/settings.yaml") -> Settings:
    """从 YAML 文件加载配置

    Raises:
        FileNotFoundError: 配置文件不存在
        ValueError: YAML 语法错误或必填字段缺失
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"配置文件不存在: {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"YAML 解析错误 ({path}): {e}") from e

    if raw is None:
        raise ValueError(f"配置文件为空: {path}")

    raw = _walk_and_substitute(raw)

    try:
        llm_raw = raw["llm"]
        settings = Settings(
            llm=LLMConfig(
                provider=llm_raw.get("provider", ""),
                model=llm_raw.get("model", ""),
                api_key=llm_raw.get("api_key", ""),
                base_url=llm_raw.get("base_url", ""),
            )
        )
    except KeyError as e:
        raise ValueError(f"缺少配置字段: {e}") from e

    validate_settings(settings)
    return settings


def validate_settings(settings: Settings) -> None:
    """校验必填字段，缺失时抛出 ValueError 包含字段路径

    Raises:
        ValueError: 必填字段为空
    """
    checks = [
        ("llm.provider", settings.llm.provider),
        ("llm.model", settings.llm.model),
        ("llm.api_key", settings.llm.api_key),
    ]

    for field_path, value in checks:
        if not value:
            raise ValueError(f"缺少必填配置: {field_path}")
