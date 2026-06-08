"""ObservabilityConfig 单元测试

审核人: Trump
审核日期: 2026-06-07
审核状态: [已通过]
"""

import json
import pytest
from src.observability.config import ObservabilityConfig


class TestObservabilityConfig:
    def test_default_values(self):
        """默认配置：enabled=True, log_level=INFO, json 格式, stdout"""
        c = ObservabilityConfig()
        assert c.enabled is True
        assert c.log_level == "INFO"
        assert c.log_format == "json"
        assert c.log_file is None
        assert c.trace_enabled is True

    def test_custom_log_level(self):
        c = ObservabilityConfig(log_level="DEBUG")
        assert c.log_level == "DEBUG"

    def test_text_format(self):
        c = ObservabilityConfig(log_format="text")
        assert c.log_format == "text"

    def test_log_file_path(self):
        c = ObservabilityConfig(log_file="/tmp/agent.log")
        assert c.log_file == "/tmp/agent.log"

    def test_disabled(self):
        """enabled=False 可实例化（Observer 检查此字段决定是否日志）"""
        c = ObservabilityConfig(enabled=False)
        assert c.enabled is False

    def test_trace_disabled(self):
        c = ObservabilityConfig(trace_enabled=False)
        assert c.trace_enabled is False
    def test_log_format_case_insensitive(self):
        """log_format 大小写不敏感（"JSON" → "json"）"""
        c = ObservabilityConfig(log_format="JSON")
        assert c.log_format == "json"


class TestObservabilityConfigValidation:
    def test_invalid_log_format_raises(self):
        """非法 format 抛 ValueError（仅允许 json/text）"""
        with pytest.raises(ValueError, match="log_format"):
            ObservabilityConfig(log_format="xml")

    def test_empty_log_format_raises(self):
        """空字符串 format 抛 ValueError"""
        with pytest.raises(ValueError, match="log_format"):
            ObservabilityConfig(log_format="")

    def test_log_level_not_validated(self):
        """log_level 不做校验（Python logging 接受任意字符串）"""
        c = ObservabilityConfig(log_level="INVALID")
        assert c.log_level == "INVALID"
