# MaintainerFlow frontend

The frontend is a read-only TypeScript/Vite operations dashboard. It displays the public API and
database readiness probes and links to the OpenAPI schema; it does not receive secrets or write
to GitHub.

```powershell
npm ci --prefix frontend
npm run dev --prefix frontend
```

Vite proxies `/api/*` to `http://localhost:8000` during development. Production Nginx restricts
the proxy to `/api/health`, `/api/ready`, and `/api/openapi.json`. For a different endpoint, set
`VITE_API_BASE_URL` at build time and configure that API's CORS policy. Production uses
`nginx.conf` and the Compose `api` service, so no cross-origin setting is needed.

```powershell
npm run typecheck --prefix frontend
npm test --prefix frontend
npm run build --prefix frontend
```
