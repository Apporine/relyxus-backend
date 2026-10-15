# ADR-0004: Incident lifecycle states and transitions (Ph0)

- **Status:** Accepted provisionally (2026-10-15). Cancelled-from states follow MPS-8A.15 table text ("any open state") until Q-11 (a) is resolved.
- **Requirements:** MPS-8A.07–8A.16, MPS-8A.22; MPS-23.05 (Ph0 incident model).

## States

| State | Role |
|---|---|
| `triage` | Exists but not yet declared (auto-grouped alerts, declare draft). |
| `investigating` | Declared; active investigation. |
| `mitigating` | Mitigation in progress. |
| `monitoring` | Impact mitigated; watching for regression. |
| `resolved` | Impact normal; post-incident work may continue. |
| `closed` | Terminal; review complete. |
| `cancelled` | Terminal; false alarm / duplicate. |
| `merged` | Terminal; absorbed into another incident. |

## Allowed transitions (server-enforced)

- `triage` → `investigating` (declare)
- `investigating` → `mitigating`
- `mitigating` → `monitoring`
- `monitoring` → `resolved` | `mitigating` (fix did not hold)
- `resolved` → `closed` | `investigating` (reopen)
- Any **open** state (`triage` … `resolved`) → `cancelled` | `merged`

Terminal states admit no further lifecycle transitions.

## Implementation

- Pure functions in `relyxus_api.modules.incident.lifecycle` (`validate_lifecycle_transition`).
- HTTP declare/transition endpoints and audit hooks come in follow-up PRs; the database stores `lifecycle_state` with CHECK constraints matching this ADR.

## Addendum (2026-10-15, I3): transitions API

- **Prerequisites not yet enforceable.** "A working hypothesis or action recorded" (8A.09), "mitigation action recorded" (8A.10) and "impact back to normal for the watch period" (8A.11) depend on records that do not exist yet. Roles and the lifecycle graph are enforced now; these checks arrive with the Brain, actions and the impact model.
- **Closing is refused** (409 `INCIDENT_REVIEW_REQUIRED`) until post-incident review sign-off exists (8A.12, MPS-13.17).
- **Inconsistency for Q-11(a).** The table above lists `resolved` as open (so it could be cancelled or merged), but `validate_lifecycle_transition` allows only `resolved → closed | investigating`. The validator is what runs. Resolve with Q-11(a).

## Addendum (2026-10-15, I18): closure gate

- **Closing is now possible** and supersedes the I3 refusal above. Resolved → Closed is decided by the post-incident review owner (8A.12), or a workspace owner, not by a workspace role.
- **Gates, in order:**
  1. The review is approved or published, so its required reviewers have signed off.
  2. No live task is still open, in progress or blocked.
  3. SEV1/SEV2 only: every unfinished mandatory follow-up has an owner and a due date.
  4. SEV1/SEV2 only: a `root_cause` is given (MPS-13.04, MPS-13.17).
- **Exception:** a workspace owner may record a `closure_exception_reason` that skips gates 1–3 but not the root cause. Gate 2 and who may grant exceptions are provisional (register Q-39).
- **Effects:** closing sets `closed_at`, `closed_by_user_id` and `root_cause`, and moves an approved or published review to `closed` (the report lock). Analytics and report locking beyond the review wait for those features.
