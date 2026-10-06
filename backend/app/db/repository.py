"""Repository layer — the only place SQLAlchemy queries live."""
from __future__ import annotations

import time
from typing import Any, Iterable, Optional

from sqlalchemy import asc, desc, func, select

from app.db.database import Database
from app.db.models import AgentEvent, Device, DeviceAction, Incident, Telemetry


class Repository:
    def __init__(self, db: Database) -> None:
        self.db = db

    # ------------------------------------------------------------------ devices
    def upsert_device(self, device: Device) -> Device:
        with self.db.session() as s:
            s.merge(device)
        return device

    def get_device(self, device_id: str) -> Optional[Device]:
        with self.db.session() as s:
            return s.get(Device, device_id)

    def list_devices(self) -> list[Device]:
        with self.db.session() as s:
            return list(s.scalars(select(Device).order_by(asc(Device.id))))

    def update_device_fields(self, device_id: str, **fields: Any) -> None:
        with self.db.session() as s:
            device = s.get(Device, device_id)
            if device is None:
                return
            for key, value in fields.items():
                setattr(device, key, value)

    def update_devices_bulk(self, fields_by_id: dict[str, dict[str, Any]]) -> None:
        """One session for a whole-fleet tick update (no per-device session churn)."""
        with self.db.session() as s:
            devices = {d.id: d for d in s.scalars(select(Device))}
            for device_id, fields in fields_by_id.items():
                device = devices.get(device_id)
                if device is None:
                    continue
                for key, value in fields.items():
                    setattr(device, key, value)

    def last_restart_times(self) -> dict[str, float]:
        with self.db.session() as s:
            rows = s.execute(
                select(DeviceAction.device_id, func.max(DeviceAction.started_at))
                .where(DeviceAction.action == "restart_device")
                .group_by(DeviceAction.device_id)
            ).all()
        return {device_id: float(ts) for device_id, ts in rows}

    def open_incident_counts(self) -> dict[str, int]:
        with self.db.session() as s:
            rows = s.execute(
                select(Incident.device_id, func.count(Incident.id))
                .where(Incident.status.in_(["OPEN", "INVESTIGATING", "MITIGATING", "MONITORING"]))
                .group_by(Incident.device_id)
            ).all()
        return {device_id: int(count) for device_id, count in rows}

    def delete_devices(self) -> None:
        with self.db.session() as s:
            s.query(Telemetry).delete()
            s.query(DeviceAction).delete()
            s.query(AgentEvent).delete()
            s.query(Incident).delete()
            s.query(Device).delete()

    # ---------------------------------------------------------------- telemetry
    def insert_telemetry_batch(self, rows: Iterable[Telemetry]) -> int:
        rows = list(rows)
        if not rows:
            return 0
        with self.db.session() as s:
            s.add_all(rows)
        return len(rows)

    def recent_telemetry(
        self, device_id: str, metric: str, limit: int = 60, since: float | None = None
    ) -> list[Telemetry]:
        with self.db.session() as s:
            stmt = select(Telemetry).where(
                Telemetry.device_id == device_id, Telemetry.metric == metric
            )
            if since is not None:
                stmt = stmt.where(Telemetry.timestamp >= since)
            stmt = stmt.order_by(desc(Telemetry.timestamp)).limit(limit)
            return list(reversed(list(s.scalars(stmt))))

    def telemetry_range(
        self, device_id: str, metric: str, start: float, end: float, max_points: int = 600
    ) -> list[Telemetry]:
        with self.db.session() as s:
            stmt = (
                select(Telemetry)
                .where(
                    Telemetry.device_id == device_id,
                    Telemetry.metric == metric,
                    Telemetry.timestamp >= start,
                    Telemetry.timestamp <= end,
                )
                .order_by(asc(Telemetry.timestamp))
            )
            rows = list(s.scalars(stmt))
        if len(rows) > max_points:  # simple downsample by stride
            stride = max(1, len(rows) // max_points)
            rows = rows[::stride]
        return rows

    def count_telemetry(self) -> int:
        with self.db.session() as s:
            return int(s.scalar(select(func.count(Telemetry.id))) or 0)

    def prune_telemetry_older_than(self, cutoff: float) -> int:
        with self.db.session() as s:
            deleted = s.query(Telemetry).filter(Telemetry.timestamp < cutoff).delete()
        return int(deleted or 0)

    # ---------------------------------------------------------------- incidents
    def create_incident(self, incident: Incident) -> Incident:
        with self.db.session() as s:
            s.add(incident)
            s.flush()
            s.refresh(incident)
        return incident

    def get_incident(self, incident_id: int) -> Optional[Incident]:
        with self.db.session() as s:
            return s.get(Incident, incident_id)

    def update_incident(self, incident_id: int, **fields: Any) -> Optional[Incident]:
        fields["updated_at"] = time.time()
        with self.db.session() as s:
            incident = s.get(Incident, incident_id)
            if incident is None:
                return None
            for key, value in fields.items():
                setattr(incident, key, value)
            s.flush()
            s.refresh(incident)
            return incident

    def list_incidents(
        self,
        status: str | None = None,
        device_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Incident], int]:
        with self.db.session() as s:
            stmt = select(Incident)
            count_stmt = select(func.count(Incident.id))
            if status:
                stmt = stmt.where(Incident.status == status)
                count_stmt = count_stmt.where(Incident.status == status)
            if device_id:
                stmt = stmt.where(Incident.device_id == device_id)
                count_stmt = count_stmt.where(Incident.device_id == device_id)
            total = int(s.scalar(count_stmt) or 0)
            items = list(
                s.scalars(stmt.order_by(desc(Incident.created_at)).limit(limit).offset(offset))
            )
        return items, total

    def open_incidents(self) -> list[Incident]:
        with self.db.session() as s:
            return list(
                s.scalars(
                    select(Incident).where(
                        Incident.status.in_(["OPEN", "INVESTIGATING", "MITIGATING", "MONITORING"])
                    )
                )
            )

    def find_active_incident(self, device_id: str, metric: str) -> Optional[Incident]:
        """Used for duplicate suppression / grouping."""
        with self.db.session() as s:
            return s.scalars(
                select(Incident)
                .where(
                    Incident.device_id == device_id,
                    Incident.metric == metric,
                    Incident.status.in_(["OPEN", "INVESTIGATING", "MITIGATING", "MONITORING"]),
                )
                .order_by(desc(Incident.created_at))
            ).first()

    def find_active_incident_for_device(self, device_id: str, within_seconds: float = 120.0) -> Optional[Incident]:
        """Most recent active incident on a device regardless of metric — used to
        group correlated multi-metric failures into one incident."""
        cutoff = time.time() - within_seconds
        with self.db.session() as s:
            return s.scalars(
                select(Incident)
                .where(
                    Incident.device_id == device_id,
                    Incident.created_at >= cutoff,
                    Incident.status.in_(["OPEN", "INVESTIGATING", "MITIGATING", "MONITORING"]),
                )
                .order_by(desc(Incident.created_at))
            ).first()

    def recent_incidents_for_device(self, device_id: str, limit: int = 10) -> list[Incident]:
        with self.db.session() as s:
            return list(
                s.scalars(
                    select(Incident)
                    .where(Incident.device_id == device_id)
                    .order_by(desc(Incident.created_at))
                    .limit(limit)
                )
            )

    def incidents_since(self, since: float) -> list[Incident]:
        with self.db.session() as s:
            return list(
                s.scalars(select(Incident).where(Incident.created_at >= since))
            )

    # -------------------------------------------------------------- agent events
    def add_agent_event(self, event: AgentEvent) -> AgentEvent:
        with self.db.session() as s:
            s.add(event)
            s.flush()
            s.refresh(event)
        return event

    def incident_timeline(self, incident_id: int) -> list[AgentEvent]:
        with self.db.session() as s:
            return list(
                s.scalars(
                    select(AgentEvent)
                    .where(AgentEvent.incident_id == incident_id)
                    .order_by(asc(AgentEvent.timestamp), asc(AgentEvent.id))
                )
            )

    # -------------------------------------------------------------- device actions
    def add_device_action(self, action: DeviceAction) -> DeviceAction:
        with self.db.session() as s:
            s.add(action)
            s.flush()
            s.refresh(action)
        return action

    def update_device_action(self, action_id: int, **fields: Any) -> None:
        with self.db.session() as s:
            row = s.get(DeviceAction, action_id)
            if row is None:
                return
            for key, value in fields.items():
                setattr(row, key, value)

    def last_action_for_device(self, device_id: str, action: str) -> Optional[DeviceAction]:
        with self.db.session() as s:
            return s.scalars(
                select(DeviceAction)
                .where(DeviceAction.device_id == device_id, DeviceAction.action == action)
                .order_by(desc(DeviceAction.started_at))
            ).first()

    def actions_for_device(self, device_id: str, limit: int = 20) -> list[DeviceAction]:
        with self.db.session() as s:
            return list(
                s.scalars(
                    select(DeviceAction)
                    .where(DeviceAction.device_id == device_id)
                    .order_by(desc(DeviceAction.started_at))
                    .limit(limit)
                )
            )
