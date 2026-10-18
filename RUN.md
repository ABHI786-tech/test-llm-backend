# Run Commands

Every command needed to install, run, test and lint this project.

Run all backend commands from the repo root:

```bash
cd "D:\abhinash\All projects\llm"
```

---

## 1. Prerequisites

| Tool | Version used | Check with |
| --- | --- | --- |
| Python | 3.14 | `python --version` |
| Node.js | 24.x | `node --version` |
| npm | 11.x | `npm --version` |
| Docker | any | `docker --version` |

The venv already exists at `.venv/`. Skip step 2 if you are using it.

---

## 2. First-time setup (only once)

### Backend

```bash
# install Python dependencies (includes LiteLLM, which drives every provider)
.venv/Scripts/python.exe -m pip install -r requirements.txt

# install the linter
.venv/Scripts/python.exe -m pip install ruff
```

### Frontend

```bash
cd frontend
npm install
cd ..
```

---

## 3. Start the database

Postgres must be running before the app boots. Tables are created automatically on
startup, so no manual migration is needed.

```bash
docker compose up -d
```

Check it is up:

```bash
docker compose ps
```

Stop / remove it:

```bash
docker compose stop
docker compose down
```

---

## 4. Configure environment variables

`.env` in the repo root:

```
DATABASE_URL= "postgresql+asyncpg://abhi:one2three@localhost:5432/mydb"

# Read by LiteLLM. Add the keys for the columns you want to run.
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
# GEMINI_API_KEY is often already exported in your shell; leave blank to use that.

LITELLM_MODEL_CLAUDE=anthropic/claude-sonnet-4-5
LITELLM_MODEL_GEMINI=gemini/gemini-2.5-flash
LITELLM_MODEL_GPT=gpt-4o-mini

LITELLM_MODEL=gpt-4o-mini
```

- `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` — LiteLLM reads each
  provider's key from its usual environment variable, so no per-provider SDK is needed.
  A column with no key is marked `failed` in the review grid and the other columns
  still work. Every other route works without any key.
- `LITELLM_MODEL_CLAUDE` / `_GEMINI` / `_GPT` — LiteLLM `provider/model` ids.
- `LITELLM_MODEL` — model used by the single-question `/ask` route.

---

## 5. Run the backend

```bash
.venv/Scripts/python.exe -m uvicorn main:app --reload
```

Or on an explicit port (this is what the frontend defaults to):

```bash
.venv/Scripts/python.exe -m uvicorn main:app --reload --port 8000
```

| URL | What |
| --- | --- |
| http://localhost:8000/docs | Swagger UI (custom dark theme) |
| http://localhost:8000/openapi.json | OpenAPI schema |
| http://localhost:8000/media-outlets | Media outlet list |

Stop the server with `Ctrl+C`.

---

## 6. Run the frontend

New terminal:

```bash
cd frontend
npm run dev
```

Open http://localhost:3000

The frontend calls `http://localhost:8000` by default. Point it elsewhere with
`frontend/.env.local`:

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

CORS for `localhost:3000` is already configured in `main.py`.

Production build:

```bash
cd frontend
npm run build
npm run start
```

Lint and typecheck (Next 16 removed `next lint`, so these use the CLI directly):

```bash
cd frontend
npm run lint
npm run typecheck
```

---

## 7. Run both at once

Terminal 1 — database + backend:

```bash
cd "D:\abhinash\All projects\llm"
docker compose up -d
.venv/Scripts/python.exe -m uvicorn main:app --reload --port 8000
```

Terminal 2 — frontend:

```bash
cd "D:\abhinash\All projects\llm\frontend"
npm run dev
```

---

## 8. Test the API with curl

### All routes

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/register` | student registration |
| `GET` | `/media-outlets` | list outlets (nested personnel) |
| `POST` | `/media-outlets` | create outlet + its personnel |
| `GET` | `/media-outlets/{id}` | one outlet |
| `PATCH` | `/media-outlets/{id}` | partial update + personnel upserts |
| `DELETE` | `/media-outlets/{id}` | delete (cascades personnel) |
| `POST` | `/media-outlets/{id}/ask` | LLM answer from the record JSON |
| `POST` | `/media-outlets/{id}/suggest` | per-field suggestions per model column |
| `GET` | `/media-outlets/{id}/personnel` | list nested personnel |
| `POST` | `/media-outlets/{id}/personnel` | add a person |
| `GET` | `/media-outlets/{id}/personnel/{pid}` | one person |
| `PATCH` | `/media-outlets/{id}/personnel/{pid}` | update a person |
| `DELETE` | `/media-outlets/{id}/personnel/{pid}` | remove a person |

### Create a media outlet with its personnel

```bash
curl -s -X POST http://localhost:8000/media-outlets -H "Content-Type: application/json" -d '{"maven_id":"maven-1042","name":"The Daily Chronicle","aliases":["Chronicle","Daily Chron"],"slogan":"All the news that fits","website":"https://example.com","email":"hello@example.com","phone":"+44 20 7946 0000","media_type":"newspaper","subtype":"national_daily","language":"English","direct_owner":"Chronicle Group","personnel":[{"first_name":"Ada","last_name":"Lovelace","email":"ada@example.com","phone":"+44 20 7946 0001","title":"Editor in Chief","linkedin_url":"https://linkedin.com/in/ada"},{"first_name":"Alan","last_name":"Turing","email":"alan@example.com","title":"Technology Reporter"}]}'
```

Only `maven_id` and `name` are required.

### List / get one

```bash
curl -s http://localhost:8000/media-outlets
curl -s http://localhost:8000/media-outlets/1
```

### Update: change fields, upsert people, remove people

`personnel` entries with an `id` update that person; entries without one are inserted.
Removals are explicit via `remove_personnel_ids`, so a PATCH never drops people silently.

```bash
curl -s -X PATCH http://localhost:8000/media-outlets/1 -H "Content-Type: application/json" -d '{"slogan":"Truth, timely","personnel":[{"id":2,"title":"Editor Emeritus"},{"first_name":"Grace","last_name":"Hopper","email":"grace@example.com","title":"Science Correspondent"}],"remove_personnel_ids":[3]}'
```

### Nested personnel

```bash
curl -s http://localhost:8000/media-outlets/1/personnel
curl -s -X POST http://localhost:8000/media-outlets/1/personnel -H "Content-Type: application/json" -d '{"first_name":"Katherine","last_name":"Johnson","email":"kj@example.com","title":"Research Analyst"}'
curl -s -X PATCH http://localhost:8000/media-outlets/1/personnel/2 -H "Content-Type: application/json" -d '{"title":"Editor Emeritus"}'
curl -s -X DELETE http://localhost:8000/media-outlets/1/personnel/2 -o /dev/null -w "delete -> %{http_code}\n"
```

### Ask the LLM a question about an outlet

Uses `LITELLM_MODEL`. Needs that provider's key; without it returns `503`.

```bash
curl -s -X POST "http://localhost:8000/media-outlets/1/ask?question=what%20is%20the%20email%20of%20the%20editor"
```

### Get per-field suggestions from several models at once

This is what the **Run LLM** button calls. Each column is independent: a model with no
key reports its own error and the others still return, so the request never fails
because one provider is unconfigured.

```bash
curl -s -X POST "http://localhost:8000/media-outlets/1/suggest?columns=claude,gpt"
```

Response shape (one entry per column, suggestions keyed by field):

```json
{
  "media_outlet_id": 1,
  "record": { "...": "..." },
  "columns": [
    {
      "column": "gpt",
      "model": "gpt-4o-mini",
      "ok": true,
      "error": null,
      "suggestions": [
        {"key": "name", "value": "Disney+", "confidence": 0.95, "note": "already correct"},
        {"key": "language", "value": ["English", "Spanish"], "confidence": 0.82, "note": null}
      ]
    },
    {
      "column": "claude",
      "model": "anthropic/claude-sonnet-4-5",
      "ok": false,
      "error": "ANTHROPIC_API_KEY is not set on the server",
      "suggestions": []
    }
  ]
}
```

### Delete an outlet (cascades its personnel)

```bash
curl -s -X DELETE http://localhost:8000/media-outlets/1 -o /dev/null -w "delete -> %{http_code}\n"
```

### Expected error responses

| Case | Status | Body |
| --- | --- | --- |
| Duplicate personnel email | 409 | `{"detail": "One of the personnel emails is already in use"}` |
| Duplicate email in one payload | 422 | `personnel contains duplicate email addresses` |
| Unknown outlet id | 404 | `{"detail": "No media outlet with id 999"}` |
| Unknown personnel id | 404 | `{"detail": "No personnel with id 5 on media outlet 1"}` |
| Blank/short field | 422 | FastAPI validation list |
| No API key (single route) | 503 | `{"detail": "<PROVIDER>_API_KEY is not set on the server"}` |
| No API key (per-column) | 200 | the column comes back with `"ok": false` and its own `error` |
| Model returns bad JSON | 502 | `{"detail": "The model did not return valid JSON: ..."}` |

---

## 9. Lint

```bash
# from the repo root
.venv/Scripts/python.exe -m ruff check .
```

`.venv/Scripts/ruff.exe check .` works too once ruff is installed. `ruff.toml`
excludes `.venv`, `__pycache__`, `frontend` and `main copy.py`, so only Python source
is scanned.

Auto-fix:

```bash
.venv/Scripts/python.exe -m ruff check . --fix
```

TypeScript is checked by the frontend build:

```bash
cd frontend && npm run build
```

---

## 10. Reset the database

Tables are created from the models on startup.

### Drop just the media tables (fastest)

```bash
docker exec postgres_db psql -U abhi -d mydb -c "DROP TABLE IF EXISTS personnel CASCADE; DROP TABLE IF EXISTS media_outlets CASCADE;"
```

Add `-it` if you want an interactive psql prompt (`docker exec -it ...`); omit it when
running from a script or a shell with no TTY, otherwise psql reports
`cannot attach stdin to a TTY-enabled container`.

**Restart the backend after dropping.** Tables are created in the lifespan
(`Base.metadata.create_all`), which runs once at startup. Dropping a table out from
under a running server leaves every personnel route returning `500` (relation does
not exist) until you restart uvicorn — `--reload` will not trigger on a DB change.

### Nuke everything, including all data

`docker-compose.yml` declares no named volume, so Postgres stores data in an
**anonymous** volume — `docker volume rm <name>` has no predictable name to target.
Remove the container and its anonymous volumes together:

```bash
docker compose down -v
docker compose up -d
```

On Docker Desktop you can also do it from the GUI: Containers → postgres_db →
Delete, with "Remove volumes" ticked.

Warning: this deletes all rows in every table, including `students` and `media_outlets`.

Both options need the backend restarted afterwards for the schema to come back (see the
note above).

---

## Troubleshooting

**`ConnectionError: unexpected connection_lost() call`**
Postgres is still starting up. Wait a few seconds after `docker compose up -d`, or run
`docker compose ps` until it reports `Up`.

**`503 <PROVIDER>_API_KEY is not set on the server`**
Expected until you add a key to `.env`. Restart uvicorn after editing `.env`. On the
review grid the same condition shows as a `failed` badge in that model's column header
instead of an error, so the other columns still work.

**`Cannot reach the API at http://localhost:8000` (frontend)**
The backend is not running, or is on a different port. Set `NEXT_PUBLIC_API_URL` in
`frontend/.env.local`.

**Frontend changes not showing**
Stop with `Ctrl+C` and rerun `npm run dev`.

**Port 8000 or 3000 already in use**
```bash
.venv/Scripts/python.exe -m uvicorn main:app --reload --port 8001
cd frontend && npm run dev -- --port 3001
```
Add the new frontend origin to `allow_origins` in `main.py` if you change port 3000.

**`Column type did not change`**
There is no Alembic. `create_all` never alters an existing table — drop the table
(section 10) or write a migration.

**`no such volume: llm_postgres_data`**
There is no named volume; `docker-compose.yml` does not declare one, so Postgres uses
an anonymous volume. Use `docker compose down -v` instead (section 10).

---

## Project layout

```
main.py               FastAPI app, lifespan, CORS, /docs, error handlers
core/database.py      async engine, Base, get_db dependency
core/exceptions.py    AppError base + domain errors
models/models.py      Media_outlets, Personnel, Students ORM models
schemas/schemas.py    Pydantic request/response schemas
routers/routers.py    /register, /media-outlets, nested personnel
services/services.py  business logic
services/llm.py       LiteLLM acompletion, prompts, structured-output parsing
repo/repo.py          database access
frontend/             Next.js app (see frontend/README.md)
static/               swagger-dark.css
docker-compose.yml    postgres:16-alpine on localhost:5432, db "mydb"
```