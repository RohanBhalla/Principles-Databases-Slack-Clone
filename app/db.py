from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

# Connection configuration. Using correct text encoding.
async def _configure(conn) -> None:
    await conn.set_autocommit(True)
    await conn.execute("SET client_encoding TO 'UTF8'")
    await conn.set_autocommit(False)

# Create a connection pool to allow multiple connections to the database
def make_pool(dsn: str) -> AsyncConnectionPool:
    # `open=False` avoids deprecated eager-open behavior; we explicitly `await pool.open()` in app lifespan.
    return AsyncConnectionPool(
        conninfo=dsn,
        min_size=1,
        max_size=10,
        open=False,
        configure=_configure,
        kwargs={"row_factory": dict_row},
    )


def _placeholders(n: int) -> str:
    return ", ".join(["%s"] * n)

# Create a stored procedure call (basically like a function call to a stored procedure)
async def call_proc(conn, name: str, *args: Any) -> Any:
    placeholders = _placeholders(len(args))
    sql = f"SELECT {name}({placeholders}) AS value"
    async with conn.cursor() as cur:
        await cur.execute(sql, args)
        row = await cur.fetchone()
        return None if row is None else row["value"]

# Fetch a single row from the database
async def fetch_one(conn, sql: str, params: Sequence[Any] | None = None) -> dict[str, Any] | None:
    async with conn.cursor() as cur:
        await cur.execute(sql, params or [])
        return await cur.fetchone()

# Fetch all rows from the database
async def fetch_all(conn, sql: str, params: Sequence[Any] | None = None) -> list[dict[str, Any]]:
    async with conn.cursor() as cur:
        await cur.execute(sql, params or [])
        return list(await cur.fetchall())

