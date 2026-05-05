from __future__ import annotations

import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from . import config
from .db import make_pool
from .routers import auth, channels, invitations, messages, search, workspaces
from .security import LoginRateLimiter, ensure_csrf_token


templates = Jinja2Templates(directory="app/templates")
# Python 3.14 + Jinja2 3.1.x: default template cache keys include weakrefs to the loader,
# which can be unhashable for FileSystemLoader and crash template loading.
templates.env.cache = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.templates = templates
    app.state.db_pool = make_pool(config.DATABASE_URL)
    app.state.login_rate_limiter = LoginRateLimiter()
    await app.state.db_pool.open()
    try:
        yield
    finally:
        await app.state.db_pool.close()


app = FastAPI(lifespan=lifespan)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; "
        "base-uri 'self'; "
        "frame-ancestors 'none'"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    return response


@app.middleware("http")
async def ensure_csrf_middleware(request: Request, call_next):
    ensure_csrf_token(request.session)
    return await call_next(request)


@app.middleware("http")
async def csrf_protect(request: Request, call_next):
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        # IMPORTANT: do not call `request.form()` here — it consumes the body and breaks
        # FastAPI `Form(...)` dependencies on the route (422 "Field required").
        # Token must come from the URL query string (?csrf_token=...) or X-CSRF-Token header.
        expected = request.session.get("csrf_token")
        submitted = request.headers.get("x-csrf-token") or request.query_params.get("csrf_token")
        ok = bool(expected) and bool(submitted) and secrets.compare_digest(str(expected), str(submitted))
        if not ok:
            # Returning a plain Response here (instead of raising HTTPException) keeps
            # the failure clean: BaseHTTPMiddleware does not catch HTTPException, so
            # raising would surface as an unhandled ASGI error.
            return PlainTextResponse(
                "CSRF token mismatch. Please refresh the page and try again.",
                status_code=403,
            )
    return await call_next(request)


# Must be registered AFTER other middleware so it wraps the app and `request.session` works.
app.add_middleware(
    SessionMiddleware,
    secret_key=config.SESSION_SECRET,
    session_cookie=config.SESSION_COOKIE,
    same_site="lax",
    https_only=False,  # local demo
    max_age=60 * 60 * 24 * 7,
)


@app.get("/healthz")
async def healthz():
    return {"ok": True}


@app.get("/me", response_class=HTMLResponse)
async def me(request: Request):
    uid = request.session.get("user_id")
    if not uid:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request, "me.html", {"user_id": uid})


@app.exception_handler(401)
async def auth_401(request: Request, exc):
    return RedirectResponse(url="/login", status_code=303)


app.include_router(auth.router)
app.include_router(workspaces.router)
app.include_router(channels.router)
app.include_router(messages.router)
app.include_router(invitations.router)
app.include_router(search.router)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

