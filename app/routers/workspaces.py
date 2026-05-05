from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from ..db import call_proc, fetch_all, fetch_one
from ..security import CurrentUser, require_user


router = APIRouter()


@router.get("/")
async def home(request: Request, user: CurrentUser = Depends(require_user)):
    pool = request.app.state.db_pool
    async with pool.connection() as conn:
        workspaces = await fetch_all(
            conn,
            """
            SELECT w.workspace_id, w.name, w.description, wm.is_admin
            FROM workspaces w
            JOIN workspace_members wm ON wm.workspace_id = w.workspace_id
            WHERE wm.user_id = %s
            ORDER BY w.created_at DESC, w.workspace_id DESC
            """,
            [user.user_id],
        )

        invitations = await fetch_all(
            conn,
            """
            SELECT
              i.invitation_id,
              i.status,
              i.created_at,
              i.workspace_id,
              i.channel_id,
              w.name AS workspace_name,
              c.name AS channel_name,
              u.username AS inviter_username
            FROM invitations i
            JOIN users u ON u.user_id = i.inviter_id
            LEFT JOIN workspaces w ON w.workspace_id = i.workspace_id
            LEFT JOIN channels c ON c.channel_id = i.channel_id
            WHERE LOWER(i.invitee_email) = LOWER(%s)
              AND i.status = 'pending'
            ORDER BY i.created_at DESC, i.invitation_id DESC
            """,
            [user.email],
        )

    return request.app.state.templates.TemplateResponse(
        request,
        "home.html",
        {"user": user, "workspaces": workspaces, "invitations": invitations},
    )


@router.get("/workspaces/new")
async def new_workspace_page(request: Request, user: CurrentUser = Depends(require_user)):
    return request.app.state.templates.TemplateResponse(request, "workspace_new.html", {"user": user})


@router.post("/workspaces")
async def create_workspace(
    request: Request,
    user: CurrentUser = Depends(require_user),
    name: str = Form(...),
    description: str = Form(""),
):
    pool = request.app.state.db_pool
    async with pool.connection() as conn:
        wid = await call_proc(conn, "create_workspace", name, description or None, user.user_id)
    return RedirectResponse(url=f"/w/{wid}", status_code=303)


@router.get("/w/{workspace_id}")
async def workspace_dashboard(request: Request, workspace_id: int, user: CurrentUser = Depends(require_user)):
    pool = request.app.state.db_pool
    async with pool.connection() as conn:
        workspace = await fetch_one(
            conn,
            """
            SELECT w.workspace_id, w.name, w.description, wm.is_admin
            FROM workspaces w
            JOIN workspace_members wm ON wm.workspace_id = w.workspace_id
            WHERE w.workspace_id = %s AND wm.user_id = %s
            """,
            [workspace_id, user.user_id],
        )
        if not workspace:
            return RedirectResponse(url="/", status_code=303)

        channels = await fetch_all(
            conn,
            """
            SELECT c.channel_id, c.name, c.type
            FROM channels c
            JOIN channel_members cm ON cm.channel_id = c.channel_id
            WHERE c.workspace_id = %s AND cm.user_id = %s
            ORDER BY c.type ASC, c.name ASC
            """,
            [workspace_id, user.user_id],
        )

        unread = await fetch_all(conn, "SELECT * FROM list_unread_counts(%s)", [user.user_id])
        unread_map = {int(r["channel_id"]): int(r["unread"]) for r in unread}

        members = await fetch_all(
            conn,
            """
            SELECT u.user_id, u.username, u.nickname, wm.is_admin
            FROM workspace_members wm
            JOIN users u ON u.user_id = wm.user_id
            WHERE wm.workspace_id = %s
            ORDER BY wm.is_admin DESC, u.username ASC
            """,
            [workspace_id],
        )

    error = request.query_params.get("error")
    success = request.query_params.get("success")
    return request.app.state.templates.TemplateResponse(
        request,
        "workspace.html",
        {
            "user": user,
            "workspace": workspace,
            "channels": channels,
            "unread_map": unread_map,
            "members": members,
            "error": error,
            "success": success,
        },
    )


@router.post("/w/{workspace_id}/channels")
async def create_channel(
    request: Request,
    workspace_id: int,
    user: CurrentUser = Depends(require_user),
    name: str = Form(...),
    type: str = Form(...),
):
    pool = request.app.state.db_pool
    async with pool.connection() as conn:
        cid = await call_proc(conn, "create_channel", workspace_id, name, type, user.user_id)
    return RedirectResponse(url=f"/w/{workspace_id}/c/{cid}", status_code=303)


@router.post("/w/{workspace_id}/admins")
async def promote_admin(
    request: Request,
    workspace_id: int,
    user: CurrentUser = Depends(require_user),
    target_user_id: int = Form(...),
):
    pool = request.app.state.db_pool
    async with pool.connection() as conn:
        await call_proc(conn, "add_workspace_admin", workspace_id, user.user_id, target_user_id)
    return RedirectResponse(url=f"/w/{workspace_id}", status_code=303)


@router.post("/w/{workspace_id}/description")
async def update_description(
    request: Request,
    workspace_id: int,
    user: CurrentUser = Depends(require_user),
    description: str = Form(""),
):
    pool = request.app.state.db_pool
    try:
        async with pool.connection() as conn:
            await call_proc(conn, "update_workspace_description", workspace_id, user.user_id, description or None)
    except Exception as e:
        # Stored procedures raise explicit errors like 'not_authorized'.
        msg = str(e)
        if "not_authorized" in msg:
            return RedirectResponse(url=f"/w/{workspace_id}?error=Admin+permissions+required", status_code=303)
        return RedirectResponse(url=f"/w/{workspace_id}?error=Could+not+update+description", status_code=303)
    return RedirectResponse(url=f"/w/{workspace_id}?success=Description+updated", status_code=303)


@router.post("/w/{workspace_id}/members/remove")
async def remove_member(
    request: Request,
    workspace_id: int,
    user: CurrentUser = Depends(require_user),
    target_user_id: int = Form(...),
):
    pool = request.app.state.db_pool
    try:
        async with pool.connection() as conn:
            await call_proc(conn, "remove_workspace_member", workspace_id, user.user_id, target_user_id)
    except Exception as e:
        msg = str(e)
        if "not_authorized" in msg:
            return RedirectResponse(url=f"/w/{workspace_id}?error=Admin+permissions+required", status_code=303)
        if "cannot_remove_last_admin" in msg:
            return RedirectResponse(url=f"/w/{workspace_id}?error=Cannot+remove+the+last+admin", status_code=303)
        return RedirectResponse(url=f"/w/{workspace_id}?error=Could+not+remove+member", status_code=303)
    return RedirectResponse(url=f"/w/{workspace_id}?success=Member+removed", status_code=303)

