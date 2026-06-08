"""TraceContext — 单次 prompt() 调用追踪"""

import time
import uuid
from dataclasses import dataclass, field


@dataclass
class TraceEvent:
    """单条追踪事件

    Attributes:
        event_type: 事件类型（如 "turn_start", "tool_end"）
        timestamp: 时间戳（time.time()）
        duration_ms: 距上次事件的毫秒数（首条为 None）
        data: 附加数据
    """

    event_type: str
    timestamp: float
    duration_ms: float | None = None
    data: dict = field(default_factory=dict)


class TraceContext:
    """单次 prompt() 调用追踪上下文

    生命周期：start() → record(...) × N → end() → to_dict()
    """

    def __init__(self):
        self.run_id: str | None = None
        self.started_at: float = 0.0
        self.ended_at: float = 0.0
        self.events: list[TraceEvent] = []
        self._last_ts: float | None = None
        self._started = False

    def start(self) -> None:
        """开始追踪（重置所有状态）"""
        self.run_id = str(uuid.uuid4())
        self.started_at = time.time()
        self.ended_at = 0.0
        self.events.clear()
        self._last_ts = None
        self._started = True

    def end(self) -> None:
        """结束追踪（重复调用不更新 ended_at）"""
        if not self._started or self.ended_at > 0:
            return
        self.ended_at = time.time()

    def record(self, event_type: str, **kwargs) -> None:
        """记录一条事件

        Args:
            event_type: 事件类型标识
            **kwargs: 附加数据，存入 TraceEvent.data
        """
        if not self._started:
            return
        now = time.time()
        duration_ms = None
        if self._last_ts is not None:
            duration_ms = (now - self._last_ts) * 1000
        self._last_ts = now

        self.events.append(TraceEvent(
            event_type=event_type,
            timestamp=now,
            duration_ms=duration_ms,
            data=dict(kwargs),
        ))

    def to_dict(self) -> dict:
        """序列化为字典

        Returns:
            {"run_id": ..., "duration_ms": ..., "events": [...]}
        """
        total_ms = 0.0
        if self.ended_at > 0 and self.started_at > 0:
            total_ms = (self.ended_at - self.started_at) * 1000

        return {
            "run_id": self.run_id,
            "duration_ms": total_ms,
            "events": [
                {
                    "event_type": e.event_type,
                    "timestamp": e.timestamp,
                    "duration_ms": e.duration_ms,
                    "data": e.data,
                }
                for e in self.events
            ],
        }
