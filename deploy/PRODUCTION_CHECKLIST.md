# MeteoLens production deployment checklist

Use this checklist before exposing a public demo or production instance. The
boxes are intentionally unchecked: complete them per deployment on the target
host. A historical smoke-test run is recorded in
`docs/release/SMOKE_TEST_2026-07-03.md`, but unrestricted public deployment now
requires the Stage 19-21 hardening and validation plan in
`docs/release/PUBLIC_ALPHA_HARDENING_PLAN.md`.

## Legal and attribution

- [ ] Current IMGW-PIB terms reviewed for the intended public or commercial use
  (see `LEGAL_ATTRIBUTION.md` → "Commercial And Public Use").
- [ ] MIT License referenced in deployment notes and repository README.
- [ ] IMGW-PIB attribution visible in the UI and exports.
- [ ] Processed-data notice visible wherever data is normalized or transformed.
- [ ] Known limitations from README remain visible (no hidden data-quality gaps).

## Infrastructure

- [ ] Local development smoke test recorded with `docker compose up --build`,
  `/health`, `/api/v1/sources`, frontend map load, station details, warning
  details/list, exports, expert panel, and timeline shell.
- [ ] `docker compose -f docker-compose.prod.yml up --build` succeeds on the target host.
- [ ] Production smoke test recorded with
  `docker compose --env-file .env.production -f docker-compose.prod.yml up --build`.
- [ ] Configured public HTTP port opens during the production smoke test.
- [ ] Frontend is served as static assets (nginx), not the Vite dev server.
- [ ] Backend image built from `backend/Dockerfile.prod` without dev dependencies.
- [ ] Reverse proxy and TLS configured (`deploy/caddy/Caddyfile.example` or equivalent).
- [ ] Production CORS origins set via `METEOLENS_FRONTEND_ORIGIN` (comma-separated if needed).
- [ ] Persistent volume mounted at `/data` for SQLite and IMGW cache.
- [ ] `restart: unless-stopped` policies active for backend and frontend services.
- [ ] Fresh named-volume startup tested.
- [ ] Upgrade from an existing pre-Stage-18 volume tested.

## Endpoint protection and abuse limits

- [ ] API routes classified as public, expensive, or administrative.
- [ ] Administrative archive-backfill routes disabled by default or protected by
  admin authentication in public deployments.
- [ ] Public per-IP request rate limits configured.
- [ ] Lower public limits configured for product render routes.
- [ ] Product downloads, renders, and archive imports have concurrency limits.
- [ ] Repeated render requests serve cached PNGs where possible and cannot force
  repeated approximately 160 MB downloads.
- [ ] Large COSMO frames use a documented safe model: queueing, cache-only
  serving, pre-rendering, or another bounded execution path.
- [ ] Public users cannot trigger credential-backed Claude/OpenCode workflows
  unless explicitly allowed.
- [ ] CORS restricted to intended production origins.

## IMGW access discipline

- [ ] Refresh intervals match `METEOLENS_REFRESH_*` defaults or documented overrides.
- [ ] Timeout/retry/backoff configured via `METEOLENS_IMGW_*` settings.
- [ ] Stale cache and source failures remain visible in `/api/v1/sources`.
- [ ] No direct IMGW calls from the browser.

## Proxy and HTTP hardening

- [ ] TLS enabled at the public edge.
- [ ] HTTP security headers configured.
- [ ] nginx or upstream proxy request-size limits configured.
- [ ] nginx or upstream proxy connection and request-rate limits configured.
- [ ] Proxy read, send, and upstream timeouts configured.
- [ ] Response-size or buffering safeguards reviewed for export/render routes.
- [ ] Compression configured only for safe content types.
- [ ] `/health` and API proxy headers reviewed.

## Container hardening

- [ ] Backend production container runs as a non-root user.
- [ ] Frontend/nginx runtime user reviewed.
- [ ] Unnecessary Linux capabilities dropped.
- [ ] `no-new-privileges` enabled where supported.
- [ ] Read-only root filesystem evaluated while preserving writable `/data`.
- [ ] Container resource limits configured for CPU and memory.
- [ ] Dependency, secret, and container image scans reviewed.

## Observability

- [ ] `/health` monitored for liveness.
- [ ] Readiness or source-freshness signal monitored separately from liveness.
- [ ] `/api/v1/sources` monitored for cache freshness, source failures, and
  parser errors.
- [ ] Refresh durations and failures monitored.
- [ ] Product download/render duration, queue state, and cache hits monitored.
- [ ] Archive import progress and failures monitored.
- [ ] SQLite size, cache size, product-cache size, disk usage, memory, and CPU
  monitored.
- [ ] Container logs reviewed for `meteolens.source` fetch outcomes.
- [ ] API errors logged under `meteolens.api` with path and error code.
- [ ] Logs are structured or otherwise rotation-safe.
- [ ] Request or correlation identifiers configured where useful.
- [ ] Logs reviewed to avoid secrets or unnecessary sensitive location data.
- [ ] Operational thresholds and alert recommendations documented.

## Backups and recovery

- [ ] Backups configured for `/data`.
- [ ] Backup scope documents SQLite, observation history, cache metadata,
  product manifests/renders, reviewed geometry, and any local imports.
- [ ] Data that can be recreated from IMGW is distinguished from data that must
  be backed up.
- [ ] Restore procedure documented with commands.
- [ ] Restore from backup tested on a fresh volume.
- [ ] Persistent-volume upgrade and rollback steps documented.
- [ ] Incident-response and troubleshooting runbook available.

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
