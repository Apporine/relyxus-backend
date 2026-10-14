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
| Q-30 | Local branches only; nothing pushed, no PRs opened on GitHub until you say so | this file |
| Q-31 | `important/` (confidential source documents) git-ignored, not committed | ADR-0001 |
| Q-32 | Licence signature ECDSA P-256 / SHA-256 (AWS KMS `ECDSA_SHA_256`) | ADR-0002 |
| Q-33 | Verifier trusts only a caller-supplied, environment-tagged key set | ADR-0002 |
| Q-07b | Grace policy registry with a single `standard-30d` policy; unknown IDs rejected | ADR-0002 |

Still open and **not** assumed: Q-01, Q-02, Q-03 (no HTTP endpoints built yet), Q-07a (which operations Grace/Expired restrict), Q-08 (Relyxus entitlement catalogue), Q-11, Q-16, Q-18, Q-19, Q-34.

---

## Feature F-LIC — Commercial licence verification (Relyxus side)

**Scope:** schema, signed envelope, canonicalisation and the offline local verifier library that Relyxus and the `relyxus` CLI use. The issuer, entitlement service, KMS signing and admin screens are Apporine Control Plane work (system B), tracked separately as F-ACP-LIC.

**Requirement coverage target:** LIC-1.02, LIC-2.03, LIC-2.04, LIC-2.05, LIC-5.01–5.04, LIC-6.03, LIC-6.04, LIC-7.02–7.04, LIC-12.01, LIC-12.02, LIC-13.01–13.05 (model only), LIC-17.02 (forgery, wrong-customer, downgrade at verify time), LIC-19.01, LIC-19.02, LIC-19.07; MPS-29.01–29.08, MPS-29.11, MPS-29.15–29.17, MPS-29.20 (verifier parts); TSD-23.04, TSD-23.07, TSD-23.11, TSD-23.14; DEP-23.08 (verifier fixtures); MP-13.01, MP-14.01, MP-16.01, MP-19.01.

| # | PR / branch | Scope | Requirement IDs | Status |
|---|---|---|---|---|
| 1 | `docs/requirements-register` | Requirements register + this tracker | (all — traceability) | in review |
| 2 | `chore/python-workspace-foundation` | uv workspace, Python 3.13, Ruff, mypy, pytest, pre-commit, CI, ADR-0001 | MPS-17.07, MPS-22.19, TSD-6.01, TSD-12.01, TSD-14.02, MP-38.01 | planned |
| 3 | `feat/license-canonical-json` | ADR-0002, RFC 8785 canonical JSON, golden vectors | LIC-5.03, LIC-19.01, TSD-23.11 | planned |
| 4 | `feat/license-payload-schema` | Payload/envelope models, typed errors, exported JSON Schemas + drift test | LIC-5.01, LIC-5.02, LIC-5.04, LIC-12.01, LIC-12.02, MPS-29.05, MPS-29.06, MP-19.01 | planned |
| 5 | `feat/license-signature-verification` | Key set, base64url, ECDSA verify, golden signature vector | LIC-6.03, LIC-6.04, MPS-29.15–29.17, TSD-23.04, TSD-23.07 | planned |
| 6 | `feat/license-verifier` | Verification pipeline, binding checks, state evaluation (Active/Grace/Expired), grace registry, entitlement access, exhaustive tests | LIC-2.05, LIC-7.02–7.04, LIC-13.x, LIC-19.02, TSD-23.14, MPS-29.04, MPS-29.08, MPS-29.20 | planned |
| 7 | `feat/license-cli-inspect-verify` | `relyxus license inspect|verify` | LIC-15.03, DEP-23.02 | planned |
| 8 | `feat/license-store` | install/replace/status, Superseded history, downgrade/replay protection (needs DB foundation) | LIC-7.07, LIC-12.03, LIC-17.02, DEP-23.07 | blocked (DB foundation) |
| 9 | `feat/license-runtime-integration` | Startup + periodic verification, embedded key pinning, safe degradation | LIC-10.01, MPS-6A.11, MPS-29.04 | blocked (Q-07a, Q-33) |
| 10 | `feat/license-connected-refresh` | Outbound signed status client, cache, outage handling | LIC-9.03, LIC-10.02, LIC-10.03, LIC-19.03 | planned (Licensing phase 5) |
| 11 | `feat/license-airgap-import` | Offline import/renewal tooling | LIC-11.02, LIC-19.04 | planned (Licensing phase 6) |

### Progress log

_Each entry: PR number, date, what changed, requirement IDs covered, test/lint results as actually run._

- **PR 1 — 2026-10-14** — Added requirements register (846 + 75 LIC requirements, 33 open questions) and this tracker. No code.

---

## Feature F-ACP-LIC — Licence issuance (Apporine Control Plane)

Status: **blocked** on Q-34 (repo placement, MP-37.01) and the missing Admin Control Plane Spec v1.0 (Q-05).
Covers LIC-3.01, LIC-4.x, LIC-6.01/6.02/6.05/6.06, LIC-7.01, LIC-8.01, LIC-9.x, LIC-14.01, LIC-15.01, LIC-16.01, LIC-17.01, LIC-18.01, LIC-19.05, LIC-19.06.

---

## Other features

Not started. Feature breakdown (step 3) waits on the remaining blocking questions in register section E.
