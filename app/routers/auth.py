from __future__ import annotations

#Authentication routes are defined here
#This router renders the login/register pages, validates credentials against the DB,
#and stores the authenticated user in the session via `request.session["user_id"]`
from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from ..db import call_proc, fetch_one
from ..security import hash_password, verify_password


router = APIRouter()

# Login page route
# Render the login page or redirect home if already logged in
@router.get("/login")
async def login_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse(url="/", status_code=303)
    return request.app.state.templates.TemplateResponse(request, "login.html")


# Login route
# Authenticate a user and start a session by setting `session["user_id"]`
# Validate credentials against the DB
# Store the authenticated user in the session via `request.session["user_id"]`
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


# Register page route
# Render the registration page or redirect home if already logged in
@router.get("/register")
async def register_page(request: Request):
    """Render the registration page (or redirect home if already logged in)."""
    if request.session.get("user_id"):
        return RedirectResponse(url="/", status_code=303)
    return request.app.state.templates.TemplateResponse(request, "register.html")

# Register route
# Create a new user account
# Start a session for the new user
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


# Logout route
# End the current session and redirect back to the login page
@router.post("/logout")
async def logout(request: Request):
    """End the current session and redirect back to the login page."""
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)

