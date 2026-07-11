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
  named volume for `/data`. The backend service builds from the repository root
  so the image can include the reviewed `data/geometry/` seed files.
- `backend/Dockerfile.prod` — installs runtime dependencies only (no pytest/ruff)
  and bundles reviewed geometry seeds under `/app/bundled/geometry`.
- `backend/docker-entrypoint.prod.sh` — on first startup, copies the bundled
  reviewed geometry datasets into `/data/geometry`; on later upgrades, merges
  newly bundled dataset entries and files into an existing geometry volume
  without overwriting already registered datasets.
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

In production, a missing, wildcard, or `localhost` frontend-origin setting
produces no CORS allow-list. This is intentional fail-closed behavior; set only
the exact HTTPS browser origins that need direct backend access. MeteoLens does
not use browser credentials, so credentialed CORS is disabled.

### Public-internet security (Stage 19)

Production route categories are public (read-only data, exports, and metadata),
expensive (product renders), and administrative (archive backfill). Archive
backfill is disabled by default. To deliberately enable it, store a high-entropy
`METEOLENS_ADMIN_TOKEN` outside git and supply it in the
`X-MeteoLens-Admin-Token` header. Do not put this value in the frontend or
browser configuration.

The bundled nginx configuration rejects bodies over 64 KB, applies finite
client/proxy timeouts, restricts public API and product-render request rates,
and emits CSP, anti-framing, content-type, referrer, and permissions headers.
Product renders are additionally limited in the backend to one concurrent
render by default and identical simultaneous render requests share the cached
result. Archive imports permit one active run and rate-limit a recently
completed identical range.

Production Compose exposes only nginx; the backend has no host port. The
long-running backend runs as UID/GID 10001 with a read-only root filesystem,
all Linux capabilities dropped, and `no-new-privileges`. `/data` remains the
intentional writable persistent volume. A short-lived `data-init` service seeds
and assigns that volume before the backend starts. The nginx service is also
non-root, read-only, capability-free, and uses a temporary filesystem for its
runtime files.

Logs exclude authorization headers and request query strings. Source and error
logging redacts token-like parameters and signed URL material. Do not add exact
caller coordinates to application logs; use aggregate operational metrics when
location diagnostics are necessary.

### Reviewed geometry data

Production Compose stores runtime state in the `meteolens-data` named volume.
Fresh volumes start empty, so the backend production image bundles the reviewed
geometry files from `data/geometry/` and seeds `/data/geometry` before starting
the API when no manifest is present. Existing volumes keep their local geometry,
but the entrypoint also merges newly bundled reviewed datasets that are missing
from the active manifest. This makes Stage 13 voivodeship/county polygons and
Stage 18 synop station coordinates available across fresh deployments and image
upgrades while preserving any later geometry imported into the volume with
`python -m app.geometry.import_cli`.

Check the active geometry state with:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml exec backend \
  python -m app.geometry.import_cli status --geometry-dir /data/geometry
```

### IMGW retry and backoff

Configure public-instance fetch discipline through:

- `METEOLENS_REFRESH_ENABLED` — enables the in-process periodic refresh
  scheduler (enabled by default in the provided Compose files),
- `METEOLENS_REFRESH_*_SECONDS` — scheduler/refresh intervals per source family,
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
