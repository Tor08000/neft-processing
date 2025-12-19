# Admin Web Runbook

## Local development

```bash
cd frontends/admin-ui
npm install
npm run dev
```

The dev server runs on port 8080 (see `vite.config.ts`).

## Production build

```bash
cd frontends/admin-ui
npm run build
```

The build output is written to `dist/` and served by nginx in the Docker image described in `frontends/admin-ui/Dockerfile`.

## Docker image

```
docker build -t neft-admin-web -f frontends/admin-ui/Dockerfile .
```

The image bundles the Vite production build into nginx. Runtime configuration for the API endpoint is read from `VITE_API_BASE_URL` (gateway origin, e.g. `http://gateway`), while the base path is fixed via `BASE_URL=/admin/` from `vite.config.ts`.
