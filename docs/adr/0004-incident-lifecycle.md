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
