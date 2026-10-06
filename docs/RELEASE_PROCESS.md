# Release Process & Rollback Runbook

AgentOps is developed daily. This runbook keeps `main` deployable, isolates
experiments, and makes any bad release reversible in minutes.

## The three safety mechanisms

### 1. CI gate (nothing red reaches main)

- `.github/workflows/ci.yml` runs **backend pytest**, **frontend typecheck+build**,
  and a **Docker build + health smoke test** on every PR and every push to main.
- Enable branch protection on GitHub:
  `Settings → Branches → Add rule → main → Require status checks → CI backend/frontend/docker`.
- Merge strategy: **squash merge** (one clean commit per change → trivially revertable).

### 2. Feature flags (experiments never crash production)

New or risky behavior ships **dark**, behind a flag, default OFF:

```bash
# backend/app/core/config.py
feature_flags = {"predictive_health": False, "chaos_controls": False}

# enable for local experiments only
FEATURE_FLAGS="predictive_health=true"   # .env (git-ignored)

# enable in production only after validation (Render dashboard → Environment)
FEATURE_FLAGS="predictive_health=true"
```

Rules:
- Backend surface behind a flag returns 404 when the flag is off (`routes_devices.py`
  `/prediction` is the reference implementation).
- Frontend hides the UI behind `config.feature_flags.<name>`.
- A flag defaults OFF in `main`. Turning it on is a config change, not a deploy.
- Turning it **off** is the fastest rollback: no redeploy needed.

### 3. Tagged releases + instant rollback

```bash
# after each validated merge to main
git tag -a v0.x.y -m "what changed"
git push origin main --tags
```

**If something breaks in production:**

| Severity | Action | Time |
|---|---|---|
| Feature-flagged change misbehaves | Set flag to `false` in Render env vars | < 1 min |
| Bad release, no flags involved | Render dashboard → your service → **Rollback** to previous deploy (or `git revert <sha>` + push) | ~2 min |
| Database corrupted | Free tier is ephemeral by design — redeploy resets the demo DB. (With PostgreSQL attached: restore latest snapshot.) | ~5 min |
| Local crash while experimenting | `git stash` / `git checkout main` — nothing experimental ever touches main until CI is green | instant |

**Never** force-push main or rewrite published history — rollback is `git revert`,
so every state in history stays reachable.

## Daily development loop

```
main (always shippable)
  └── feature/<name>  → local test → PR → CI green → squash merge → tag
                                    ↳ if CI red: fix here, main untouched
```

1. `git checkout -b feature/<name>`
2. Backend: `cd backend && .venv/Scripts/python -m pytest tests -q` must pass.
3. Frontend: `cd frontend && npm run build` must pass.
4. Experimental? Wrap in a feature flag (default OFF).
5. PR → CI → squash merge → optional tag → Render auto-deploys main.

## Environments

| Env | Where | DB | Flags |
|---|---|---|---|
| Local dev | `localhost:8000` | SQLite (`data/agentops.db`) | anything in `.env` |
| Public demo (temporary) | Cloudflare quick tunnel | same local DB | same |
| Production | Render Docker web service | SQLite (ephemeral) or PostgreSQL | only validated flags ON |

## Pre-merge checklist (paste into every PR)

- [ ] `pytest` green
- [ ] `npm run build` green
- [ ] New behavior behind a flag (if experimental)
- [ ] No secrets / no hardcoded URLs
- [ ] README/docs updated if behavior changed
