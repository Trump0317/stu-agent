"""配置加载与校验 — 单元测试

审核人: Trump
审核日期: 2026-06-07
审核状态: [已通过]
"""

import tempfile
from pathlib import Path

import pytest
import yaml


# 测试实现前先写 import，方便后续替换
# from src.config.settings import Settings, load_settings, validate_settings


class TestLoadSettings:
    """配置加载测试"""

    def test_load_valid_settings(self):
        """加载合法配置"""
        from src.config.settings import load_settings

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(
                {
                    "llm": {
                        "provider": "deepseek",
                        "model": "deepseek-chat",
                        "api_key": "sk-test",
                        "base_url": "https://api.deepseek.com/v1",
                    }
                },
                f,
            )
            path = f.name

        try:
            settings = load_settings(path)
            assert settings.llm.provider == "deepseek"
            assert settings.llm.model == "deepseek-chat"
            assert settings.llm.api_key == "sk-test"
        finally:
            Path(path).unlink()

    def test_load_settings_missing_file(self):
        """加载不存在的配置文件"""
        from src.config.settings import load_settings

        with pytest.raises(FileNotFoundError):
            load_settings("/nonexistent/settings.yaml")

    def test_load_settings_invalid_yaml(self):
        """加载语法错误的 YAML"""
        from src.config.settings import load_settings

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write("llm: {invalid: yaml: here")
            path = f.name

        try:
            with pytest.raises(ValueError, match="YAML"):
                load_settings(path)
        finally:
            Path(path).unlink()


class TestValidateSettings:
    """配置校验测试"""

    def test_valid_settings_passes(self):
        """合法配置通过校验"""
        from src.config.settings import LLMConfig, Settings, validate_settings

        settings = Settings(
            llm=LLMConfig(
                provider="openai",
                model="gpt-4o",
                api_key="sk-test",
                base_url="https://api.openai.com/v1",
            )
        )
        validate_settings(settings)  # 不应抛异常

    def test_missing_provider_raises(self):
        """缺少 provider 抛异常"""
        from src.config.settings import LLMConfig, Settings, validate_settings

        settings = Settings(
            llm=LLMConfig(
                provider="",
                model="gpt-4o",
                api_key="sk-test",
                base_url="https://api.openai.com/v1",
            )
        )
        with pytest.raises(ValueError, match="llm.provider"):
            validate_settings(settings)

    def test_missing_api_key_raises(self):
        """缺少 api_key 抛异常"""
        from src.config.settings import LLMConfig, Settings, validate_settings

        settings = Settings(
            llm=LLMConfig(
                provider="openai",
                model="gpt-4o",
                api_key="",
                base_url="https://api.openai.com/v1",
            )
        )
        with pytest.raises(ValueError, match="llm.api_key"):
            validate_settings(settings)

    def test_missing_model_raises(self):
        """缺少 model 抛异常"""
        from src.config.settings import LLMConfig, Settings, validate_settings

        settings = Settings(
            llm=LLMConfig(
                provider="openai",
                model="",
                api_key="sk-test",
                base_url="https://api.openai.com/v1",
            )
        )
        with pytest.raises(ValueError, match="llm.model"):
            validate_settings(settings)

    def test_env_var_substitution(self):
        """验证环境变量替换语法被保留"""
        import os

        from src.config.settings import load_settings

        os.environ["TEST_API_KEY"] = "env-key-value"

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(
                {
                    "llm": {
                        "provider": "deepseek",
                        "model": "deepseek-chat",
                        "api_key": "${TEST_API_KEY}",
                        "base_url": "https://api.deepseek.com/v1",
                    }
                },
                f,
            )
            path = f.name

        try:
            settings = load_settings(path)
            assert settings.llm.api_key == "env-key-value"
        finally:
            Path(path).unlink()
            del os.environ["TEST_API_KEY"]
