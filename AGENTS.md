# Rastreio-DB — Agent Instructions

## Stack & Ports

* **Backend**: Python 3.14, FastAPI, SQLAlchemy, SQLite — `uvicorn main:app --reload --port 9742`
* **Frontend**: React + Vite — `npm run dev` on port **9743**, proxies `/api` → `localhost:9742`
* **Executable**: PyInstaller `--onedir --windowed`, served from `main:app` via `__main__` entrypoint

## Development Commands

```bash
# Backend
cd backend && python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 9742

# Frontend
cd frontend && npm install && npm run dev

# Build
./build.sh          # Linux
build.bat           # Windows
```

## Architecture

* `backend/main.py` — entrypoint, serves frontend static, mounts all routers under `/api`
* `backend/database.py` — SQLAlchemy models + engine. DB path resolves relative to `sys.executable` when frozen
* `backend/schemas.py` — Pydantic validation schemas
* `backend/routers/` — one file per domain, all mounted in `main.py` under `/api` prefix
* `frontend/pages/` — one file per route, grouped in `App.jsx` under `GRUPOS_NAV`
* `frontend/api/` — one file per domain, all use shared `client.js` instance (never raw axios)
* New features follow: model → schema → router → api file → page

## Gotchas

* **No DB migrations framework**: schema changes use manual scripts (`migrar_*.py`). Applied ones live in `backend/old/`. Use table recreation preserving IDs/FKs.
* **DB location**: `dados/rastreio.db` relative to the executable. In dev, `backend/dados/rastreio.db`.
* **Frontend proxy**: Vite proxies `/api` to `:9742`. The executable serves both API and SPA.
* **CI**: `build.sh`/`build.bat` assume `node_modules` exists. CI runs `npm ci` first.
* **Tray**: `tray.py` manages the executable lifecycle and degrades gracefully if unavailable.
* **Stats**: refunds reduce expense (not revenue); transfers are excluded from metrics.
* **Asset accounting**: FIFO for investments; `contabilizacao` (`investimento` vs `patrimonio`) determines the accounting path.

## Never Touch the Real Database

`backend/dados/rastreio.db` holds the user's live financial data. It is not a
test fixture and it is not disposable. These rules are not advisory.

1. **Never start the backend, or any script that imports `database`, without
   pointing `RASTREIO_DB_DIR` at a throwaway copy first.** The variable is read
   at import time (`backend/database.py:34`) and takes precedence over the
   frozen-executable path, so it must be set in the *same* command:

   ```bash
   # correct
   RASTREIO_DB_DIR=/tmp/rastreio-sandbox uvicorn main:app --port 9742

   # wrong — opens the real DB, and any endpoint may write to it
   uvicorn main:app --port 9742
   ```

   Remember `RASTREIO_DB_DIR` is a *directory*; the file is `<dir>/rastreio.db`.
   Seed it with `cp backend/dados/rastreio.db "$DIR/rastreio.db"`.

2. **Never open the real DB with the `sqlite3` CLI, not even read-only.** Any
   `INSERT`, `DELETE`, `UPDATE`, `DROP`, `ALTER`, `VACUUM` or `REPLACE` typed by
   hand mutates production without a transaction to roll back, and `sqlite3`
   gives no confirmation. If a read is genuinely unavoidable, open the file
   read-only by URI so the database itself rejects writes:

   ```bash
   sqlite3 "file:backend/dados/rastreio.db?mode=ro" "PRAGMA integrity_check;"
   ```

   Prefer `RASTREIO_DB_DIR` + a copy even for reads: a copy can be corrupted
   freely, and the schema in `docs/divida-tecnica.md` (D1a) shows the real DB
   is already in a state where a tool's defaults can produce surprising results.

3. **Never let a test or a manual probe touch production data.** Exercise
   writes against a copy, inside a transaction that is always rolled back, and
   say so explicitly in the notes. If a write did land by accident, report it
   with the row count before and after, do not quietly clean up, and confirm
   `PRAGMA integrity_check` — deleting a row does not restore the file byte for
   byte, so an MD5 change after a write-then-delete is expected, not evidence of
   damage.

Both failures happened in one session: a browser import wrote a real
transaction, and a hand-typed `DELETE` probe ran against the live file before
anyone decided whether that was acceptable. Neither was necessary — a copy in
`/tmp` answered both questions.

## Working Rules

* Keep changes **KISS and minimal**. Prefer existing patterns over new abstractions, layers, or duplicate logic.
* Do not refactor unrelated code or introduce unnecessary dependencies.
* Reuse existing frontend components and `componentes.css`; avoid new CSS unless genuinely necessary.
* Keep user-facing text in **PT-PT** and follow existing UI conventions.
* Treat financial calculations, FIFO, sales, reimbursements, imports and patrimony calculations as correctness-critical.
* Before finishing, run the relevant tests/build/lint checks and inspect `git diff`.
* Do not assume undocumented business rules; inspect the existing code/docs/tests first.
