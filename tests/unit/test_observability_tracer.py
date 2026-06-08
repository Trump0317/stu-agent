"""TraceContext 单元测试

审核人: Trump
审核日期: 2026-06-07
审核状态: [已通过]
"""

import time
import pytest
from src.observability.tracer import TraceContext, TraceEvent


class TestTraceEvent:
    def test_create(self):
        e = TraceEvent(event_type="turn_start", timestamp=1000.0, duration_ms=None, data={})
        assert e.event_type == "turn_start"
        assert e.timestamp == 1000.0
        assert e.duration_ms is None
        assert e.data == {}

    def test_with_duration(self):
        e = TraceEvent(event_type="tool_end", timestamp=2000.0, duration_ms=45.2,
                       data={"tool": "search"})
        assert e.duration_ms == 45.2
        assert e.data["tool"] == "search"


class TestTraceContext:
    def test_start_creates_run_id_and_timestamp(self):
        ctx = TraceContext()
        assert ctx.run_id is None

        ctx.start()
        assert ctx.run_id is not None
        assert len(ctx.run_id) == 36  # UUID 格式
        assert ctx.started_at > 0
        assert ctx.ended_at == 0.0  # 未结束

    def test_end_sets_ended_at(self):
        ctx = TraceContext()
        ctx.start()
        ctx.end()
        assert ctx.ended_at > ctx.started_at

    def test_record(self):
        """record 生成 TraceEvent 并加入 events 列表"""
        ctx = TraceContext()
        ctx.start()
        ctx.record("turn_start", turn=1)
        ctx.record("turn_end", turn=1, chunks=42)

        assert len(ctx.events) == 2

        e1 = ctx.events[0]
        assert e1.event_type == "turn_start"
        assert e1.timestamp >= ctx.started_at
        assert e1.data["turn"] == 1

        e2 = ctx.events[1]
        assert e2.event_type == "turn_end"
        assert e2.timestamp >= ctx.started_at
        assert e2.data["chunks"] == 42

    def test_record_calculates_duration(self):
        """连续 record 自动计算距上次事件的 duration_ms"""
        ctx = TraceContext()
        ctx.start()
        ctx.record("event_a")
        time.sleep(0.05)
        ctx.record("event_b")
        assert len(ctx.events) == 2
        # 第一条无 duration（无上次事件），第二条有
        assert ctx.events[0].duration_ms is None
        assert ctx.events[1].duration_ms is not None
        assert ctx.events[1].duration_ms > 0

    def test_first_record_has_no_duration(self):
        """第一个 record 的 duration_ms 为 None（无上次事件）"""
        ctx = TraceContext()
        ctx.start()
        ctx.record("agent_start")
        assert ctx.events[0].duration_ms is None

    def test_to_dict(self):
        """to_dict 输出可序列化"""
        ctx = TraceContext()
        ctx.start()
        ctx.record("turn_start", turn=1)
        ctx.end()

        d = ctx.to_dict()
        assert d["run_id"] == ctx.run_id
        assert d["duration_ms"] == (ctx.ended_at - ctx.started_at) * 1000
        assert len(d["events"]) == 1
        ev = d["events"][0]
        assert ev["event_type"] == "turn_start"
        assert ev["timestamp"] > 0
        assert ev["duration_ms"] is None
        assert ev["data"] == {"turn": 1}


class TestTraceContextBoundary:
    def test_double_start_overwrites(self):
        """重复 start() 重置所有状态"""
        ctx = TraceContext()
        ctx.start()
        first_run_id = ctx.run_id
        ctx.record("e1")
        ctx.start()  # 第二次
        assert ctx.run_id != first_run_id
        assert ctx.events == []
        assert ctx.ended_at == 0.0

    def test_end_before_start_noop(self):
        """start() 前调 end() 不抛异常"""
        ctx = TraceContext()
        ctx.end()  # noop
        assert ctx.ended_at == 0.0

    def test_record_before_start_ignored(self):
        """start() 前调 record() 不记录"""
        ctx = TraceContext()
        ctx.record("early")
        assert ctx.events == []

    def test_double_end_noop(self):
        """重复 end() 不抛异常，ended_at 不变"""
        ctx = TraceContext()
        ctx.start()
        ctx.end()
        first_ended = ctx.ended_at
        # 第二次 end 不修改 ended_at
        ctx.end()
        assert ctx.ended_at == first_ended
