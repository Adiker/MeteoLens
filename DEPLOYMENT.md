# DEPLOYMENT.md - MeteoLens

Stage 2 includes a local Docker Compose deployment for the skeleton app.

## Local Development Target

Command:

```bash
docker compose up --build
```

Services:

- `backend`: FastAPI app.
- `frontend`: Vite dev server.
- SQLite data is mounted through `./data:/data`; no separate database container
  exists in the skeleton.

## Environment

`.env.example` includes:

- `METEOLENS_ENV`,
- `METEOLENS_API_BASE_URL`,
- `METEOLENS_DATABASE_URL`,
- `METEOLENS_CACHE_DIR`,
- `METEOLENS_IMGW_BASE_URL`,
- `METEOLENS_LOG_LEVEL`,
- scheduler intervals for each source.

No secrets are needed for public IMGW-PIB sources.

## Persistence

MVP:

- SQLite database in a persistent volume.
- Raw payload cache in a persistent volume or under `data/cache`.

Post-MVP:

- PostgreSQL/PostGIS for geometry and relational data.
- TimescaleDB for observation history.
- Object storage or mounted volume for large product files.

## Healthchecks

Backend exposes:

- `GET /health` for service liveness.
- `GET /api/v1/sources` for source/cache status.

Docker healthcheck should call `/health`.

## Production Notes

- Put the app behind a reverse proxy with TLS.
- Configure cache/storage retention before enabling large product downloads.
- Monitor IMGW source failures and parser failures.
- Back up the database and any manually downloaded geometry datasets.
- Keep source attribution visible in public deployments.
- Verify current IMGW-PIB terms before public or commercial use.

## Stage 7 Production Target

Stage 7 adds a production deployment path separate from the local development
Docker Compose setup.

### Commands

Local development (Vite dev server + backend):

```bash
docker compose up --build
```

Production smoke test (nginx static frontend + runtime backend image):

```bash
cp deploy/.env.production.example .env.production
docker compose --env-file .env.production -f docker-compose.prod.yml up --build
```

Open `http://localhost:8080` (or the configured `PUBLIC_HTTP_PORT`). The nginx
frontend proxies `/api/*` and `/health` to the backend and serves the Vite build
from `/usr/share/nginx/html`.

### Production assets

- `docker-compose.prod.yml` — production services with restart policies and a
  named volume for `/data`.
- `backend/Dockerfile.prod` — installs runtime dependencies only (no pytest/ruff).
- `frontend/Dockerfile.prod` — multi-stage build + nginx runtime.
- `deploy/nginx/frontend.conf` — static UI, API proxy, SPA fallback.
- `deploy/caddy/Caddyfile.example` — TLS termination example in front of the stack.
- `deploy/.env.production.example` — production environment template.
- `deploy/PRODUCTION_CHECKLIST.md` — public deployment checklist.

### CORS

Set `METEOLENS_FRONTEND_ORIGIN` to the public site origin. Comma-separated values
are supported when the UI and API are served from different hostnames, for example:

```env
METEOLENS_FRONTEND_ORIGIN=https://meteolens.example.com,https://www.meteolens.example.com
```

When nginx serves the UI and proxies `/api` on the same origin, CORS is mainly
relevant for direct backend access during diagnostics.

### IMGW retry and backoff

Configure public-instance fetch discipline through:

- `METEOLENS_REFRESH_*` — scheduler/refresh intervals per source family,
- `METEOLENS_IMGW_TIMEOUT_SECONDS` — HTTP timeout per request,
- `METEOLENS_IMGW_MAX_RETRIES` — retry count for transient 5xx/transport errors,
- `METEOLENS_IMGW_RETRY_DELAY_SECONDS` — delay between retries.

Keep refresh intervals conservative. MeteoLens must not hammer IMGW-PIB public
endpoints.

### Observability

Production logging writes structured single-line records for:

- app startup (`meteolens` logger),
- IMGW source fetch outcomes (`meteolens.source`: source key, URL, status,
  retrieval timestamp, record count, parser warning count),
- API errors (`meteolens.api`: path, status code, error code).

Monitor `/health` for liveness and `/api/v1/sources` for cache freshness,
parser warnings, and stale/error states.

### License and terms

Public deployments must document the MIT License (see repository `LICENSE`) and
verify current IMGW-PIB terms before commercial or high-traffic public use. See
`LEGAL_ATTRIBUTION.md`.

### Demo media

Capture README screenshots from a populated real cache following
`docs/screenshots/README.md`.

Stage 7 public deployment checklist: see `deploy/PRODUCTION_CHECKLIST.md`.

## Stage 10 Product-File Deployment Notes

Large product, radar-like, and GRIB files are not production-ready. Before any
product layer is deployed, Stage 10 must document:

- expected file sizes and retention policy,
- storage location for raw products and generated tiles/rasters,
- cache eviction behavior,
- source retry/backoff behavior for large downloads,
- projection and rendering requirements,
- missing-frame and stale-frame behavior,
- legal/source review outcome for each product family.

## Observability

Minimum logs:

- app startup config summary without secrets,
- source fetch success/failure,
- parser success/failure,
- cache freshness,
- API error responses,
- export generation.

Later:

- Prometheus metrics,
- structured JSON logs,
- source freshness dashboard,
- alerting for repeated source failures.

Stage 7 should define the minimum production log fields for source key, URL,
status, retrieval timestamp, parser version, parser errors, cache freshness, API
error code, and request ID where available.
