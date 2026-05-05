# snickr (Project 2) — FastAPI + Jinja + PostgreSQL

This is the Project 2 web UI for the Project 1 database (Slack-like system).

## Prereqs

- PostgreSQL 15+ (you already have a local cluster under `Project1/.pgdata` on port **5433**)
- Python 3.11+

## Setup

From the course workspace root:

1) Start the existing PostgreSQL cluster:

```bash
pg_ctl -D "Project1/.pgdata" -l "Project1/.pglog" start
```

2) Create and load the `snickr` database:

```bash
createdb -p 5433 snickr
psql -p 5433 -d snickr -f "Principles-Databases-Slack-Clone/sql/schema_v2.sql"
psql -p 5433 -d snickr -f "Principles-Databases-Slack-Clone/sql/procedures.sql"
psql -p 5433 -d snickr -f "Principles-Databases-Slack-Clone/sql/seed_v2.sql"
```

3) Create a venv and install dependencies:

```bash
cd "Principles-Databases-Slack-Clone"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

4) Configure env vars:

```bash
cp .env.example .env
```

Set:

- `DATABASE_URL=postgresql://localhost:5433/snickr`
- `SESSION_SECRET=...` (any long random string is fine)

## Run

```bash
uvicorn app.main:app --reload --port 8000
```

Open `http://127.0.0.1:8000`.

Demo login (seed data):

- `rohan@example.com` / `password123`

## Supported features (required)

- Register/login/logout
- Create workspaces and channels
- Post messages
- Invite to workspace or channel and respond (accept/reject)
- Browse workspace/channel content
- Search visible messages (`/search?q=...`)

## Extra features (implemented)

- **Unread badges** per channel (`channel_reads` + `list_unread_counts`)
- **Emoji reactions** on messages (`reactions` + `toggle_reaction`)

## Security notes (write-up points)

- **SQL injection**: all backend queries are parameterized; all writes go through stored procedures invoked as `SELECT fn(%s, ...)` with bound params.\n+- **XSS**: Jinja autoescape is used; templates never use `|safe` for user content.\n+- **CSRF**: per-session token stored in the signed session cookie; every POST form includes a hidden `csrf_token`, validated by middleware.\n+- **Concurrency**: write operations are done inside DB functions; membership acceptance uses `SELECT ... FOR UPDATE` and idempotent `ON CONFLICT DO NOTHING` inserts to prevent duplicates.\n+
