# ADR-0003: REST API conventions for Relyxus services

- **Status:** Accepted (2026-10-14). The product owner approved the register recommendations for Q-01, Q-02, Q-03, Q-09, Q-15, Q-16, Q-18, Q-19, Q-20, Q-21 and Q-22.
- **Requirements:** MPS-22A.03–22A.10, MP-8.02, MP-9.01, MP-9.03, MP-10.01, MP-34.01; context.md §5–§9.

## Decisions

### 1. Success and error shapes (Q-01)

- **Success:** `{"success": true, "data": …, "meta": {…}}`, the shared envelope from context.md §5. `meta` is present only on lists.
- **Errors:** RFC 9457 problem details, served as `application/problem+json`:

  ```json
  {
    "type": "https://errors.relyxus.io/incident-not-found",
    "title": "Incident not found",
    "status": 404,
    "detail": "No incident with this ID is visible to you.",
    "instance": "/api/v1/incidents/0192…",
    "code": "INCIDENT_NOT_FOUND",
    "correlation_id": "0192f0c4-…"
  }
  ```

  `code` is the stable machine-readable code that context.md §8 requires. `correlation_id` satisfies MPS-22A.04.
- Errors never use the success envelope, and a 2xx response never carries an error.

### 2. Pagination (Q-02)

- Cursor pagination only: `?cursor=<opaque>&limit=<1..100>` (default 20).
- Response `meta`: `{ "next_cursor": "<opaque>|null", "limit": 20 }`.
- **No `total`.** A count computed before permission filtering could reveal restricted incidents (MPS-15.07).

### 3. OpenAPI source of truth (Q-03)

- **Code first.** FastAPI/Pydantic models are the source. The contract is exported to `packages/schemas/openapi/relyxus-api.openapi.json` (OpenAPI 3.1) by `python -m relyxus_api.openapi_export`.
- A test fails when the committed file differs from the app, so every contract change appears as a reviewed diff in its PR. This satisfies context.md §6 ("never maintain both by hand").
- This departs from MPS-22A.03's "written in the OpenAPI file before code"; the owner accepted that departure.
- `/docs` (Swagger UI) and `/docs.json` are served in local, development and staging; they are disabled in production.
- `info.version` is bumped on every contract change.

### 4. Paths, casing, identifiers (Q-15, Q-21, Q-22)

- **Paths:** `/api/v1/<plural-kebab-noun>`, nested at most two levels. Probes are at `/health` and `/ready`, outside the version prefix.
- **JSON casing:** field names are `snake_case`. Timestamps are UTC ISO 8601; money is an integer amount in minor units plus an ISO 4217 currency code.
- **Workspace context:** sent in the `X-Relyxus-Workspace-Id` header and always verified against the caller's memberships, never trusted on its own (MP-10.01).
- **IDs:** public IDs are UUIDv7. Human display numbers (`INC-1042`) are not identifiers and are never accepted as lookup keys.

### 5. Safe writes and limits (MPS-22A.05/22A.06)

- Create and action requests accept `Idempotency-Key`.
- Updates use `ETag` / `If-Match` (412 on mismatch).
- Rate limits return 429 with `Retry-After`.

These are implemented with the first endpoints that need them.

### 6. Data and tenancy (Q-09, Q-18, Q-19, Q-20)

- **Migrations:** forward-only in shared environments, using expand/contract so the previous release keeps working.
- **Tenancy columns:** `organization_id` on every tenant table; `workspace_id` on workspace-scoped tables. PostgreSQL RLS enforces both.
- **Roles:** granted to a user per workspace and to teams. A user's effective permissions are the union of the two, and conditions are evaluated in OPA.
- **Hash chains:**
  - The audit log and the evidence ledger are separate chains, each scoped per workspace.
  - Records that belong to an organisation rather than a workspace get their own organisation-level audit chain.
  - Each entry's hash is SHA-256 over its RFC 8785 canonical JSON.

### 7. Identity (Q-16)

- The API accepts only OIDC access tokens issued by Keycloak.
- Email sign-in uses Keycloak local accounts. Google and other IdPs are federated through Keycloak.
- Relyxus never stores passwords.

## Consequences

- Clients get one success shape and one standard error format with stable codes.
- The frontend generates its client from the exported contract.
- Any endpoint change without a regenerated contract fails CI.
