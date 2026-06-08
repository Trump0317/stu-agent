"""可观测性配置"""

from dataclasses import dataclass

VALID_FORMATS = frozenset({"json", "text"})


@dataclass
class ObservabilityConfig:
    """可观测性配置

    Attributes:
        enabled: 总开关（False 时不记录任何日志）
        log_level: 日志级别（透传给 Python logging）
        log_format: 输出格式（json / text）
        log_file: 文件输出路径（None=stdout）
        trace_enabled: 计时追踪开关
    """

    enabled: bool = True
    log_level: str = "INFO"
    log_format: str = "json"
    log_file: str | None = None
    trace_enabled: bool = True

    def __post_init__(self):
        """校验 log_format"""
        self.log_format = self.log_format.strip().lower()
        if self.log_format not in VALID_FORMATS:
            raise ValueError(
                f"log_format 必须为 json 或 text，收到: {self.log_format!r}"
            )
