# AgentOps 2.0 — Complete Build & Deployment Journey

**A step-by-step engineering record. Keep this file — it is the full recipe to
rebuild, restore, or re-deploy the project from zero.**

- **Live production:** https://agentops-o50e.onrender.com
- **Repository:** https://github.com/tjmhmdaarif/agentops
- **Legacy (original Streamlit version, archived):** https://github.com/tjmhmdaarif/agentops-legacy
- **Built:** October 6, 2026 — concept → production in one day

---

## 1. What the product is

An autonomous IoT fleet intelligence (AIOps) platform:

```
SIMULATED FLEET (12 devices × 7 metrics, real failure scenarios)
  → HYBRID ANOMALY DETECTION (robust z-score + fast/slow EWMA + rate-of-change + Isolation Forest)
  → INCIDENT MANAGER (persistence, cooldowns, correlated grouping)
  → AUTONOMOUS AGENT (investigate → decide → remediate → verify recovery → resolve/escalate)
  → SSE EVENT STREAM → REACT DASHBOARD (live, dark, cinematic)
  → PARTICLE GLOBE LANDING (30k real land points → dissolve → login → deep-space app background)
```

No LLM/API key required (optional Anthropic mode with validated fallback). One
Docker container serves API + UI. Login-gated. CI-gated. One-click rollback.

---

## 2. Final architecture

```
React/Vite (dashboard, lazy three.js chunk)
      │ REST (Pydantic schemas) + SSE (/api/events/stream, cookie-auth)
      ▼
FastAPI ── SimulationEngine (tick-driven, seeded RNG)
       ├─ HybridDetector (zscore/ewma/rate/iforest → fused score)
       ├─ IncidentManager (lifecycle state machine)
       ├─ AgentRuntime (per-incident state machines, 12-tool registry)
       ├─ AuthService (PBKDF2, DB sessions, httpOnly cookies)
       └─ SQLite via repository layer (batch writes, indexed)
```

Everything in-process: no Kafka/Redis/Celery. `DATABASE_URL` can move to
PostgreSQL later without code changes.

## 3. Repository layout (as committed)

```
agentops-2/
├── backend/app/{api,core,db,simulation,detection,incidents,agent,tools,services}
├── backend/tests/            # 58 tests, all green
├── frontend/src/{components,pages,hooks,lib,types,three}
├── frontend/src/three/       # SpaceScene, ParticleGlobe, Environment, shaders, sceneStore, EntryOverlay, landPoints
├── tools/generate_landmask.py
├── docs/                     # DEPLOYMENT, RELEASE_PROCESS, SPACE_SCENE, PROJECT_JOURNEY, screenshots
├── Dockerfile  docker-compose.yml  render.yaml  .env.example  .dockerignore
├── .github/workflows/ci.yml  CONTRIBUTING.md  LICENSE  README.md
└── start-backend.ps1 / start-backend.sh
```

## 4. Build phases (what happened, in order)

1. **Backend core** — settings/env config, event bus, structured logging, SQLAlchemy models + repository, Pydantic schemas.
2. **Simulation engine** — metric specs, per-device seeded baselines + diurnal drift, 12 named failure scenarios, ambient anomaly injector, demo script.
3. **Detection engine** — robust z-score (median/MAD), fast/slow EWMA divergence, noise-gated ROC, per-device Isolation Forests; weighted fusion + severity bands; persistence/cooldown/grouping suppression.
4. **Incident manager** — OPEN→INVESTIGATING→MITIGATING→MONITORING→RESOLVED/ESCALATED/FALSE_POSITIVE; cross-metric correlated grouping; offline watchdog.
5. **Tools + agent** — 12-tool registry with risk classes + idempotency; tick-driven agent state machine; deterministic rule chains; recovery verification; escalation; optional LLM planner with Pydantic validation + silent rule fallback.
6. **API + SSE** — all routes, simulation control, failure injection, analytics, one SSE stream.
7. **Tests** — 58 tests incl. deterministic end-to-end autonomous-loop test.
8. **Frontend** — dark observability dashboard: fleet grid, live charts, incident center + agent-timeline drawer, analytics, simulation control, settings.
9. **Verification** — all 12 scenarios validated end-to-end via deterministic harness (with and without Isolation Forest).
10. **Auth** — PBKDF2 users, DB sessions, httpOnly cookie middleware, landing/login, change-password.
11. **Cinematic globe** — Natural Earth → 30k particles, GPU dissolution shader, drag physics, starfield/dust/nebula, scene state machine, lazy chunk.
12. **Ship** — Dockerfile, compose, render.yaml, CI, docs; GitHub repo; Render production deploy.

## 5. Real bugs found & fixed (the valuable part)

| # | Bug | Root cause | Fix |
|---|---|---|---|
| 1 | Rolling z-score stopped firing mid-fault | Window absorbed the anomaly into its own baseline | Median/MAD robust stats |
| 2 | EWMA never caught slow ramps | It chased the drift | Fast/slow divergence + gated adaptation |
| 3 | EWMA self-masked anomalies | Residual variance inflated by the fault | Freeze variance in abnormal regime; noise floor |
| 4 | IF scoring 28ms/call | sklearn joblib dispatch per call | Manual average-path-length scoring, validated vs sklearn (~60× faster) |
| 5 | IF scores compressed | Raw decision fn hovers near 0 for inliers | Calibrate sigmoid on training-score mean/std |
| 6 | Warmup false positives | Unstable early MAD | Min samples + override maturity gate |
| 7 | Recovery looked anomalous | Rolling window contaminated by the incident | Verify against gated EWMA baseline |
| 8 | Offline device stayed offline after restart | restart kept max(old, 2) offline ticks | restart() sets exactly 2 |
| 9 | Correlated failures → 3 parallel incidents | Grouping was per-metric only | Device-level correlated grouping (120 s) |
| 10 | SSE test hung forever | starlette TestClient can't consume infinite streams | Test SSE via real uvicorn thread |
| 11 | `/incidents` 404 on refresh | StaticFiles mount isn't an SPA | Catch-all fallback → index.html |
| 12 | Black screen after navigation | framer-motion `mode="wait"` stranded opacity 0 under StrictMode | Keyed remount, no exit phase |
| 13 | Feed flooded with per-tick anomaly events | Detector emits during persistence window | Coalesce repeats in the store |
| 14 | Globe looked like a white blob | Point size 10× too large | Perspective size constants tuned (140→26) |
| 15 | **Render deploy failed at startup** | `sqlite:///./data/...` resolved against container CWD; dir missing | `_ensure_sqlite_parent_dir()` + `mkdir backend/data` in Dockerfile (CI proved fix) |
| 16 | Login "invalid credentials" on prod | Expected: Render auto-generated ADMIN_PASSWORD | Read it from Environment tab (by design) |

## 6. Verification record

- `pytest`: **58/58 passed** (simulator, detectors, agent rules/chains, idempotency, LLM fallback, API, auth, live SSE, deterministic e2e).
- CI on GitHub: Backend tests ✓ Frontend build ✓ Docker build + container health smoke ✓ (currently green on `main`).
- Browser-verified (Playwright): globe form/drag/dissolve, login, dashboard-over-space, incident drawer timeline, analytics, simulation page. 59 FPS / 27 MB heap.
- Production-verified: `/api/health` healthy, simulation running, API 401 without session, demo creds hidden.

## 7. Commands you actually use

```bash
# Run locally (Windows)
./start-backend.ps1                     # http://localhost:8000
cd frontend && npm run dev              # optional hot-reload UI on :5173

# Tests
cd backend && .venv/Scripts/python -m pytest tests -q

# Frontend build
cd frontend && npm run build

# Docker
docker compose up --build

# Daily dev loop
git checkout -b feature/<name>   # code…  tests+build green…
git push -u origin feature/<name>  # → PR → CI → squash merge → Render auto-deploys
```

## 8. Production operations

| Task | Where |
|---|---|
| URL | https://agentops-o50e.onrender.com |
| Admin password | Render → agentops service → Environment → `ADMIN_PASSWORD` (auto-generated) |
| Change password | In-app Settings → Change Password |
| Redeploy | Automatic on `git push` to `main` (or Manual Deploy) |
| Rollback | Render → Events → previous deploy; or flip `FEATURE_FLAGS`; or `git revert` |
| CI / branch protection | GitHub Actions; `main` requires Backend tests + Frontend build + Docker build |
| Free-tier nap | Sleeps after 15 min idle; ~50 s cold start on next visit — normal |
| Data | SQLite resets on redeploy/restart (demo re-seeds itself). PostgreSQL later via `DATABASE_URL` |

## 9. Disaster recovery — restore on a brand-new machine

```bash
# 1. Install: Python 3.12+, Node 20+, git
git clone https://github.com/tjmhmdaarif/agentops.git
cd agentops

# 2. Backend
python -m venv backend/.venv
backend/.venv/Scripts/pip install -r backend/requirements.txt      # Windows
# backend/.venv/bin/pip install -r backend/requirements.txt        # macOS/Linux

# 3. Frontend
cd frontend && npm install && npm run build && cd ..

# 4. Run
./start-backend.ps1        # or: backend/.venv/bin/python -m uvicorn --app-dir backend app.main:app
# open http://localhost:8000 — fleet boots, admin seeded from env or default admin/agentops (dev)

# 5. Re-deploy: repo already contains render.yaml — Render Blueprint picks it up automatically.
```

Local credentials (dev only): `admin / agentops`. Production password lives only
in Render's Environment (never in git).

## 10. Feature flags — the experiment safety valve

```bash
FEATURE_FLAGS="predictive_health=true,chaos_controls=false"
```

Default OFF in `main`. Flag OFF = feature 404s and its UI hides. Flip flags in
Render → Environment for a <1-minute rollback without redeploying.

## 11. Where to continue tomorrow

- Ideas: alert webhooks on escalation, human-approval queue for HIGH_RISK tools,
  seasonal baselines, cross-device root-cause, PostgreSQL, named Cloudflare
  tunnel or Render custom domain.
- Process: feature branch → flag → CI → squash merge → tag release → auto-deploy.
