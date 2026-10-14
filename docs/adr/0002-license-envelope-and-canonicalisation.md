# ADR-0002: Licence envelope, canonicalisation and offline verification

- **Status:** Proposed — accepted provisionally for implementation (2026-10-14). Items marked **[confirm]** need Apporine security sign-off (register Q-07b, Q-32, Q-33).
- **Requirements:** LIC-5.01–5.04, LIC-6.03, LIC-6.04, LIC-7.02–7.07, LIC-12.01, LIC-12.02, LIC-19.01, LIC-19.02; MPS-29.05–29.08, MPS-29.15–29.17; TSD-23.04, TSD-23.07, TSD-23.10, TSD-23.11, TSD-23.14; DEP-23.01, DEP-23.08.
- **Why an ADR:** LIC §20 phase 1 requires "ADR for signing envelope/canonicalization". TSD-23.10 requires the algorithm and key size to be versioned in the schema/ADR.

## 1. Artifact: signed envelope (`relyxus.license`)

The artifact is a UTF-8 JSON document with exactly these members; unknown members are rejected:

```json
{
  "envelope_version": 1,
  "algorithm": "ECDSA_P256_SHA256",
  "key_id": "apporine-license-prod-2026-10",
  "payload": "<base64url, unpadded, of the canonical payload bytes>",
  "signature": "<base64url, unpadded, of the DER-encoded ECDSA signature>"
}
```

- **Detached bytes.** The signature covers the exact decoded `payload` bytes. The verifier never re-serialises before checking the signature, so serialisation differences cannot change what was signed.
- **Canonical form required.** After the signature checks out, the payload bytes must already be in canonical form (section 2). If they aren't, the artifact is rejected, so one licence has exactly one valid byte representation.
- **Strict base64url.** Padding, whitespace and non-alphabet characters are rejected. Re-encoding the decoded bytes must reproduce the input exactly.
- **Size cap.** Artifacts above a configurable size cap are rejected before parsing (default 64 KiB).

## 2. Canonicalisation: RFC 8785 (JCS), restricted subset

- Objects with string keys, arrays, strings, booleans and `null`; numbers only as integers within ±(2^53 − 1).
- **Floats, NaN and Infinity are rejected,** not approximated. Payload fields never need them (LIC-5.03: the representation is "locked by schema and tests, not ad-hoc serialisation").
- **Keys are sorted by UTF-16 code units, and strings are escaped exactly as RFC 8785 §3.2.2.2.** Duplicate keys and invalid UTF-8 are rejected on parse.
- **Golden vectors** in `packages/licensing/tests/` lock the behaviour (LIC-19.01).

## 3. Signature algorithm **[confirm, Q-32]**

`ECDSA_P256_SHA256`: AWS KMS key spec `ECC_NIST_P256`, signing algorithm `ECDSA_SHA_256`, `MessageType=RAW`, DER signature as returned by KMS (LIC-6.01, MPS-29.15).

- The verifier accepts only algorithms in its supported set; anything else fails closed (MPS-29.17, TSD-23.11).
- The algorithm is named in the envelope, so a later ADR can add another algorithm (e.g. Ed25519 or ML-DSA) without changing envelope version 1 semantics.

## 4. Payload schema v1

| Field | Type / rule | Source |
|---|---|---|
| `schema_version` | integer, must be `1` | LIC-5.02 |
| `license_id` | UUID string | LIC-5.02, MPS-29.06 |
| `revision` | integer ≥ 1 | LIC-5.02 |
| `customer_id` | UUID string | LIC-5.02 |
| `product_id` | lowercase slug, e.g. `relyxus` | LIC-5.02, MP-19.01 |
| `deployment_bindings` | non-empty list of `{deployment_id, allowance}`; `allowance` ∈ `production`, `non_production`, `disaster_recovery`; IDs unique | LIC-12.01, LIC-12.02 |
| `issued_at`, `not_before`, `expires_at` | UTC timestamp `YYYY-MM-DDTHH:MM:SSZ`; `issued_at ≤ expires_at`, `not_before < expires_at` | LIC-5.02, MPS-14.24 |
| `grace_policy_id` | ID from the grace-policy registry (section 7) | LIC-5.02 |
| `entitlements` | sorted, unique list of keys namespaced by product, e.g. `relyxus.premium_connectors` | LIC-13.02, MP-19.01 |
| `limits` | map of namespaced key → integer ≥ 0 | LIC-13.03 |
| `support_tier` | `standard`, `premium`, `enterprise` | LIC-13.04 |

- `key_id` and `signature` live in the envelope, not the payload (LIC-5.02 lists them as artifact fields).
- No field may carry secrets (LIC-5.04). The closed schema (`additionalProperties: false`) prevents adding free-form fields.
- Customer display names are not in the payload (MPS-29.06).

## 5. Trusted key set **[confirm, Q-33]**

The verifier receives a `TrustedKeySet` from its caller and never discovers keys itself. Each key has:
- `key_id`
- `environment` (`production`, `staging` or `development`)
- `algorithm`
- the public key
- `valid_from` / optional `valid_until`: the window in which that key may have *issued* licences

Rules:
- A licence is trusted only if its `key_id` is in the set and the key's environment equals the verifier's configured environment. Non-production keys therefore never verify production licences (LIC-6.03).
- Several keys may be present at once, which gives the rotation overlap (LIC-6.04, MPS-29.16).
- A licence whose `issued_at` falls outside the key's window is rejected.
- **Proposed runtime rule (built in PR 9):** the running Relyxus builds the key set from keys embedded in the signed release. `public-keys/*.pem` in the install kit is for inspection only, so a customer cannot add a key of their own.

### 5.1 Key-set document v1 (added 2026-10-14)

Keys are loaded from a JSON document (schema `packages/schemas/licensing/trusted-key-set.v1.schema.json`):

```json
{
  "key_set_version": 1,
  "keys": [
    {
      "key_id": "apporine-license-prod-2026-10",
      "environment": "production",
      "algorithm": "ECDSA_P256_SHA256",
      "valid_from": "2026-10-01T00:00:00Z",
      "valid_until": null,
      "public_key_pem": "-----BEGIN PUBLIC KEY-----
..."
    }
  ]
}
```

- **Closed schema.** Unknown members are rejected, as are unknown versions, empty key lists, duplicate key IDs, non-P-256 keys and private-key PEM. Every one of these failures is a `KeySetConfigurationError`: a deployment fault, distinct from a bad licence.
- **Where the file comes from.** It is what Apporine publishes alongside the plain `public-keys/*.pem` files (DEP-23.01) and what the runtime embeds (Q-33).

## 6. Verification order (fail closed until state evaluation)

1. Size cap → strict JSON parse of envelope → envelope version → algorithm supported.
2. Key lookup → key environment matches → ECDSA verify over payload bytes.
3. Payload strict parse → canonical form → `schema_version` supported → schema validation.
4. `product_id`, `customer_id` and local `deployment_id` match the installation (MPS-29.17).
5. `issued_at` inside the key's validity window.
6. `not_before` ≤ now + clock-skew tolerance (default 5 minutes, configurable).
7. State evaluation (section 7) — never an error.

Any failure in steps 1–6 raises a typed error with a stable code. Invalid signatures fail closed. Commercial expiry fails safe: it is a state, never an exception (DEP-23.08, MPS-29.04).

## 7. State evaluation and grace policies **[confirm, Q-07b]**

Offline the verifier can compute these LIC §7 states:
- **Active:** now ≤ `expires_at`.
- **Grace:** `expires_at` < now ≤ `expires_at` + grace period.
- **Expired:** after that.

Other states have other sources:
- **Draft** never reaches a customer.
- **Suspended** and **Revoked** come only from signed status refresh in connected mode (PR 10).
- **Superseded** is assigned by the local licence store when a newer revision is installed (PR 8).

Grace policies are a versioned registry in the library. v1 contains `standard-30d` = 30 days (the MPS-6A.11 default). An unknown `grace_policy_id` is rejected as unsupported.

What each state *restricts* is decided by the runtime, not the verifier, and is still open (Q-07a).

## 8. Explicitly out of scope here

Issuer, entitlement service and KMS signing (Apporine Control Plane, Q-34); licence store and downgrade/replay protection (PR 8); connected refresh (PR 10).

## Consequences

- One canonical byte form per licence makes tampering detectable and golden vectors stable.
- The issuer (Control Plane) must emit exactly this canonical form. The shared `canonical_json` module and JSON Schemas are the contract for it.
