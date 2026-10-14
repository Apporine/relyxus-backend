# Backend Engineering Context

Rules for this repo. Apply to all backend code and APIs. Keep this file updated when a rule changes.

---

## 1. Layering

Three layers. Dependencies point downward only.

```
Controller / Route   → HTTP only
Service              → business logic
Repository / DAO     → data access
```

- Controller: parse input, call one service, return response. No logic, no SQL.
- Service: all rules, validation, orchestration. No HTTP objects (no request/response types). No raw SQL.
- Repository: queries only. No business rules.
- A layer never calls upward. Repository never imports a service.
- Domain models stay independent of the framework and the database driver.

---

## 2. Project Structure

Group by feature, not by type.

```
src/
  modules/
    user/
      user.controller
      user.service
      user.repository
      user.model
      user.schema        # request/response validation
  shared/
    errors/
    middleware/
    config/
    utils/
    constants/
  db/
    migrations/
    seeds/
```

- Anything used by two or more modules moves to `shared/`.
- A module never imports another module's repository. Go through its service.
- No file over ~300 lines. Split it.

---

## 3. No Duplication

- Same logic in two places → extract to `shared/`.
- Same string in two places → constant.
- Same query shape in two places → one repository method with parameters.
- Copy-paste is a code review rejection.
- Exception: do not abstract until the third occurrence. Two similar things may diverge.

---

## 4. Naming

- Variables and functions: `camelCase`. Classes/types: `PascalCase`. Constants: `UPPER_SNAKE_CASE`. Files: `kebab-case`.
- Booleans start with `is`, `has`, `can`, `should`: `isActive`, `hasAccess`.
- Functions start with a verb: `getUser`, `createOrder`, `validatePayload`.
- No abbreviations except widely known ones (`id`, `url`, `db`).
- No `data`, `info`, `temp`, `obj`, `result2`.
- Name says what it is, not how it works.

---

## 5. REST API Design

**URLs**
- Plural nouns, lowercase, hyphenated: `/api/v1/user-profiles`
- No verbs in paths. `POST /users`, not `/createUser`.
- Nesting max two levels: `/users/{id}/orders`. Deeper → use query params.
- Version in the path: `/api/v1/...`

**Methods**
| Method | Use | Idempotent |
|---|---|---|
| GET | read | yes |
| POST | create | no |
| PUT | full replace | yes |
| PATCH | partial update | no |
| DELETE | remove | yes |

**Status codes**
- `200` ok · `201` created · `204` no content
- `400` bad input · `401` not authenticated · `403` not allowed · `404` not found · `409` conflict · `422` validation failed · `429` rate limited
- `500` server error. Never return 200 with an error inside.

**Response shape** — consistent across every endpoint.

```json
{ "success": true, "data": { }, "meta": { } }
```

```json
{ "success": false, "error": { "code": "USER_NOT_FOUND", "message": "User does not exist" } }
```

**Lists** — always paginate. Never return an unbounded collection.

```
GET /users?page=1&limit=20&sort=-created_at&status=active
```
Return `meta: { page, limit, total, totalPages }`. Cap `limit` (e.g. 100).

**Rules**
- Field names `snake_case` or `camelCase` — pick one, never mix.
- Dates: ISO 8601 UTC (`2026-10-14T07:56:00Z`).
- Money: integer minor units (cents), never float.
- IDs: UUID or ULID in public APIs, never sequential integers.
- Breaking change → new version. Never change an existing contract.

---

## 6. Validation

- Validate every request at the edge with a schema (Zod / Joi / Bean Validation / Pydantic).
- Invalid input never reaches the service layer.
- Validate type, length, range, format, and allowed values.
- Reject unknown fields.
- Never trust client-sent `role`, `price`, `userId`, or `isAdmin`.

---

## 7. Error Handling

- One global error handler. Controllers do not contain try/catch for responses.
- Throw typed errors: `NotFoundError`, `ValidationError`, `ConflictError`, `UnauthorizedError`.
- Every error has a stable machine-readable `code`.
- Never leak stack traces, SQL, or internal paths to the client.
- Never swallow an error silently. Log it or throw it.

---

## 8. Database

- All schema changes via versioned migrations. No manual changes to any environment.
- Migrations are forward-only and reviewed like code.
- Index every foreign key and every column used in `WHERE`, `ORDER BY`, or `JOIN`.
- Use transactions for any multi-write operation.
- Parameterised queries only. String-concatenated SQL is a hard reject.
- Watch for N+1 queries. Batch or join.
- Soft delete (`deleted_at`) where history matters; hard delete where it doesn't.
- Every table: `id`, `created_at`, `updated_at`.

---

## 9. Security

- Secrets in environment variables. Never in the repo. `.env` is gitignored; `.env.example` is committed.
- Authenticate at middleware; authorise in the service layer.
- Check ownership on every resource access — not just that the user is logged in.
- Hash passwords with bcrypt or argon2. Never MD5/SHA.
- Rate limit auth endpoints and any expensive route.
- Enforce HTTPS. Set security headers. Restrict CORS to known origins.
- Never log passwords, tokens, card data, or full PII.
- Keep dependencies patched.

---

## 10. Configuration

- Load and validate all config at startup. Crash immediately on a missing required variable.
- No hardcoded URLs, ports, keys, or limits anywhere in the code.
- Same build artifact runs in every environment; only config differs.

---

## 11. Logging & Observability

- Structured JSON logs. No `print` / `console.log` in committed code.
- Levels: `error` (needs action), `warn` (unexpected, handled), `info` (lifecycle), `debug` (local only).
- Attach a request ID to every log line and pass it through all layers.
- Expose `/health` (liveness) and `/ready` (dependencies reachable).

---

## 12. Testing

- Unit tests for services — mock the repository.
- Integration tests for repositories — use a real test database.
- API tests for each endpoint — happy path plus failure cases.
- Test behaviour, not implementation details.
- A bug fix ships with a test that reproduces the bug.
- No test depends on another test or on run order.

---

## 13. Git & Commits

- Branches: `feat/short-name`, `fix/short-name`, `chore/short-name`.
- Conventional commits: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`.
- Subject under 72 characters, imperative mood: `fix: reject expired refresh tokens`.
- One logical change per commit. Formatting and logic go in separate commits.
- Never commit secrets, `node_modules`, build output, or commented-out code.

**Pre-commit checks (must pass):**
1. Linter
2. Formatter
3. Type check
4. Unit tests
5. Secret scan

**Before merge:** all tests green, no linter warnings, migration included if schema changed, no debug code, at least one approving review.

---

## 14. Review Checklist

- [ ] Layer boundaries respected
- [ ] No duplicated logic
- [ ] Input validated at the edge
- [ ] Errors typed and handled centrally
- [ ] No secrets or hardcoded config
- [ ] Authorisation checked, not just authentication
- [ ] Queries indexed, no N+1
- [ ] Tests added
- [ ] API response shape consistent
- [ ] Names clear without a comment explaining them

---

## 15. Principles

- Make it work, make it right, make it fast — in that order.
- Explicit beats clever.
- A comment explains *why*, never *what*. If it explains what, rename things instead.
- Delete dead code. Git remembers it.
- Consistency with the existing codebase beats personal preference.
