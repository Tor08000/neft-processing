# Slice 0: Token routing hygiene (Client + Partner + Admin)

## Goal
Ensure every portal sends tokens only via `Authorization: Bearer <token>` and that core-api
verifiers return clean, predictable errors when a token is used against the wrong portal
verifier.

## Behavior changes
- `client_auth.verify`, `partner_auth.verify`, and `admin_auth.verify` now reject tokens
  intended for a different portal with `401` and `reason_code=TOKEN_WRONG_PORTAL`.
- JWKS refresh attempts only happen on signature/key rotation failures, not on issuer/audience
  mismatches.

## Token × endpoint matrix

| Endpoint | Client token | Partner token | Admin token |
| --- | --- | --- | --- |
| `/api/core/client/auth/verify` | 204 | 401 TOKEN_WRONG_PORTAL | 401 TOKEN_WRONG_PORTAL |
| `/api/core/partner/auth/verify` | 401 TOKEN_WRONG_PORTAL | 204 | 401 TOKEN_WRONG_PORTAL |
| `/api/core/admin/auth/verify` | 401 TOKEN_WRONG_PORTAL | 401 TOKEN_WRONG_PORTAL | 204 |

Wrong-portal responses use:

```
{
  "detail": {
    "error": "token_rejected",
    "reason_code": "TOKEN_WRONG_PORTAL",
    "error_id": "<uuid>"
  }
}
```

## Endpoints
- `GET /api/core/client/auth/verify`
- `GET /api/core/partner/auth/verify`
- `GET /api/core/admin/auth/verify`

## Smoke
Run the Windows CMD smoke:

```
scripts\smoke_slice_0_tokens.cmd
```

This script logs into each portal, calls the matching verifier endpoint with the correct token,
asserts that cross-portal token use returns `401 TOKEN_WRONG_PORTAL`, and ends with `ALL PASS`
or a `[FAIL]` line plus the response body for the failing endpoint.
