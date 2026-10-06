"""Auth endpoints + the API auth middleware.

Public:  /api/auth/login, /api/health (platform health checks must stay open)
Private: every other /api/* route requires the session cookie.
"""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.auth import SESSION_COOKIE

router = APIRouter(prefix="/api/auth", tags=["auth"])

PUBLIC_PREFIXES = ("/api/health", "/api/auth/login")
PUBLIC_EXACT = {"/api/health"}


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/login")
def login(body: LoginRequest, request: Request) -> JSONResponse:
    auth = request.app.state.runtime.auth
    if not auth.verify(body.username, body.password):
        return JSONResponse(
            status_code=401,
            content={"error": {"type": "invalid_credentials", "message": "Invalid username or password"}},
        )
    token = auth.create_session(body.username)
    settings = request.app.state.settings
    response = JSONResponse({"ok": True, "username": body.username})
    response.set_cookie(
        SESSION_COOKIE, token,
        max_age=7 * 24 * 3600,
        httponly=True,
        samesite="lax",
        secure=settings.app_env == "production",
    )
    return response


@router.post("/logout")
def logout(request: Request) -> JSONResponse:
    auth = request.app.state.runtime.auth
    auth.revoke(request.cookies.get(SESSION_COOKIE))
    response = JSONResponse({"ok": True})
    response.delete_cookie(SESSION_COOKIE)
    return response


@router.get("/me")
def me(request: Request) -> dict:
    return {"username": request.state.username, "authenticated": True}


@router.post("/change-password")
def change_password(body: ChangePasswordRequest, request: Request) -> JSONResponse:
    auth = request.app.state.runtime.auth
    username = request.state.username
    if not auth.verify(username, body.current_password):
        return JSONResponse(
            status_code=403,
            content={"error": {"type": "invalid_credentials", "message": "Current password is incorrect"}},
        )
    if len(body.new_password) < 8:
        return JSONResponse(
            status_code=422,
            content={"error": {"type": "weak_password", "message": "Password must be at least 8 characters"}},
        )
    auth.change_password(username, body.new_password)
    return JSONResponse({"ok": True, "message": "Password changed — please sign in again."})
