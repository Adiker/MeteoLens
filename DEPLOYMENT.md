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

Stage 7 should create a production deployment path separate from the local
development Docker Compose setup.

Required production changes:

- build the frontend with Vite and serve static assets through nginx, Caddy, or
  an equivalent static server,
- do not run the Vite dev server in production,
- build the backend image without development-only dependencies,
- configure a reverse proxy with TLS termination,
- document production CORS origins instead of using permissive local defaults,
- add restart policies for backend and frontend services,
- mount persistent volumes for SQLite/cache data and any manually reviewed
  geometry datasets,
- document backup expectations for database, cache metadata, and reviewed
  external datasets,
- document rate-limit, retry, and backoff expectations for IMGW access,
- keep stale cache and source failures visible instead of masking them.

Stage 7 public deployment checklist:

- current IMGW-PIB terms verified for the intended public or commercial use,
- project license selected and documented,
- attribution visible in UI, exports, screenshots, and README,
- processed-data notice visible wherever data is normalized, aggregated,
  converted, or otherwise transformed,
- production CORS origins set,
- reverse proxy and TLS configured,
- persistent volumes configured and tested,
- restart policies configured,
- `/health` and `/api/v1/sources` monitored,
- source fetch, parser failure, stale cache, and API error logs reviewed,
- README screenshots captured from a populated real cache,
- known limitations remain visible.

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
