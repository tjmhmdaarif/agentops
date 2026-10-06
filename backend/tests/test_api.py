"""API tests via FastAPI TestClient (runs the real app + lifespan)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import build_app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path.as_posix()}/api_test.db")
    settings = Settings.from_env(env_file=None)
    settings.simulation_autostart = True
    settings.random_seed = 42
    settings.iforest_min_samples = 10**9
    app = build_app(settings)
    with TestClient(app) as c:
        # Every API route except /api/health and /api/auth/login requires a session.
        r = c.post("/api/auth/login", json={"username": "admin", "password": "agentops"})
        assert r.status_code == 200
        yield c


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "healthy"
    assert body["database"] == "connected"
    assert body["simulation"] == "running"
    assert body["agent"] in {"rule-engine", "llm"}


def test_health_is_public_without_login(tmp_path, monkeypatch):
    """Platform health checks must work without a session cookie."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path.as_posix()}/health_pub.db")
    app = build_app(Settings.from_env(env_file=None))
    with TestClient(app) as anon:
        assert anon.get("/api/health").status_code == 200


def test_api_requires_login(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path.as_posix()}/auth_req.db")
    app = build_app(Settings.from_env(env_file=None))
    with TestClient(app) as anon:
        assert anon.get("/api/devices").status_code == 401
        assert anon.get("/api/incidents").status_code == 401
        bad = anon.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
        assert bad.status_code == 401
        ok = anon.post("/api/auth/login", json={"username": "admin", "password": "agentops"})
        assert ok.status_code == 200
        assert anon.get("/api/devices").status_code == 200
        anon.post("/api/auth/logout")
        assert anon.get("/api/devices").status_code == 401


def test_devices_list(client):
    r = client.get("/api/devices")
    assert r.status_code == 200
    devices = r.json()
    assert len(devices) == 12
    first = devices[0]
    for field in ("id", "status", "health_score", "firmware_version", "latest_metrics"):
        assert field in first


def test_device_detail_and_404(client):
    assert client.get("/api/devices/EDGE-001").status_code == 200
    assert client.get("/api/devices/NOPE-999").status_code == 404


def test_telemetry_endpoint(client):
    r = client.get("/api/devices/EDGE-001/telemetry", params={"metric": "temperature", "minutes": 5})
    assert r.status_code == 200
    body = r.json()
    assert body["metric"] == "temperature"
    assert "points" in body and "baseline" in body


def test_telemetry_unknown_metric(client):
    r = client.get("/api/devices/EDGE-001/telemetry", params={"metric": "flux_capacitance"})
    assert r.status_code == 404


def test_incidents_list_schema(client):
    r = client.get("/api/incidents")
    assert r.status_code == 200
    body = r.json()
    assert set(body) >= {"items", "total", "limit", "offset"}


def test_simulation_control(client):
    assert client.post("/api/simulation/pause").json()["status"] == "PAUSED"
    assert client.post("/api/simulation/resume").json()["status"] == "RUNNING"
    assert client.post("/api/simulation/speed", json={"speed": 2.0}).json()["speed"] == 2.0
    assert client.get("/api/simulation/status").status_code == 200


def test_inject_validation_and_404(client):
    bad = client.post("/api/simulation/inject", json={
        "device_id": "EDGE-001", "scenario": "not_a_scenario", "severity": "high",
    })
    assert bad.status_code == 422
    missing = client.post("/api/simulation/inject", json={
        "device_id": "NOPE-001", "scenario": "temperature_spike", "severity": "high",
    })
    assert missing.status_code == 404


def test_inject_creates_incident(client):
    client.post("/api/simulation/speed", json={"speed": 20.0})
    ok = client.post("/api/simulation/inject", json={
        "device_id": "EDGE-004", "scenario": "temperature_spike", "severity": "critical",
    })
    assert ok.status_code == 200 and ok.json()["ok"]
    # give the background loop a moment at 20x speed
    import time
    deadline = time.time() + 15
    incident_id = None
    while time.time() < deadline:
        body = client.get("/api/incidents", params={"device_id": "EDGE-004"}).json()
        if body["total"] > 0:
            incident_id = body["items"][0]["id"]
            break
        time.sleep(0.3)
    assert incident_id is not None
    timeline = client.get(f"/api/incidents/{incident_id}/timeline")
    assert timeline.status_code == 200
    assert len(timeline.json()) >= 1


def test_analytics_overview(client):
    r = client.get("/api/analytics/overview")
    assert r.status_code == 200
    body = r.json()
    assert body["devices_total"] == 12
    assert "auto_resolution_rate" in body
    assert "severity_distribution" in body


def test_manual_restart_action(client):
    r = client.post("/api/devices/EDGE-003/actions/restart")
    assert r.status_code == 200
    assert r.json()["status"] in {"completed", "skipped"}


def test_sse_stream_connects(tmp_path, monkeypatch):
    """SSE is tested against a real uvicorn server: starlette's TestClient
    portal cannot consume unbounded StreamingResponses."""
    import threading
    import time

    import httpx
    import uvicorn

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path.as_posix()}/sse_test.db")
    settings = Settings.from_env(env_file=None)
    settings.random_seed = 42
    settings.iforest_min_samples = 10**9
    app = build_app(settings)

    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8124, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        for _ in range(50):  # wait for startup
            try:
                httpx.get("http://127.0.0.1:8124/api/health", timeout=1)
                break
            except Exception:
                time.sleep(0.2)
        session = httpx.Client()
        login = session.post("http://127.0.0.1:8124/api/auth/login",
                             json={"username": "admin", "password": "agentops"})
        assert login.status_code == 200
        with session.stream("GET", "http://127.0.0.1:8124/api/events/stream", timeout=10) as r:
            assert r.status_code == 200
            assert r.headers["content-type"].startswith("text/event-stream")
            events = []
            for line in r.iter_lines():
                if line.startswith("event:"):
                    events.append(line.split(":", 1)[1].strip())
                if "telemetry" in events or len(events) >= 3:
                    break
        assert "connected" in events
        assert "telemetry" in events
    finally:
        server.should_exit = True


def test_config_endpoint_hides_secrets(client):
    r = client.get("/api/config")
    assert r.status_code == 200
    assert "api_key" not in r.text.lower()
