# Implementation Tracker

Tracks every feature and every PR from the requirements register ([docs/spec/requirements-register.md](spec/requirements-register.md)) to merged code. Update this file in the same PR as the change it describes.

**Status legend:** `planned` · `in progress` · `in review` (branch ready, PR not merged) · `merged` · `blocked` (needs an answer, see the Q-ID)

**Rules:** branch from `develop` (stacked on the previous PR when it depends on it), one branch per PR, conventional commits, under ~400 changed lines excluding generated lockfiles, tests and docs in the same PR (context.md §14).

---

## Provisional decisions in force

Applied so work could start. Each is overridable; see [ADR-0001](adr/0001-engineering-conventions.md) and [ADR-0002](adr/0002-license-envelope-and-canonicalisation.md).

| Q-ID | Decision applied | Where recorded |
|---|---|---|
| Q-04 | Repo laid out as the monorepo's backend half: `packages/`, `services/`, `policy/`, `docs/` | ADR-0001 |
| Q-14 | PEP 8 naming in Python (snake_case modules/functions, PascalCase classes); context.md feature grouping kept | ADR-0001 |
| Q-29 | Python 3.13, managed with `uv` workspace | ADR-0001 |
| Q-30 | Branches pushed and PRs raised on GitHub; merged after required CI checks pass | this file |
| Q-31 | `important/` (confidential source documents) git-ignored, not committed | ADR-0001 |
| Q-32 | Licence signature ECDSA P-256 / SHA-256 (AWS KMS `ECDSA_SHA_256`) | ADR-0002 |
| Q-33 | Verifier trusts only a caller-supplied, environment-tagged key set | ADR-0002 |
| Q-07b | Grace policy registry with a single `standard-30d` policy; unknown IDs rejected | ADR-0002 |

Still open and **not** assumed: Q-01, Q-02, Q-03 (no HTTP endpoints built yet), Q-07a (which operations Grace/Expired restrict), Q-08 (Relyxus entitlement catalogue), Q-11, Q-16, Q-18, Q-19, Q-34.

---

## Feature F-LIC — Commercial licence verification (Relyxus side)

**Scope:** schema, signed envelope, canonicalisation and the offline local verifier library that Relyxus and the `relyxus` CLI use. The issuer, entitlement service, KMS signing and admin screens are Apporine Control Plane work (system B), tracked separately as F-ACP-LIC.

**Requirement coverage target:** LIC-1.02, LIC-2.03, LIC-2.04, LIC-2.05, LIC-5.01–5.04, LIC-6.03, LIC-6.04, LIC-7.02–7.04, LIC-12.01, LIC-12.02, LIC-13.01–13.05 (model only), LIC-17.02 (forgery, wrong-customer, downgrade at verify time), LIC-19.01, LIC-19.02, LIC-19.07; MPS-29.01–29.08, MPS-29.11, MPS-29.15–29.17, MPS-29.20 (verifier parts); TSD-23.04, TSD-23.07, TSD-23.11, TSD-23.14; DEP-23.08 (verifier fixtures); MP-13.01, MP-14.01, MP-16.01, MP-19.01.

| # | GitHub PR / branch | Scope | Requirement IDs | Status |
|---|---|---|---|---|
| 1 | [#1](https://github.com/Apporine/relyxus-backend/pull/1) `docs/requirements-register` | Requirements register + this tracker | (all — traceability) | merged |
| 2 | [#2](https://github.com/Apporine/relyxus-backend/pull/2) `chore/python-workspace-foundation` | uv workspace, Python 3.13, Ruff, mypy, pytest, pre-commit, CI, ADR-0001 | MPS-17.07, MPS-22.19, TSD-6.01, TSD-12.01, TSD-14.02, MP-38.01 | merged |
| 3 | [#3](https://github.com/Apporine/relyxus-backend/pull/3) `feat/license-canonical-json` | ADR-0002, RFC 8785 canonical JSON, golden vectors | LIC-5.03, LIC-19.01, TSD-23.11 | merged |
| 4 | [#4](https://github.com/Apporine/relyxus-backend/pull/4) `feat/license-payload-schema` | Payload/envelope models, typed errors, exported JSON Schemas + drift test | LIC-5.01, LIC-5.02, LIC-5.04, LIC-12.01, LIC-12.02, MPS-29.05, MPS-29.06, MP-19.01 | merged |
| 5 | [#5](https://github.com/Apporine/relyxus-backend/pull/5) `feat/license-signature-verification` | Key set, base64url, ECDSA verify, golden signature vector | LIC-6.03, LIC-6.04, MPS-29.15–29.17, TSD-23.04, TSD-23.07 | merged |
| 6 | [#6](https://github.com/Apporine/relyxus-backend/pull/6) `feat/license-verifier` | Verification pipeline, binding checks, state evaluation, grace registry, entitlement access | LIC-2.05, LIC-7.02–7.04, LIC-13.x, LIC-19.02, TSD-23.14, MPS-29.04, MPS-29.08, MPS-29.20 | merged |
| 7 | `feat/license-key-set-document` | Versioned trusted key-set file format + schema + loader | LIC-6.04, DEP-23.01, TSD-23.04 | in review |
| 8 | `feat/license-cli-inspect-verify` | `relyxus license inspect\|verify` | LIC-15.03, DEP-23.02 | planned |
| 9 | `feat/license-store` | install/replace/status, Superseded history, downgrade/replay protection (needs DB foundation) | LIC-7.07, LIC-12.03, LIC-17.02, DEP-23.07 | blocked (DB foundation) |
| 10 | `feat/license-runtime-integration` | Startup + periodic verification, embedded key pinning, safe degradation | LIC-10.01, MPS-6A.11, MPS-29.04 | blocked (Q-07a, Q-33) |
| 11 | `feat/license-connected-refresh` | Outbound signed status client, cache, outage handling | LIC-9.03, LIC-10.02, LIC-10.03, LIC-19.03 | planned (Licensing phase 5) |
| 12 | `feat/license-airgap-import` | Offline import/renewal tooling | LIC-11.02, LIC-19.04 | planned (Licensing phase 6) |

GitHub PR #7 was a temporary CI diagnostic, closed unmerged.

### Progress log

_Each entry: PR number, date, what changed, requirement IDs covered, test/lint results as actually run._

- **PR 1 — 2026-10-14** — Added requirements register (846 + 75 LIC requirements, 33 open questions) and this tracker. No code.
- **PR 2 — 2026-10-14** — uv workspace (Python 3.13), `apporine-licensing` package skeleton, Ruff (incl. bandit, no-print, no-blind-except, no commented-out code), mypy `--strict`, pytest, pre-commit (lint, format, types, tests, Gitleaks), GitHub Actions CI, `.gitignore` (excludes `important/`, key material), LF line endings, ADR-0001. **Covered:** TSD-6.01 (tooling), TSD-14.02 (lint/type/unit/secret-scan CI; policy, migration, container scans and E2E come with their features), MPS-17.07 (secret scanning, mandatory-review part only), MPS-22.19, MP-38.01. **Results:** `pre-commit run --all-files`: ruff check, ruff format, mypy, pytest (1 passed), gitleaks — all Passed. CI workflow not yet run on GitHub (nothing pushed).
- **PR 3 — 2026-10-14** — ADR-0002 (envelope, canonicalisation, algorithm, payload schema v1, trusted key set, verification order, state evaluation; provisional on Q-07b/Q-32/Q-33). `apporine_licensing.canonical_json`: RFC 8785 serialisation restricted to integers/strings/bools/null/arrays/objects, UTF-16 key ordering, exact escaping; strict parser rejecting duplicate keys, floats, NaN/Infinity, invalid UTF-8, BOM; `is_canonical`. `errors.py` with `LicenseError` base and stable codes. **Covered:** LIC-5.03, LIC-19.01 (canonicalisation vectors; signature vectors in PR 5), TSD-23.11 (canonical bytes). **Results:** ruff check/format pass, mypy strict pass, pytest 43 passed.
- **PR 4 — 2026-10-14** — `LicensePayload` v1 (closed schema; lowercase UUIDs; UTC `…Z` second-precision timestamps; deployment bindings with production/non_production/disaster_recovery allowances; sorted unique product-namespaced entitlements; namespaced non-negative limits; support tier; cross-field date/duplicate/namespace rules), `parse_payload` (strict parse → canonical-bytes check → schema version → schema), `LicenseEnvelope` v1 + `parse_envelope`, typed verification errors with stable codes, validation messages that never echo input values, JSON Schemas exported to `packages/schemas/licensing/` with a drift test. Pydantic 2 added; mypy pydantic plugin enabled. **Covered:** LIC-5.01, LIC-5.02, LIC-5.04 (closed schema), LIC-12.01, LIC-12.02, MPS-29.05, MPS-29.06, MP-19.01, DEP-23.01 (`license.schema.json` source). **Results:** ruff check/format pass, mypy strict pass, pytest 103 passed.
- **PR 5 — 2026-10-14** — Strict unpadded base64url (single valid encoding); `TrustedKey`/`TrustedKeySet` (P-256 public keys only, private PEM refused, environment tag, UTC signing window, duplicate/empty set refused); `authenticate_envelope` (supported algorithm → known key → matching environment → algorithm/key consistency → ECDSA-SHA256 over exact payload bytes). Golden vector `tests/vectors/golden-license-v1.json` (public key only; signing key discarded). Test signing helpers in `tests/signing_support.py` with per-session generated keys. **Covered:** LIC-6.03 (non-prod key never verifies prod), LIC-6.04 + MPS-29.16 (rotation overlap), LIC-19.01 (signature golden vector), MPS-29.15 (public key set only, private key refused), MPS-29.17 (tampered payload, malformed envelope, unsupported algorithm), TSD-23.04, TSD-23.07, TSD-23.11 (unknown key IDs), MP-14.01. **Results:** pre-commit all hooks Passed (ruff, format, mypy strict, pytest 135 passed, gitleaks).
- **PR 6 — 2026-10-14** — `LicenseVerifier.verify(artifact, now)`: size cap → envelope → signature → canonical payload → product/customer/deployment binding → key signing window → `not_before` with configurable clock-skew tolerance → state. `LicenseState` enum with all seven LIC §7 states; offline evaluation yields Active/Grace/Expired only; provisional grace registry (`standard-30d`). `VerifiedLicense` exposes matched deployment binding (production/non-production/DR), grace end, `has_entitlement`, `get_limit`. Explicit clock (naive `now` refused). **Covered:** LIC-2.04 (no network), LIC-2.05 + MPS-29.04 + DEP-23.08 (expiry is a state, not an error), LIC-7.02–7.04, LIC-12.01, LIC-12.02 (allowance surfaced), LIC-13.02–13.03 (entitlement/limit read API), LIC-19.02 (tamper, expiry, clock skew, wrong customer/deployment, key rotation), TSD-23.14 (positive, tampered, expired, not-yet-valid, wrong-customer, wrong-deployment, wrong-key, rotated-key), MPS-29.08, MPS-29.11 (local verification), MPS-29.17. **Not covered yet:** enforcement of what Grace/Expired restrict (Q-07a), Suspended/Revoked (PR 10), Superseded/downgrade protection (PR 8). **Results:** pre-commit all hooks Passed; pytest 161 passed; coverage of `apporine_licensing` 99% (uncovered: schema-writer entry point, one unreachable algorithm-mismatch branch).

---

## Feature F-API-FOUNDATION — Relyxus API service foundation (MPS Phase 0)

**Scope:** the `services/api` FastAPI service: configuration, probes, OpenAPI contract, error model, observability, persistence, tenancy and RLS. Conventions: [ADR-0003](adr/0003-api-conventions.md).

| # | Branch | Scope | Requirement IDs | Status |
|---|---|---|---|---|
| A1 | `feat/api-service-skeleton` | Settings (fail fast), app factory, `/health`, `/ready`, `/docs`, `/docs.json`, OpenAPI export + drift test, ADR-0003 | TSD-11.01 (probes), MP-28.01, MPS-22A.03 (adapted), MP-9.01, context.md §6/§11 | in review |
| A2 | `feat/api-error-handling` | RFC 9457 problem details, typed errors, correlation-ID middleware, structured JSON logging | MPS-22A.04, MP-34.01, MP-28.01, context.md §8/§12 | in review |
| A3 | `feat/api-envelope-pagination` | Success envelope with meta, cursor pagination primitives | MPS-22A.04, context.md §5 | in review |
| A4 | `feat/api-database-foundation` | SQLAlchemy 2, psycopg 3, Alembic, PostgreSQL in CI/Compose, base model, transactions, DB readiness | MP-25.01, TSD-7.01, context.md §9 | planned |
| A5 | `feat/api-tenancy-rls` | Organisation, Workspace, RLS policies, isolation tests | MP-10.01, MPS-28.08, TSD-22.02/22.03 | planned |

### Progress log

- **A1 — 2026-10-14** — `services/api` package (`relyxus_api`).
  - **Settings:** `RELYXUS_ENVIRONMENT` and `RELYXUS_PUBLIC_BASE_URL` are required; the app refuses to start without them.
  - **Factory:** `create_app` / `build_app` (uvicorn `--factory`).
  - **Health module** (controller → service): liveness never checks dependencies; readiness aggregates dependency probes and returns 503 when any fails.
  - **Docs:** `/docs` and `/docs.json` are served outside production and return 404 in production.
  - **Contract:** OpenAPI 3.1 exported to `packages/schemas/openapi/relyxus-api.openapi.json`, with a drift test.
  - Test client uses `httpx2` (Starlette 1.8 deprecates `httpx`).

  **Results:** ruff, mypy strict, pytest 174 passed. Manual uvicorn run: `/health` 200, `/ready` 200, `/docs` 200; startup without the base URL fails fast.

- **A2 — 2026-10-14** — Errors and observability.
  - **Typed errors:** `AppError` hierarchy, one class per MP-34.01 category: validation 422, authentication 401, permission 403, policy denial 403, licence problem 403, not found 404, conflict 409, dependency unavailable 503, internal 500. Features subclass these with their own stable `code`.
  - **One global handler** turns every failure into RFC 9457 `application/problem+json`. The body has a URN `type`, `code`, `correlation_id` and `instance`, plus per-field `errors` for validation. It never includes input values, stack traces or SQL.
  - **Framework errors** are covered too: unknown routes, wrong methods and unexpected exceptions also return problem details.
  - **Correlation ID middleware** (pure ASGI): accepts a safe caller ID or mints a UUID, echoes `X-Correlation-Id`, and logs method, path, status and duration only, never query strings, headers or bodies.
  - **Logging:** JSON formatter; the correlation ID is stamped when the log record is created.
  - **Contract:** OpenAPI documents 422/500 problem responses; version 0.2.0.
  - **Tooling:** Ruff `max-args=6`; mypy excludes `conftest.py`, since two same-named modules can't be checked in one run.

  **Results:** ruff, mypy strict (49 files), pytest 192 passed.

- **A3 — 2026-10-14** — Lists and pagination.
  - **List envelope:** `ListEnvelope[T]` is `{success, data, meta: {next_cursor, limit}}`, deliberately with no `total`.
  - **`PageRequestDependency`:** `?cursor=&limit=`, default 20, 1–100 enforced, cursor at most 512 characters.
  - **Opaque versioned cursor** (base64url JSON of the last item's sort-key position). A tampered or foreign cursor returns 422 `INVALID_CURSOR`. A test caught a cursor shape that would have crashed with a 500; it's fixed.
  - **`build_page`:** keyset paging from `limit + 1` fetched rows.
  - **Requirements covered:** MPS-22A.04 (cursor pagination), MPS-15.07 (no counts), context.md §5 (bounded lists, capped limit).

  **Results:** ruff, mypy strict (51 files), pytest 207 passed.

---

## Feature F-ACP-LIC — Licence issuance (Apporine Control Plane)

Status: **blocked** on Q-34 (repo placement, MP-37.01) and the missing Admin Control Plane Spec v1.0 (Q-05).
Covers LIC-3.01, LIC-4.x, LIC-6.01/6.02/6.05/6.06, LIC-7.01, LIC-8.01, LIC-9.x, LIC-14.01, LIC-15.01, LIC-16.01, LIC-17.01, LIC-18.01, LIC-19.05, LIC-19.06.

---

## Other features

Not started. Feature breakdown (step 3) waits on the remaining blocking questions in register section E.

- **2026-10-14 — CI and merges** — Actions only started after the workflow scope fix; required checks `lint, types, tests` and `secret scan` set on `develop` (repo made public). PRs #1–#6 squash-merged in order, each after green checks (#1 docs-only merged with admin bypass, as instructed).
- **PR 7 — 2026-10-14** — `apporine_licensing.key_set_document`: closed, versioned trusted key-set file (`key_id`, `environment`, `algorithm`, UTC signing window, public PEM), loader returning `TrustedKeySet`, all failures as `KeySetConfigurationError`; schema `trusted-key-set.v1.schema.json`; ADR-0002 §5.1. **Covered:** LIC-6.04 (versioned key set with key IDs), DEP-23.01 (key material shipped as data, not code), TSD-23.04. **Results:** ruff, mypy strict, pytest 177 passed.
