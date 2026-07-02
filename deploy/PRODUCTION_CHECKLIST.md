# MeteoLens production deployment checklist

Use this checklist before exposing a public demo or production instance.

## Legal and attribution

- [ ] Current IMGW-PIB terms reviewed for the intended public or commercial use
  (see `LEGAL_ATTRIBUTION.md` → "Commercial And Public Use").
- [ ] MIT License referenced in deployment notes and repository README.
- [ ] IMGW-PIB attribution visible in the UI and exports.
- [ ] Processed-data notice visible wherever data is normalized or transformed.
- [ ] Known limitations from README remain visible (no hidden data-quality gaps).

## Infrastructure

- [ ] `docker compose -f docker-compose.prod.yml up --build` succeeds on the target host.
- [ ] Frontend is served as static assets (nginx), not the Vite dev server.
- [ ] Backend image built from `backend/Dockerfile.prod` without dev dependencies.
- [ ] Reverse proxy and TLS configured (`deploy/caddy/Caddyfile.example` or equivalent).
- [ ] Production CORS origins set via `METEOLENS_FRONTEND_ORIGIN` (comma-separated if needed).
- [ ] Persistent volume mounted at `/data` for SQLite and IMGW cache.
- [ ] `restart: unless-stopped` policies active for backend and frontend services.
- [ ] Backups planned for `/data` (database + cache metadata).

## IMGW access discipline

- [ ] Refresh intervals match `METEOLENS_REFRESH_*` defaults or documented overrides.
- [ ] Timeout/retry/backoff configured via `METEOLENS_IMGW_*` settings.
- [ ] Stale cache and source failures remain visible in `/api/v1/sources`.
- [ ] No direct IMGW calls from the browser.

## Observability

- [ ] `/health` monitored for liveness.
- [ ] `/api/v1/sources` monitored for cache freshness and parser errors.
- [ ] Container logs reviewed for `meteolens.source` fetch outcomes.
- [ ] API errors logged under `meteolens.api` with path and error code.

## Demo media

- [ ] README screenshots captured from a populated real cache (not mock data).
- [ ] Screenshots include attribution and processed-data notice where applicable.

## Commands

Local production smoke test:

```bash
cp deploy/.env.production.example .env.production
docker compose --env-file .env.production -f docker-compose.prod.yml up --build
```

Then open `http://localhost:8080` (or your configured `PUBLIC_HTTP_PORT`).
