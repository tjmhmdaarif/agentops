"""SQLAlchemy ORM models. API code never touches these directly — use repository/services."""
from __future__ import annotations

import time
from typing import Optional

from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


def _now() -> float:
    return time.time()


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)          # e.g. EDGE-001
    name: Mapped[str] = mapped_column(String(64))
    device_type: Mapped[str] = mapped_column(String(48))
    location: Mapped[str] = mapped_column(String(96))
    status: Mapped[str] = mapped_column(String(16), default="ONLINE", index=True)
    health_score: Mapped[float] = mapped_column(Float, default=100.0)
    last_seen: Mapped[float] = mapped_column(Float, default=_now)
    created_at: Mapped[float] = mapped_column(Float, default=_now)
    firmware_version: Mapped[str] = mapped_column(String(24), default="2.4.1")
    uptime: Mapped[float] = mapped_column(Float, default=0.0)              # seconds
    restart_count: Mapped[int] = mapped_column(Integer, default=0)


class Telemetry(Base):
    __tablename__ = "telemetry"
    __table_args__ = (
        Index("ix_telemetry_device_metric_ts", "device_id", "metric", "timestamp"),
        Index("ix_telemetry_ts", "timestamp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(32), ForeignKey("devices.id"))
    timestamp: Mapped[float] = mapped_column(Float, default=_now)
    metric: Mapped[str] = mapped_column(String(32))
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(16), default="")


class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = (
        Index("ix_incidents_status", "status"),
        Index("ix_incidents_device", "device_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(32), ForeignKey("devices.id"))
    metric: Mapped[str] = mapped_column(String(32))
    severity: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(20), default="OPEN")
    detector: Mapped[str] = mapped_column(String(64))                      # e.g. "zscore+iforest"
    anomaly_score: Mapped[float] = mapped_column(Float, default=0.0)
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[float] = mapped_column(Float, default=_now)
    updated_at: Mapped[float] = mapped_column(Float, default=_now)
    resolved_at: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    action_taken: Mapped[str] = mapped_column(String(48), default="")
    resolution_notes: Mapped[str] = mapped_column(Text, default="")


class AgentEvent(Base):
    __tablename__ = "agent_events"
    __table_args__ = (Index("ix_agent_events_incident", "incident_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[int] = mapped_column(Integer, ForeignKey("incidents.id"))
    timestamp: Mapped[float] = mapped_column(Float, default=_now)
    event_type: Mapped[str] = mapped_column(String(32))                    # e.g. TOOL_STARTED
    message: Mapped[str] = mapped_column(Text, default="")
    tool_name: Mapped[str] = mapped_column(String(48), default="")
    tool_input: Mapped[str] = mapped_column(Text, default="")              # JSON
    tool_output: Mapped[str] = mapped_column(Text, default="")             # JSON
    duration_ms: Mapped[float] = mapped_column(Float, default=0.0)


class DeviceAction(Base):
    __tablename__ = "device_actions"
    __table_args__ = (Index("ix_device_actions_device", "device_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(32), ForeignKey("devices.id"))
    incident_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(48))
    status: Mapped[str] = mapped_column(String(16), default="PENDING")     # PENDING/RUNNING/COMPLETED/FAILED/SKIPPED
    reason: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[float] = mapped_column(Float, default=_now)
    completed_at: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    result: Mapped[str] = mapped_column(Text, default="")
