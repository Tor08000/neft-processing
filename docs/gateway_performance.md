# Gateway performance and resilience updates (v0.1.2)

## What changed
- Enabled gzip compression for common text, JSON, font, and SVG responses to reduce bandwidth for SPA assets and API responses.
- Added long-lived `Cache-Control` headers for hashed admin SPA static assets while keeping the SPA entrypoint (`/admin/`) non-cacheable.
- Applied consistent proxy timeouts to improve backend resilience (connect, send, read, and send timeouts).
- Documented a production-ready HTTP/2 + TLS server block example (kept disabled for local development).

## How to verify locally
1. Start the stack (e.g., `docker-compose up gateway`).
2. Check gzip and SPA entrypoint caching:
   - `curl -I http://localhost/admin/`
     - Expect `Cache-Control: no-store` and (when applicable) `Content-Encoding: gzip`.
3. Check asset caching and gzip:
   - `curl -I http://localhost/admin/assets/<asset-name>`
     - Expect `Cache-Control: public, max-age=31536000, immutable` and `Content-Encoding: gzip`.
4. Validate Nginx config syntax:
   - `docker build -t neft-gateway-test -f services/gateway/Dockerfile .`
   - During the build, `nginx -t` should pass without errors.
