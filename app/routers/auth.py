from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from ..db import call_proc, fetch_one
from ..security import hash_password, verify_password


router = APIRouter()


@router.get("/login")
async def login_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse(url="/", status_code=303)
    return request.app.state.templates.TemplateResponse(request, "login.html")


@router.post("/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
):
    ip = request.client.host if request.client else "unknown"
    key = f"{ip}:{email.lower()}"
    if not request.app.state.login_rate_limiter.allow(key):
        return request.app.state.templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Too many attempts. Try again in a few minutes."},
            status_code=429,
        )

    pool = request.app.state.db_pool
    async with pool.connection() as conn:
        user = await fetch_one(
            conn,
            "SELECT user_id, email, username, nickname, password_hash FROM users WHERE LOWER(email) = LOWER(%s)",
            [email],
        )

    if not user or not verify_password(password, user["password_hash"]):
        return request.app.state.templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Invalid email or password."},
            status_code=400,
        )

    request.session["user_id"] = int(user["user_id"])
    return RedirectResponse(url="/", status_code=303)


@router.get("/register")
async def register_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse(url="/", status_code=303)
    return request.app.state.templates.TemplateResponse(request, "register.html")


@router.post("/register")
async def register(
    request: Request,
    email: str = Form(...),
    username: str = Form(...),
    nickname: str = Form(""),
    password: str = Form(...),
):
    password_hash = hash_password(password)

    pool = request.app.state.db_pool
    try:
        async with pool.connection() as conn:
            uid = await call_proc(conn, "register_user", email, username, nickname or None, password_hash)
    except Exception:
        return request.app.state.templates.TemplateResponse(
            request,
            "register.html",
            {"error": "Email or username already exists."},
            status_code=400,
        )

    request.session["user_id"] = int(uid)
    return RedirectResponse(url="/", status_code=303)


@router.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)

