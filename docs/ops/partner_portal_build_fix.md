# Partner portal build fix (TypeScript)

## Symptoms
- `npm run build` in `frontends/partner-portal` fails with TS2554/TS5076 errors in `src/api/http.ts`.
- `docker compose build partner-web` fails for the same TypeScript errors.

## Cause
- `LegalRequiredError` called `ApiError` with too few constructor arguments after the API helper contract changed.
- Mixed `??` and `||` operators without parentheses in error message fallback logic.

## Fix
- Pass full `ApiError` constructor args from `LegalRequiredError` (including `requestId`/`errorCode` placeholders).
- Add parentheses around the `??` chain before the `||` fallback.

## Verification
```bash
cd frontends/partner-portal
npm run build

docker compose build partner-web
```
