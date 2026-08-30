# Interview Management Portal

Internal tool for recording physical/verbal interview feedback. See `CONTEXT.md` for the domain glossary and `docs/spec-v1.1.md` for the full spec.

## Local dev

```bash
docker-compose up
```

This brings up:

- **Postgres** on `localhost:5433` (`postgres`/`postgres`, db `interview_platform`) — mapped to 5433 on the host, not the default 5432, since this machine already runs a separate local Postgres for the `ai_valuation`/Superset project on 5432 (see the root `CLAUDE.md`). The `api` container talks to Postgres over the internal Docker network on the standard 5432, so this only affects host-side tools (`psql`, a local `alembic` run outside Docker).
- **API** (FastAPI) on `localhost:8000` — health check at `GET /health`
- **Frontend** (Vite/React) on `localhost:5173`

## Migrations

Run from `backend/`, against a running Postgres (the Compose one, on host port 5433):

```bash
cd backend
pip install -r requirements.txt
export DATABASE_URL="postgresql+psycopg2://postgres:postgres@localhost:5433/interview_platform"
alembic upgrade head          # apply all migrations
alembic revision --autogenerate -m "description"   # create a new migration
```

## Seed data

Once the Auth module ships, the first Admin account is created with:

```bash
cd backend
python -m app.seed.create_admin
```

## Tests

```bash
cd backend
pip install -r requirements.txt
pytest
```

CI (`.github/workflows/ci.yml`) runs migrations + the full test suite against a real Postgres service container on every push.
