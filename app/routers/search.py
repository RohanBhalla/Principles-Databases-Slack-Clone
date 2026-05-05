from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from ..db import fetch_all
from ..security import CurrentUser, require_user


router = APIRouter()


@router.get("/search")
async def search(request: Request, user: CurrentUser = Depends(require_user)):
    q = (request.query_params.get("q") or "").strip()
    results = []
    if q:
        pool = request.app.state.db_pool
        async with pool.connection() as conn:
            results = await fetch_all(conn, "SELECT * FROM search_visible_messages(%s, %s)", [user.user_id, q])

    return request.app.state.templates.TemplateResponse(
        request,
        "search.html",
        {"user": user, "q": q, "results": results},
    )

