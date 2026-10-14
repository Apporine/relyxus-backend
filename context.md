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

## 6. API Documentation (Swagger / OpenAPI)

Every endpoint is documented. An undocumented endpoint is an incomplete endpoint.

**Rules**
- OpenAPI 3.x. One spec per service.
- Spec and code stay in sync — generate the spec from code annotations/schemas, or generate validation from the spec. Never maintain both by hand.
- Document for each endpoint: summary, params, request body, every response code, auth requirement.
- Define reusable `components/schemas` for models and errors. Do not inline the same shape twice.
- Include the standard success and error envelopes as shared schemas.
- Realistic examples on every schema — no `"string"` placeholders.
- Group endpoints with `tags` per module.
- Bump the spec `version` on every contract change.

**Routes**
```
/docs        → Swagger UI
/docs.json   → raw OpenAPI spec
```
- Enabled in local and staging. In production: disabled, or behind auth — never public.
- Add a server entry per environment and configure the auth scheme so "Try it out" works.

**Node / Express**
```js
// shared/config/swagger.js
import swaggerUi from 'swagger-ui-express';
import swaggerJsdoc from 'swagger-jsdoc';

const spec = swaggerJsdoc({
  definition: {
    openapi: '3.0.3',
    info: { title: 'API', version: '1.0.0' },
    servers: [{ url: process.env.API_URL }],
    components: {
      securitySchemes: {
        bearerAuth: { type: 'http', scheme: 'bearer', bearerFormat: 'JWT' },
      },
    },
    security: [{ bearerAuth: [] }],
  },
  apis: ['./src/modules/**/*.controller.js'],
});

export function mountDocs(app) {
  if (process.env.NODE_ENV === 'production') return;
  app.use('/docs', swaggerUi.serve, swaggerUi.setup(spec));
  app.get('/docs.json', (_req, res) => res.json(spec));
}
```

**Spring Boot (springdoc-openapi)**
```java
@Configuration
public class SwaggerConfig {
  @Bean
  public OpenAPI api() {
    return new OpenAPI()
      .info(new Info().title("API").version("1.0.0"))
      .addSecurityItem(new SecurityRequirement().addList("bearerAuth"))
      .components(new Components().addSecuritySchemes("bearerAuth",
        new SecurityScheme().type(SecurityScheme.Type.HTTP)
          .scheme("bearer").bearerFormat("JWT")));
  }
}
```
```yaml
# application.yml
springdoc:
  swagger-ui.path: /docs
  api-docs.path: /docs.json
  swagger-ui.enabled: ${SWAGGER_ENABLED:true}
```
Annotate controllers with `@Tag`, `@Operation`, `@ApiResponse`, `@Schema`.

**Checks**
- Spec must build in CI. A broken spec fails the pipeline.
- New endpoint without documentation → review rejection.

---

## 7. Validation

- Validate every request at the edge with a schema (Zod / Joi / Bean Validation / Pydantic).
- Invalid input never reaches the service layer.
- Validate type, length, range, format, and allowed values.
- Reject unknown fields.
- Never trust client-sent `role`, `price`, `userId`, or `isAdmin`.

---

## 8. Error Handling

- One global error handler. Controllers do not contain try/catch for responses.
- Throw typed errors: `NotFoundError`, `ValidationError`, `ConflictError`, `UnauthorizedError`.
- Every error has a stable machine-readable `code`.
- Never leak stack traces, SQL, or internal paths to the client.
- Never swallow an error silently. Log it or throw it.

---

## 9. Database

- All schema changes via versioned migrations. No manual changes to any environment.
- Migrations are forward-only and reviewed like code.
- Index every foreign key and every column used in `WHERE`, `ORDER BY`, or `JOIN`.
- Use transactions for any multi-write operation.
- Parameterised queries only. String-concatenated SQL is a hard reject.
- Watch for N+1 queries. Batch or join.
- Soft delete (`deleted_at`) where history matters; hard delete where it doesn't.
- Every table: `id`, `created_at`, `updated_at`.

---

## 10. Security

- Secrets in environment variables. Never in the repo. `.env` is gitignored; `.env.example` is committed.
- Authenticate at middleware; authorise in the service layer.
- Check ownership on every resource access — not just that the user is logged in.
- Hash passwords with bcrypt or argon2. Never MD5/SHA.
- Rate limit auth endpoints and any expensive route.
- Enforce HTTPS. Set security headers. Restrict CORS to known origins.
- Never log passwords, tokens, card data, or full PII.
- Keep dependencies patched.

---

## 11. Configuration

- Load and validate all config at startup. Crash immediately on a missing required variable.
- No hardcoded URLs, ports, keys, or limits anywhere in the code.
- Same build artifact runs in every environment; only config differs.

---

## 12. Logging & Observability

- Structured JSON logs. No `print` / `console.log` in committed code.
- Levels: `error` (needs action), `warn` (unexpected, handled), `info` (lifecycle), `debug` (local only).
- Attach a request ID to every log line and pass it through all layers.
- Expose `/health` (liveness) and `/ready` (dependencies reachable).

---

## 13. Testing

- Unit tests for services — mock the repository.
- Integration tests for repositories — use a real test database.
- API tests for each endpoint — happy path plus failure cases.
- Test behaviour, not implementation details.
- A bug fix ships with a test that reproduces the bug.
- No test depends on another test or on run order.

---

## 14. Git Workflow

**Branches**
```
main      → production. Protected. Release merges only.
develop   → integration branch. Protected. All feature work lands here.
feat/*    → new work, cut from develop
fix/*     → bug fix, cut from develop
hotfix/*  → urgent production fix, cut from main
```

**Cycle — every change follows this. No exceptions.**

1. Pull the latest `develop`.
2. Cut a branch from it: `feat/user-invite`, `fix/token-expiry`, `chore/upgrade-orm`. One branch per ticket.
3. Commit in small logical units as you work.
4. Rebase on `develop` before raising the PR so the branch is current.
5. Push and raise a PR into `develop`. Never into `main`.
6. PR must describe what changed, why, and how it was tested. Link the ticket.
7. CI must be green and at least one review approved.
8. Address review comments with new commits, not a force-push that wipes the thread.
9. Squash merge into `develop`. Delete the branch after merge.
10. `develop` → `main` only at release, via its own PR.

**Rules**
- Never commit directly to `main` or `develop`.
- Never merge your own PR without a review.
- Keep PRs small — under ~400 changed lines. Split large work into stacked PRs.
- A branch open longer than a few days gets rebased on `develop` daily.
- `hotfix/*` merges into `main`, then is merged back into `develop` immediately so the fix is not lost.

**Commits**
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

**Before merge:** all tests green, no linter warnings, migration included if schema changed, OpenAPI spec updated, no debug code, at least one approving review.

---

## 15. Review Checklist

- [ ] Layer boundaries respected
- [ ] No duplicated logic
- [ ] Input validated at the edge
- [ ] Errors typed and handled centrally
- [ ] No secrets or hardcoded config
- [ ] Authorisation checked, not just authentication
- [ ] Queries indexed, no N+1
- [ ] Tests added
- [ ] API response shape consistent
- [ ] Swagger/OpenAPI updated for new or changed endpoints
- [ ] Branch cut from `develop`, PR targets `develop`
- [ ] Names clear without a comment explaining them

---

## 16. Principles

- Make it work, make it right, make it fast — in that order.
- Explicit beats clever.
- A comment explains *why*, never *what*. If it explains what, rename things instead.
- Delete dead code. Git remembers it.
- Consistency with the existing codebase beats personal preference.