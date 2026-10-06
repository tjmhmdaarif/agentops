# AgentOps 2.0 — start the backend (Windows)
# The FastAPI "app" package lives in backend/, so uvicorn must run with that as app dir.
$BackendDir = Join-Path $PSScriptRoot "backend"
$Python = Join-Path $BackendDir ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Host "Creating virtual environment and installing dependencies..."
    python -m venv (Join-Path $BackendDir ".venv")
    & $Python -m pip install -q -r (Join-Path $BackendDir "requirements.txt")
}
& $Python -m uvicorn --app-dir $BackendDir app.main:app --host 0.0.0.0 --port 8000 --reload
