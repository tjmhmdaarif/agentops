# Contributing to AgentOps 2.0

Thanks for working on AgentOps! This project is under active daily development,
so we follow a lightweight but strict safety workflow. Read
[docs/RELEASE_PROCESS.md](docs/RELEASE_PROCESS.md) before your first change.

## Golden rules

1. **`main` must always be deployable.** Never commit broken code directly to main.
2. **Every change goes through a PR** with green CI (backend tests + frontend build + docker smoke).
3. **Experimental features ship behind a feature flag**, default OFF.
4. **No secrets in git.** Use `.env` locally (it's git-ignored) and platform env vars in production.

## Daily workflow

```bash
git checkout -b feature/my-improvement
# ... code ...
cd backend && .venv/Scripts/python -m pytest tests -q   # must pass
cd ../frontend && npm run build                          # must pass
git push -u origin feature/my-improvement
# open a PR → CI runs → review → squash merge
```

## Where things live

- Backend pipeline stages: `backend/app/{simulation,detection,incidents,agent,tools}`
- API contracts: `backend/app/db/schemas.py` — change them carefully, the frontend depends on them.
- Frontend pages: `frontend/src/pages`, shared components in `frontend/src/components`
- Event types (SSE): `backend/app/core/runtime.py` publishes; `frontend/src/hooks/store.tsx` consumes.

## Adding an experimental feature

1. Add a flag to `Settings.feature_flags` defaults in `backend/app/core/config.py` (default `False`).
2. Gate the backend surface: `if not settings.feature_flags["my_feature"]: raise 404`.
3. Gate the UI: `config.feature_flags.my_feature && <MyComponent />`.
4. Enable locally via `FEATURE_FLAGS="my_feature=true"` in `.env`.
5. Merge with the flag OFF. Enable in production only after validation.

## Commit style

Short imperative subjects, e.g. `detection: tighten ewma gate`, `ui: add predictive card`.
No force-pushes to main. Rollback = `git revert`, never history rewriting (see the runbook).
