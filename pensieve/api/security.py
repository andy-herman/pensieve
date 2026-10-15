"""Local API hardening: a per-launch session token and browser security headers.

The desktop launcher starts the backend with a fresh random token in
``PENSIEVE_SESSION_TOKEN`` and opens the window at ``/?t=<token>``. This module
swaps that one-time query value for an HttpOnly, SameSite=Strict cookie and
then refuses every ``/api/*`` call that does not carry it. Without it, any web
page open in any browser (or any other Windows user on the same PC) could read
and change this user's board through ``127.0.0.1``.

``pensieve serve`` run by hand, without the variable, keeps the old open
behavior for development.

Every response also carries a Content-Security-Policy that only runs scripts
shipped with the app, so text from a task (or an AI summary of one) can never
execute as code in the dashboard even if it slipped past escaping.
"""

from __future__ import annotations

import hmac
import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse

COOKIE = "pensieve_session"
HEADER = "x-pensieve-token"
OPEN_PATHS = frozenset({"/api/healthz"})

# Inline styles stay allowed (the dashboard sets lane colors in markup); scripts,
# connections, fonts and media are limited to this app's own origin.
CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "media-src 'self' blob:",
    "font-src 'self'",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'none'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])
SECURITY_HEADERS = {
    "Content-Security-Policy": CSP,
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
}


def session_token() -> str | None:
    return os.environ.get("PENSIEVE_SESSION_TOKEN", "").strip() or None


def _matches(value: str | None, token: str) -> bool:
    return bool(value) and hmac.compare_digest(value.encode(), token.encode())


def install(app: FastAPI) -> None:
    token = session_token()

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        return response

    @app.get("/api/session/check")
    def session_check() -> dict[str, bool]:
        # Reaching this handler means the middleware accepted the caller.
        return {"ok": True}

    if token is None:
        return

    @app.middleware("http")
    async def require_session(request: Request, call_next):
        path = request.url.path
        offered = request.query_params.get("t")
        if offered is not None and not path.startswith("/api/"):
            # The launcher's one-time hand-off: set the cookie, drop the token
            # from the address bar so it never lands in history.
            if not _matches(offered, token):
                return JSONResponse({"detail": "This Pensieve link has expired. Open Pensieve from the Start menu."},
                                    status_code=401)
            resp = RedirectResponse(path or "/", status_code=303)
            resp.set_cookie(COOKIE, token, httponly=True, samesite="strict", path="/")
            return resp
        if path.startswith("/api/") and path not in OPEN_PATHS:
            if not (_matches(request.cookies.get(COOKIE), token) or _matches(request.headers.get(HEADER), token)):
                return JSONResponse({"detail": "Open Pensieve from its desktop app to use it."}, status_code=401)
        return await call_next(request)
