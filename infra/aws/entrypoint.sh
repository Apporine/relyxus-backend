#!/bin/sh
set -eu
cd /app/services/api
uv run --frozen --no-dev alembic upgrade head
exec uv run --frozen --no-dev uvicorn --factory relyxus_api.app:build_app --host 0.0.0.0 --port 8000
