"""Application configuration loaded from environment variables / .env file."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]  # backend/
PROJECT_ROOT = BASE_DIR.parent                  # agentops-2/


def _env_bool(key: str, default: bool) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, default))
    except (TypeError, ValueError):
        return default


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, default))
    except (TypeError, ValueError):
        return default


@dataclass
class Settings:
    """Runtime settings. All values are environment overridable."""

    app_env: str = "development"
    database_url: str = f"sqlite:///{(PROJECT_ROOT / 'data' / 'agentops.db').as_posix()}"

    # Simulation
    simulation_enabled: bool = True
    simulation_autostart: bool = True
    simulation_speed: float = 1.0
    simulation_tick_seconds: float = 1.0
    device_count: int = 12
    random_seed: int | None = 42

    # Detection
    anomaly_threshold: float = 0.55          # min fused score to consider anomalous
    anomaly_persistence: int = 3             # consecutive samples required
    incident_cooldown_seconds: float = 60.0  # duplicate suppression window
    zscore_threshold: float = 3.0
    ewma_threshold: float = 2.5
    roc_threshold: float = 0.45              # relative change (fraction)
    iforest_min_samples: int = 60            # min vectors before IF is trained
    iforest_retrain_every: int = 120         # retrain cadence (samples)
    rolling_window: int = 40

    # Agent
    agent_max_remediation_attempts: int = 2
    agent_recovery_samples: int = 4          # samples needed to confirm recovery
    agent_recovery_score: float = 0.40       # score below which device is "recovered"
    agent_action_cooldown_seconds: float = 30.0  # idempotency window per device/action
    agent_max_concurrent: int = 4

    # LLM (optional)
    llm_enabled: bool = False
    llm_provider: str = "anthropic"
    llm_model: str = "claude-sonnet-4-5"
    anthropic_api_key: str = ""
    llm_timeout_seconds: float = 12.0

    # Auth
    admin_username: str = "admin"
    admin_password: str = "agentops"
    show_demo_creds: bool = True          # display demo credentials on the login page

    # Feature flags — gate experimental work so main stays shippable.
    # Env format: FEATURE_FLAGS="predictive_health=true,chaos_controls=false"
    feature_flags: dict[str, bool] = field(default_factory=lambda: {
        "predictive_health": False,
        "chaos_controls": False,
    })

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = field(default_factory=lambda: [
        "http://localhost:5173", "http://127.0.0.1:5173",
    ])
    static_dir: str = str(PROJECT_ROOT / "frontend" / "dist")

    @classmethod
    def from_env(cls, env_file: str | None = ".env") -> "Settings":
        if env_file:
            load_dotenv(BASE_DIR / env_file, override=False)
            load_dotenv(PROJECT_ROOT / ".env", override=False)
        s = cls()
        s.app_env = os.getenv("APP_ENV", s.app_env)
        s.database_url = os.getenv("DATABASE_URL", s.database_url)
        s.simulation_enabled = _env_bool("SIMULATION_ENABLED", s.simulation_enabled)
        s.simulation_autostart = _env_bool("SIMULATION_AUTOSTART", s.simulation_autostart)
        s.simulation_speed = _env_float("SIMULATION_SPEED", s.simulation_speed)
        s.device_count = _env_int("DEVICE_COUNT", s.device_count)
        seed = os.getenv("RANDOM_SEED")
        s.random_seed = int(seed) if seed not in (None, "", "none") else None
        s.anomaly_threshold = _env_float("ANOMALY_THRESHOLD", s.anomaly_threshold)
        s.llm_enabled = _env_bool("LLM_ENABLED", s.llm_enabled)
        s.llm_provider = os.getenv("LLM_PROVIDER", s.llm_provider)
        s.llm_model = os.getenv("LLM_MODEL", s.llm_model)
        s.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", s.anthropic_api_key)
        s.host = os.getenv("HOST", s.host)
        s.port = _env_int("PORT", s.port)
        s.admin_username = os.getenv("ADMIN_USERNAME", s.admin_username)
        s.admin_password = os.getenv("ADMIN_PASSWORD", s.admin_password)
        s.show_demo_creds = _env_bool("SHOW_DEMO_CREDS", s.app_env != "production")
        flags = os.getenv("FEATURE_FLAGS")
        if flags:
            for pair in flags.split(","):
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    s.feature_flags[key.strip()] = value.strip().lower() in {"1", "true", "on", "yes"}
        origins = os.getenv("CORS_ORIGINS")
        if origins:
            s.cors_origins = [o.strip() for o in origins.split(",") if o.strip()]
        return s
