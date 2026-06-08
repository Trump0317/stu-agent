"""AgentObserver — 事件驱动的可观测性"""

import io
import json
import logging
import sys

from src.agent.agent import Agent
from src.agent.events import (
    AgentEnd,
    AgentStart,
    BeforeAgentStart,
    MessageUpdate,
    RetryEnd,
    RetryStart,
    ToolEnd,
    ToolStart,
    TurnEnd,
    TurnStart,
)
from src.observability.config import ObservabilityConfig
from src.observability.tracer import TraceContext

logger = logging.getLogger(__name__)


class AgentObserver:
    """订阅 Agent 事件，生成结构化日志

    用法：
        observer = AgentObserver(agent, config)
        async for chunk in agent.prompt("你好"):
            pass
        # 日志自动输出到 stdout 或指定文件
    """

    def __init__(
        self,
        agent: Agent,
        config: ObservabilityConfig,
        output: io.StringIO | None = None,
    ):
        self._config = config
        self._agent = agent
        self._trace: TraceContext | None = None
        self._chunk_count = 0
        self._turn_start_ts = 0.0
        self._tool_start_ts = 0.0

        # 输出目标
        if output is not None:
            self._output = output
        elif config.log_file:
            self._output = open(config.log_file, "a", encoding="utf-8")
        else:
            self._output = sys.stdout

        # 挂载到 agent
        self._unsubscribe = agent.subscribe(self._on_event)

    def _is_text_format(self) -> bool:
        return self._config.log_format == "text"

    def _log(self, data: dict) -> None:
        """根据 config 输出到目标"""
        if not self._config.enabled:
            return
        if self._is_text_format():
            line = self._format_text(data)
        else:
            line = json.dumps(data, ensure_ascii=False, default=str)
        self._output.write(line + "\n")
        self._output.flush()

    def _format_text(self, data: dict) -> str:
        """人性化文本格式"""
        event = data.get("event", "?")
        run_id = data.get("run_id", "-")[:8]
        duration = data.get("duration_ms", "")
        dur_str = f" ({duration:.1f}ms)" if duration else ""
        parts = [f"[{run_id}] {event}{dur_str}"]
        # 附加字段
        for k, v in data.items():
            if k not in ("event", "run_id", "ts", "duration_ms"):
                parts.append(f"{k}={v}")
        return " ".join(parts)

    def _on_event(self, event) -> None:
        """事件分发"""
        if isinstance(event, BeforeAgentStart):
            self._on_before_agent_start(event)
        elif isinstance(event, AgentStart):
            self._on_agent_start(event)
        elif isinstance(event, AgentEnd):
            self._on_agent_end(event)
        elif isinstance(event, TurnStart):
            self._on_turn_start(event)
        elif isinstance(event, TurnEnd):
            self._on_turn_end(event)
        elif isinstance(event, MessageUpdate):
            self._on_message_update(event)
        elif isinstance(event, ToolStart):
            self._on_tool_start(event)
        elif isinstance(event, ToolEnd):
            self._on_tool_end(event)
        elif isinstance(event, RetryStart):
            self._on_retry_start(event)
        elif isinstance(event, RetryEnd):
            self._on_retry_end(event)

    # --- 事件处理 ---

    def _on_before_agent_start(self, event: BeforeAgentStart):
        # 每次 prompt 创建新的 TraceContext
        self._trace = TraceContext()
        self._trace.start()
        self._trace.record("before_agent_start")
        self._log({
            "run_id": self._trace.run_id,
            "ts": self._trace.ended_at or self._trace.started_at,
            "event": "before_agent_start",
            "user_input": event.user_input[:500],
        })

    def _on_agent_start(self, event: AgentStart):
        self._chunk_count = 0
        self._trace.record("agent_start")
        self._log({
            "run_id": self._trace.run_id,
            "ts": self._trace.started_at,
            "event": "agent_start",
        })

    def _on_agent_end(self, event: AgentEnd):
        self._trace.record("agent_end")
        self._trace.end()
        self._log({
            "run_id": self._trace.run_id,
            "ts": self._trace.ended_at,
            "event": "agent_end",
            "duration_ms": (self._trace.ended_at - self._trace.started_at) * 1000,
            "messages": len(event.messages),
        })

    def _on_turn_start(self, event: TurnStart):
        self._turn_start_ts = event.turn  # store turn number
        self._chunk_count = 0
        self._trace.record("turn_start", turn=event.turn)
        self._log({
            "run_id": self._trace.run_id,
            "ts": self._trace.started_at,
            "event": "turn_start",
            "turn": event.turn,
        })

    def _on_turn_end(self, event: TurnEnd):
        self._trace.record("turn_end", turn=event.turn)
        # 计算轮次耗时（近似，用 trace 内部 duration）
        turn_duration = None
        if self._trace.events:
            for e in self._trace.events:
                if e.event_type == "turn_end" and e.duration_ms is not None:
                    turn_duration = e.duration_ms
        self._log({
            "run_id": self._trace.run_id,
            "ts": self._trace.started_at,
            "event": "turn_end",
            "turn": event.turn,
            "duration_ms": turn_duration,
            "chunks": self._chunk_count,
            "tool_results": len(event.tool_results),
            "usage": event.usage,
        })

    def _on_message_update(self, event: MessageUpdate):
        if event.delta_type == "text_delta":
            self._chunk_count += 1

    def _on_tool_start(self, event: ToolStart):
        self._trace.record("tool_start", tool=event.tool_name)
        self._log({
            "run_id": self._trace.run_id,
            "ts": self._trace.started_at,
            "event": "tool_start",
            "tool": event.tool_name,
            "args": event.args,
        })

    def _on_tool_end(self, event: ToolEnd):
        self._trace.record("tool_end", tool=event.tool_name, error=event.is_error)
        # 计算工具耗时
        tool_duration = None
        if self._trace.events:
            for e in self._trace.events:
                if e.event_type == "tool_end" and e.data.get("tool") == event.tool_name:
                    tool_duration = e.duration_ms
                    break
        self._log({
            "run_id": self._trace.run_id,
            "ts": self._trace.started_at,
            "event": "tool_end",
            "tool": event.tool_name,
            "duration_ms": tool_duration,
            "error": event.is_error,
        })

    def _on_retry_start(self, event: RetryStart):
        self._trace.record("retry_start", attempt=event.attempt)
        self._log({
            "run_id": self._trace.run_id,
            "ts": self._trace.started_at,
            "event": "retry_start",
            "attempt": event.attempt,
            "error": event.error,
        })

    def _on_retry_end(self, event: RetryEnd):
        self._trace.record("retry_end", attempt=event.attempt)
        self._log({
            "run_id": self._trace.run_id,
            "ts": self._trace.started_at,
            "event": "retry_end",
            "attempt": event.attempt,
            "error": event.error,
        })
