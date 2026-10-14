# relyxus-backend

Backend for Relyxus, Apporine's AI incident-response and operational-resilience platform.

- What is being built: [docs/spec/requirements-register.md](docs/spec/requirements-register.md)
- Progress by feature and PR: [docs/implementation.md](docs/implementation.md)
- Engineering rules: [context.md](context.md) and [docs/adr/](docs/adr/)

## Setup

Requires [uv](https://docs.astral.sh/uv/). uv installs the pinned Python version (3.13) itself.

```sh
uv sync                    # create .venv with locked dependencies
uv run pre-commit install  # enable the pre-commit checks
```

## Local database

```sh
docker compose up -d                      # PostgreSQL 18 + pgvector
cp .env.example .env                      # then export the variables
cd services/api && uv run alembic upgrade head
```

Integration tests run when `RELYXUS_TEST_DATABASE_URL` is set; otherwise they are skipped and reported. CI always runs them.
On Windows, psycopg's async driver needs the selector event loop; tests and Alembic set it automatically.

## Checks

```sh
uv run ruff check          # lint
uv run ruff format --check # format
uv run mypy                # type check (strict)
uv run pytest              # tests
```

## Layout

| Path | Contents |
|---|---|
| `packages/licensing` | `apporine_licensing`: licence schema and offline verifier |
| `services/api` | `relyxus_api`: FastAPI REST API (`RELYXUS_ENVIRONMENT=local RELYXUS_PUBLIC_BASE_URL=http://localhost:8000 uv run uvicorn --factory relyxus_api.app:build_app`) |
| `packages/schemas` | Generated JSON Schemas and the OpenAPI contract |
| `docs/spec` | Requirements register extracted from the source specifications |
| `docs/adr` | Architecture decision records |
