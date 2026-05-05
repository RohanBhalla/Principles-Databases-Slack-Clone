from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from ..db import call_proc
from ..security import CurrentUser, require_user


router = APIRouter()


@router.post("/w/{workspace_id}/invitations")
async def invite_workspace(
    request: Request,
    workspace_id: int,
    user: CurrentUser = Depends(require_user),
    invitee_email: str = Form(...),
):
    pool = request.app.state.db_pool
    try:
        async with pool.connection() as conn:
            await call_proc(conn, "invite_to_workspace", user.user_id, invitee_email, workspace_id)
    except Exception as e:
        msg = str(e)
        if "not_authorized" in msg:
            return RedirectResponse(url=f"/w/{workspace_id}?error=Only+workspace+admins+can+invite", status_code=303)
        if "already_member" in msg:
            return RedirectResponse(url=f"/w/{workspace_id}?error=User+is+already+a+member", status_code=303)
        if "duplicate" in msg or "unique" in msg or "uniq_pending_invite" in msg:
            return RedirectResponse(url=f"/w/{workspace_id}?error=Invite+already+pending", status_code=303)
        return RedirectResponse(url=f"/w/{workspace_id}?error=Could+not+send+invite", status_code=303)
    return RedirectResponse(url=f"/w/{workspace_id}?success=Invite+sent", status_code=303)


@router.post("/w/{workspace_id}/c/{channel_id}/invitations")
async def invite_channel(
    request: Request,
    workspace_id: int,
    channel_id: int,
    user: CurrentUser = Depends(require_user),
    invitee_email: str = Form(...),
):
    pool = request.app.state.db_pool
    try:
        async with pool.connection() as conn:
            await call_proc(conn, "invite_to_channel", user.user_id, invitee_email, channel_id)
    except Exception as e:
        msg = str(e)
        if "not_authorized" in msg:
            return RedirectResponse(
                url=f"/w/{workspace_id}/c/{channel_id}?error=Only+channel+members+can+invite",
                status_code=303,
            )
        if "duplicate" in msg or "unique" in msg or "uniq_pending_invite" in msg:
            return RedirectResponse(url=f"/w/{workspace_id}/c/{channel_id}?error=Invite+already+pending", status_code=303)
        return RedirectResponse(url=f"/w/{workspace_id}/c/{channel_id}?error=Could+not+send+invite", status_code=303)
    return RedirectResponse(url=f"/w/{workspace_id}/c/{channel_id}?success=Invite+sent", status_code=303)


@router.post("/invitations/{invitation_id}/respond")
async def respond(
    request: Request,
    invitation_id: int,
    user: CurrentUser = Depends(require_user),
    action: str = Form(...),
):
    pool = request.app.state.db_pool
    async with pool.connection() as conn:
        await call_proc(conn, "respond_to_invitation", invitation_id, user.user_id, action)
    return RedirectResponse(url="/", status_code=303)

