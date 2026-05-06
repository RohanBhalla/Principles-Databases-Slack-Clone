from __future__ import annotations

#Channel-related routes are defined here
#This router renders the channel view (messages + reactions + sidebar data) and
#exposes actions like deleting a channel. Access is protected by `require_user`,
#and membership/authorization is validated via queries and stored procedures.

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from ..db import call_proc, fetch_all, fetch_one
from ..security import CurrentUser, require_user


router = APIRouter()


# Delete a channel route
# Delete a non-direct channel if the current user is the creator for it
@router.post("/w/{workspace_id}/c/{channel_id}/delete")
async def delete_channel(
    request: Request,
    workspace_id: int,
    channel_id: int,
    user: CurrentUser = Depends(require_user),
):
    pool = request.app.state.db_pool
    async with pool.connection() as conn:
        row = await fetch_one(
            conn,
            """
            SELECT channel_id, workspace_id, type, created_by
            FROM channels
            WHERE channel_id = %s AND workspace_id = %s
            """,
            [channel_id, workspace_id],
        )
        if not row:
            return RedirectResponse(url=f"/w/{workspace_id}?error=channel_not_found", status_code=303)

        if row["type"] == "direct":
            return RedirectResponse(url=f"/w/{workspace_id}/c/{channel_id}?error=cannot_delete_direct", status_code=303)

        if int(row["created_by"]) != int(user.user_id):
            return RedirectResponse(url=f"/w/{workspace_id}/c/{channel_id}?error=not_authorized", status_code=303)

        await call_proc(conn, "delete_channel", channel_id, user.user_id)

    return RedirectResponse(url=f"/w/{workspace_id}?success=channel_deleted", status_code=303)


# Channel view route
# Render a channel page: sidebar channels, unread counts, messages, reactions
@router.get("/w/{workspace_id}/c/{channel_id}")
async def channel_view(
    request: Request,
    workspace_id: int,
    channel_id: int,
    user: CurrentUser = Depends(require_user),
):
    pool = request.app.state.db_pool
    async with pool.connection() as conn:
        # Mark the channel as read for the current user
        await call_proc(conn, "mark_channel_read", channel_id, user.user_id)

        channel = await fetch_one(
            conn,
            """
            SELECT c.channel_id, c.workspace_id, c.name, c.type, c.created_by
            FROM channels c
            JOIN channel_members cm ON cm.channel_id = c.channel_id
            WHERE c.channel_id = %s AND c.workspace_id = %s AND cm.user_id = %s
            """,
            [channel_id, workspace_id, user.user_id],
        )
        if not channel:
            return RedirectResponse(url=f"/w/{workspace_id}", status_code=303)

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

        messages = await fetch_all(
            conn,
            """
            SELECT m.message_id, m.content, m.created_at, u.username, u.nickname
            FROM messages m
            JOIN users u ON u.user_id = m.user_id
            WHERE m.channel_id = %s
            ORDER BY m.created_at ASC, m.message_id ASC
            """,
            [channel_id],
        )

        reactions = await fetch_all(
            conn,
            """
            SELECT message_id, emoji, COUNT(*)::int AS count
            FROM reactions
            WHERE message_id IN (SELECT message_id FROM messages WHERE channel_id = %s)
            GROUP BY message_id, emoji
            """,
            [channel_id],
        )
        my_reactions = await fetch_all(
            conn,
            """
            SELECT message_id, emoji
            FROM reactions
            WHERE user_id = %s
              AND message_id IN (SELECT message_id FROM messages WHERE channel_id = %s)
            """,
            [user.user_id, channel_id],
        )

    react_map: dict[int, list[dict]] = {}
    for r in reactions:
        react_map.setdefault(int(r["message_id"]), []).append({"emoji": r["emoji"], "count": int(r["count"])})
    my_set = {(int(r["message_id"]), r["emoji"]) for r in my_reactions}

    error = request.query_params.get("error")
    success = request.query_params.get("success")
    return request.app.state.templates.TemplateResponse(
        request,
        "channel.html",
        {
            "user": user,
            "workspace": workspace,
            "channel": channel,
            "channels": channels,
            "unread_map": unread_map,
            "error": error,
            "success": success,
            "messages": messages,
            "react_map": react_map,
            "my_set": my_set,
            "emoji_choices": ["👍", "❤", "🎉", "😂", "✅"],
        },
    )

