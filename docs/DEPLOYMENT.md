# Deployment Guide

Three ways to get AgentOps online, from most permanent to most instant.

## Option A — Render (recommended, free tier)

The repo contains `render.yaml` (Docker web service blueprint).

1. Push this repo to GitHub.
2. Render dashboard → **New → Blueprint** → select the repo → **Apply**.
3. Render builds the multi-stage Dockerfile, assigns `PORT`, and runs the health
   check against `/api/health` (public by design).
4. Your URL: `https://<service-name>.onrender.com`.

Set these in **Environment** (Render dashboard):

| Variable | Value | Notes |
|---|---|---|
| `APP_ENV` | `production` | enables secure cookies |
| `ADMIN_USERNAME` | `admin` | or your own |
| `ADMIN_PASSWORD` | *(choose a strong one)* | first-boot seeds this admin |
| `SHOW_DEMO_CREDS` | `false` | hides demo credentials on the login page |
| `LLM_ENABLED` | `false` | optional; set `true` + `ANTHROPIC_API_KEY` for LLM mode |
| `FEATURE_FLAGS` | `predictive_health=false` | manage experiments here |

**Ephemeral storage warning:** the free instance filesystem resets on redeploy/restart —
the SQLite demo DB is recreated and reseeded automatically. For persistence, attach a
Render PostgreSQL instance and set `DATABASE_URL` (SQLAlchemy URL).

## Option B — Railway

1. New Project → **Deploy from GitHub repo**.
2. Railway detects the root `Dockerfile` and injects `PORT` — no config needed.
3. Add the same environment variables as above.

## Option C — Cloudflare quick tunnel (instant public demo, zero accounts)

Exposes your local running instance on a temporary public HTTPS URL:

```bash
# 1. start the app locally
./start-backend.ps1            # or docker compose up

# 2. download cloudflared (one time)
#    https://github.com/cloudflare/cloudflared/releases/latest

# 3. open the tunnel
./cloudflared tunnel --url http://localhost:8000 --no-autoupdate
# → prints https://<random-words>.trycloudflare.com
```

- The URL lives only while both the app and cloudflared are running.
- No uptime guarantee; perfect for demos, reviews, and mobile testing.
- For a persistent named tunnel with your own hostname, create a free Cloudflare
  account and use `cloudflared tunnel create` (see `docs/` Cloudflare Zero Trust).

## Post-deploy checklist

- [ ] `https://<url>/api/health` returns `"status": "healthy"` (public)
- [ ] Root URL shows the login page (not the dashboard) when logged out
- [ ] Login works with your `ADMIN_USERNAME` / `ADMIN_PASSWORD`
- [ ] `SHOW_DEMO_CREDS=false` in production
- [ ] **Run Demo Scenario** produces incidents → agent remediation → resolution
- [ ] Change the default admin password (Settings → Change Password)
