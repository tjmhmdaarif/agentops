"""AgentOps runtime — orchestrates simulator → detection → incidents → agents.

Synchronous tick() for determinism (tests drive it directly); the async
run_loop() paces ticks at wall-clock speed in production.
"""
from __future__ import annotations

import asyncio
import time

from app.agent.agent import AgentRuntime
from app.agent.llm import LLMDecider
from app.core.auth import AuthService
from app.core.config import Settings
from app.core.events import EventBus, bus as global_bus
from app.core.logging import get_logger
from app.db.database import Database
from app.db.models import Device, Telemetry
from app.db.repository import Repository
from app.detection.detector import HybridDetector
from app.incidents.manager import IncidentManager
from app.services.analytics_service import AnalyticsService
from app.services.fleet_service import FleetService
from app.services.incident_service import IncidentService
from app.services.telemetry_service import TelemetryService
from app.simulation.engine import RUNNING, SimulationEngine
from app.simulation.telemetry import METRICS
from app.tools import build_default_registry
from app.tools.registry import ToolContext

log = get_logger("runtime")

PRUNE_EVERY_TICKS = 600
TELEMETRY_RETENTION_S = 6 * 3600


class AgentOpsRuntime:
    def __init__(self, settings: Settings, bus: EventBus | None = None) -> None:
        self.settings = settings
        self.bus = bus or global_bus
        self.db = Database(settings)
        self.repo = Repository(self.db)
        self.auth = AuthService(self.db)
        self.engine = SimulationEngine(settings)
        self.detector = HybridDetector(settings)
        self.manager = IncidentManager(self.repo, self.bus, settings)
        self.registry = build_default_registry()
        self.tool_ctx = ToolContext(
            repo=self.repo, engine=self.engine, detector=self.detector,
            bus=self.bus, settings=settings,
        )
        self.llm = LLMDecider(settings, self.registry)
        self.agents = AgentRuntime(
            repo=self.repo, manager=self.manager, registry=self.registry,
            tool_ctx=self.tool_ctx, llm=self.llm, bus=self.bus, settings=settings,
        )
        self.manager.on_incident_created = self.agents.handle_incident
        self.fleet = FleetService(self.repo, self.engine, self.detector)
        self.telemetry = TelemetryService(self.repo, self.detector)
        self.incidents = IncidentService(self.repo)
        self.analytics = AnalyticsService(self.repo)
        self.started_at = time.time()
        self._offline_ticks: dict[str, int] = {}
        self._running_task: asyncio.Task | None = None

    # --------------------------------------------------------------- lifecycle
    def init_db(self) -> None:
        self.db.create_all()
        self.auth.ensure_admin(self.settings.admin_username, self.settings.admin_password)
        self._seed_fleet()

    def _seed_fleet(self) -> None:
        existing = {d.id for d in self.repo.list_devices()}
        for device_id, sim in self.engine.devices.items():
            if device_id not in existing:
                self.repo.upsert_device(Device(
                    id=sim.id, name=sim.name, device_type=sim.device_type,
                    location=sim.location, status="ONLINE", health_score=100.0,
                    firmware_version=sim.firmware_version, created_at=sim.created_at,
                ))

    # ------------------------------------------------------------------- tick
    def tick(self) -> None:
        readings = self.engine.step()
        if not readings and self.engine.status != RUNNING:
            return
        now = time.time()

        # 1) Persist telemetry in one batch.
        rows = [
            Telemetry(device_id=device_id, timestamp=ts, metric=metric,
                      value=value, unit=METRICS[metric].unit)
            for device_id, ts, metrics in readings
            for metric, value in metrics.items()
        ]
        self.repo.insert_telemetry_batch(rows)

        # 2) Detect anomalies.
        all_detections = []
        for device_id, ts, metrics in readings:
            all_detections.extend(self.detector.evaluate(device_id, metrics, self.engine.tick))
        for det in all_detections:
            self.bus.publish("anomaly_detected", {
                "device_id": det.device_id, "metric": det.metric,
                "score": det.score, "severity": det.severity,
                "detectors": det.detectors, "explanation": det.explanation,
                "value": det.value, "baseline": det.baseline,
            })
        self.manager.handle_detections(all_detections)

        # 3) Offline watchdog.
        for device_id, sim in self.engine.devices.items():
            if sim.is_offline:
                self._offline_ticks[device_id] = self._offline_ticks.get(device_id, 0) + 1
                if self._offline_ticks[device_id] == 3:
                    self.manager.ensure_offline_incident(device_id)
            else:
                self._offline_ticks[device_id] = 0

        # 4) Sync health/status into DB; publish changes.
        changes, health_map = self.fleet.sync_from_simulation()
        for change in changes:
            self.bus.publish("device_status_changed", change)

        # 5) Publish per-device telemetry (with fresh health).
        for device_id, ts, metrics in readings:
            health, status = health_map.get(device_id, (100.0, "ONLINE"))
            self.bus.publish("telemetry", {
                "device_id": device_id, "ts": ts, "metrics": metrics,
                "health_score": health, "status": status,
            })

        # 6) Advance agents.
        self.agents.advance_all()

        # 6) Periodic retention pruning.
        if self.engine.tick % PRUNE_EVERY_TICKS == 0:
            pruned = self.repo.prune_telemetry_older_than(now - TELEMETRY_RETENTION_S)
            if pruned:
                log.info("telemetry_pruned rows=%d", pruned)

    # --------------------------------------------------------------- async loop
    async def run_loop(self) -> None:
        interval = self.settings.simulation_tick_seconds
        log.info("runtime_loop_started interval=%.2fs", interval)
        while True:
            if self.engine.status == RUNNING:
                started = time.perf_counter()
                try:
                    self.tick()
                except Exception:
                    log.exception("tick_error")
                elapsed = time.perf_counter() - started
                # Guard against a zero/negative speed (e.g. SIMULATION_SPEED=0 in
                # the environment) — without this the divide would raise and kill
                # the background loop, silently freezing the whole simulation.
                speed = self.engine.speed if self.engine.speed and self.engine.speed > 0 else 1.0
                await asyncio.sleep(max(0.02, interval / speed - elapsed))
            else:
                await asyncio.sleep(0.2)

    def start_background(self) -> None:
        if self._running_task is None:
            self._running_task = asyncio.create_task(self.run_loop())

    async def stop_background(self) -> None:
        if self._running_task is not None:
            self._running_task.cancel()
            try:
                await self._running_task
            except asyncio.CancelledError:
                pass
            self._running_task = None

    # ------------------------------------------------------------------ control
    def reset(self) -> None:
        self.engine.reset()
        self.detector.reset()
        self.agents.reset()
        self.manager.clear_cooldowns()
        self._offline_ticks.clear()
        self.repo.delete_devices()
        self._seed_fleet()
        self.bus.publish("simulation_status", self.engine.summary())
        log.info("runtime_reset")

    # ------------------------------------------------------------------ health
    def health(self) -> dict[str, str | float]:
        try:
            self.repo.count_telemetry()
            db_status = "connected"
        except Exception:
            db_status = "error"
        return {
            "status": "healthy" if db_status == "connected" else "degraded",
            "database": db_status,
            "simulation": self.engine.status.lower(),
            "event_bus": "healthy",
            "agent": "llm" if self.llm.available else "rule-engine",
            "llm": "enabled" if self.settings.llm_enabled else "disabled",
            "uptime_s": round(time.time() - self.started_at, 0),
        }
