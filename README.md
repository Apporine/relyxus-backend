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
| `docs/spec` | Requirements register extracted from the source specifications |
| `docs/adr` | Architecture decision records |
