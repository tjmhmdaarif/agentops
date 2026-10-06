from __future__ import annotations

import pytest

from app.core.config import Settings
from app.core.events import EventBus
from app.core.runtime import AgentOpsRuntime


@pytest.fixture()
def settings(tmp_path, monkeypatch) -> Settings:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path.as_posix()}/test.db")
    s = Settings.from_env(env_file=None)
    s.random_seed = 42
    s.device_count = 12
    s.iforest_min_samples = 10**9      # unit tests isolate univariate detectors
    return s


@pytest.fixture()
def bus() -> EventBus:
    return EventBus()


@pytest.fixture()
def runtime(settings, bus) -> AgentOpsRuntime:
    rt = AgentOpsRuntime(settings, bus=bus)
    rt.init_db()
    rt.engine.start()
    return rt


def run_ticks(rt: AgentOpsRuntime, n: int) -> None:
    for _ in range(n):
        rt.tick()
