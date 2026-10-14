# ADR-0001: Engineering conventions for the Python backend

- **Status:** Accepted provisionally (2026-10-14). Pending owner confirmation of Q-04, Q-14, Q-29, Q-31 in the requirements register.
- **Context documents:** context.md; TSD §6, §14, §17; MP §36, §38.

## Context

context.md sets naming and layout rules written for a generic stack. The locked Relyxus stack is Python + FastAPI + Ruff + mypy (TSD-6.01). Several context.md rules cannot be applied literally in Python:

- **Hyphenated files.** Python cannot import modules with hyphens, so `user-service.py` is not importable.
- **camelCase names.** camelCase functions and variables fail Ruff's PEP 8 naming rules (N802, N806, N815).

## Decisions

1. **Naming (Q-14).** PEP 8 inside Python:
   - `snake_case` for modules, packages, functions and variables
   - `PascalCase` for classes
   - `UPPER_SNAKE_CASE` for constants
   - context.md's intent is kept: booleans start with `is_`, `has_`, `can_` or `should_`; functions start with a verb; no abbreviations; no `data` / `info` / `temp` names.
   - Directory names outside Python packages stay kebab-case.
2. **Layout (Q-04).** This repository is laid out as the backend half of the Relyxus monorepo described in MPS-22A.02 and TSD-17.02:
   - `packages/` holds shared libraries (`packages/licensing`, later `packages/schemas`).
   - `services/` holds runtime services (`services/api`, …).
   - `policy/opa/` holds Rego policies.
   - `docs/spec` and `docs/adr` hold documentation.
   - Inside each service, code is grouped by feature as context.md §2 requires: `modules/<feature>/{controller,service,repository,model,schema}.py`.
3. **Toolchain (Q-29).**
   - Python 3.13, pinned in `.python-version`.
   - A `uv` workspace, with `uv.lock` committed.
   - Ruff for lint and format, mypy `--strict`, pytest.
   - Pre-commit runs lint, format, type check, tests and Gitleaks (context.md §14); CI runs the same checks.
4. **Confidential sources (Q-31).** The source specifications in `important/` are marked Confidential, so they are git-ignored. The requirements register in `docs/spec/` is the committed, traceable extract.
5. **Line endings.** LF everywhere, enforced via `.gitattributes`.

## Consequences

- Rules in context.md that are language-neutral (layering, validation, errors, database, security, Git workflow) apply unchanged.
- If Q-14 is answered differently, the rename is mechanical, but every module path changes. Decide before services/api starts.
