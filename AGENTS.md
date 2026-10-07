# Rastreio-DB — Agent Instructions

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
   gives no confirmation. If you need real data, ask the user. 
   Do not open the file yourself, not even read-only.

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
(For agents: never run this against the real DB. See "Never Touch the Real Database".)

# Frontend
cd frontend && npm install && npm run dev

# Build
./build.sh          # Linux
build.bat           # Windows
```

## Tests

* Run with `./backend/test.sh` (it uses `backend/venv`; never the system `python3`).
* `pytest.ini` lives in `backend/` and already sets `-q`. **Do not pass `-q` again**:
  two `-q` become `-qq` and hide the final summary line. Running from the repo
  root fails with `ModuleNotFoundError`.
* Tests never touch the real DB: `tests/conftest.py` sets `RASTREIO_DB_DIR` to a
  temp dir before any import. Do not weaken it, and do not import `main` from tests.
* Expected values are **computed by hand** and written as constants with the
  calculation in a comment. Never run the function and paste its output into the assert.
* Use real enums (`TipoCategoria`, `TipoMovimento`), never strings.
* Questionable current behaviour is fixed as-is and tagged
  `# DEVIDA-TECNICA: Dn` (matching `docs/divida-tecnica.md`).
* Verify new tests by **mutation** on a copy in `/tmp` (rsync without
  `backend/dados`, `backend/venv`, `.git`; clear `__pycache__`; confirm the
  mutation really changed the file). Print real results, never an empty table.
  Equivalent mutants are reported, not "fixed".

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


## Working Rules

* Keep changes **KISS and minimal**. Prefer existing patterns over new abstractions, layers, or duplicate logic.
* Do not refactor unrelated code or introduce unnecessary dependencies.
* Reuse existing frontend components and `componentes.css`; avoid new CSS unless genuinely necessary.
* Keep user-facing text in **PT-PT** and follow existing UI conventions.
* Treat financial calculations, FIFO, sales, reimbursements, imports and patrimony calculations as correctness-critical.
* Before finishing, run ./backend/test.sh and inspect git diff
* Do not assume undocumented business rules; inspect the existing code/docs/tests first.

## Technical Debt

* `docs/divida-tecnica.md` is the source of truth for `Dn` numbering.
* When fixing an item, in the **same commit**: fix the code, invert the
  characterization test that fails on purpose, and mark the item as resolved in the doc.
* Do not decide business rules (D3, D15, D20, ...) yourself. Describe the options and ask Pedro.

## Stop Gates

* When a prompt says **STOP** / "PÁRA" and waits for approval, stop. This holds even
  if the context is compacted and the conversation restarts: re-read the
  instructions and stop again.
* Never go beyond the task. If something outside it looks wrong, report it, do not fix it.
* Do not commit `AGENTS.md` changes unless asked.

## Git

* `git add <file>` explicitly, never `-A` or `.`. Read `git diff --cached` before
  every commit: the edit tool may accept approximate matches and apply something
  different from what was intended.
* One commit per concern. Types: `feat`, `fix`, `refactor`, `chore`, `test`, `docs`.
  Messages in PT-PT, with accents.
* Check for non-Latin characters only on versioned files, never with `grep -r` over
  `backend/` (it reads `backend/dados/` and `backend/venv/`):
  `git ls-files -z | xargs -0 grep -nIP '(?!\x{B7})[\p{Hangul}\p{Han}\p{Hiragana}\p{Katakana}\p{Cyrillic}\p{Greek}\p{Arabic}]'`
* Always report real values (test counts, `stat` of the real DB), not "unchanged".