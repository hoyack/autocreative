# Phase 20 API + worker launchers. See README for details.
.PHONY: serve serve-web serve-worker migrate fresh-db docker-up docker-down test test-api test-all

# Start both processes with honcho (requires `uv sync --extra dev`).
serve:
	uv run honcho start

# Start only the web process (foreground).
serve-web:
	uv run uvicorn flyer_generator.api:app --reload --host 127.0.0.1 --port 8000

# Start only the arq worker (foreground).
serve-worker:
	uv run arq flyer_generator.api.worker.WorkerSettings

# Apply all pending migrations.
migrate:
	uv run alembic upgrade head

# Blow away the dev SQLite DB and re-migrate from scratch.
fresh-db:
	rm -f flyer.db flyer.db-journal
	uv run alembic upgrade head

# Bring up the compose stack (Postgres + Redis).
docker-up:
	docker compose up -d

# Tear down the compose stack (keeps volumes).
docker-down:
	docker compose down

# Run only the new Phase 20 tests.
test-api:
	uv run python -m pytest tests/api/ -q

# Run the full non-slow suite (regression target from API-14).
test-all:
	uv run python -m pytest tests/ -q -m "not slow"

# Alias for convenience.
test: test-all
