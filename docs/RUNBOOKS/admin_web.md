# Admin Web Runbook

## Local development

```bash
cd services/admin-web
npm install
npm run dev
```

The dev server runs on port 8080 (see `vite.config.ts`).

## Production build

```bash
cd services/admin-web
npm run build
```

The build output is written to `dist/` and served by nginx in the Docker image described in `services/admin-web/Dockerfile`.

## Docker image

```
docker build -t neft-admin-web services/admin-web
```

The image bundles the Vite production build into nginx. Runtime configuration for the API endpoint is read from `VITE_API_BASE_URL` (defaults to `/api/v1`).
