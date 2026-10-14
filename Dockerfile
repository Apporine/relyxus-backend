FROM python:3.13-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY packages ./packages
COPY services ./services
COPY infra/aws/entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh \
    && uv sync --frozen --no-dev --package relyxus-api

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
