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
