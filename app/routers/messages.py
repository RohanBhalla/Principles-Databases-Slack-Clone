from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from ..db import call_proc
from ..security import CurrentUser, require_user


router = APIRouter()

# Post a message to a channel
@router.post("/w/{workspace_id}/c/{channel_id}/messages")
async def post_message(
    request: Request,
    workspace_id: int,
    channel_id: int,
    user: CurrentUser = Depends(require_user),
    content: str = Form(...),
):
    pool = request.app.state.db_pool
    async with pool.connection() as conn:
        await call_proc(conn, "post_message", channel_id, user.user_id, content)
    return RedirectResponse(url=f"/w/{workspace_id}/c/{channel_id}", status_code=303)

# Toggle reaction route
@router.post("/messages/{message_id}/react")
async def toggle_reaction(
    request: Request,
    message_id: int,
    user: CurrentUser = Depends(require_user),
    emoji: str = Form(...),
    workspace_id: int = Form(...),
    channel_id: int = Form(...),
):
    pool = request.app.state.db_pool
    async with pool.connection() as conn:
        await call_proc(conn, "toggle_reaction", message_id, user.user_id, emoji)
    return RedirectResponse(url=f"/w/{workspace_id}/c/{channel_id}", status_code=303)

