# Stage 12 smoke test record — 2026-07-03

Recorded local development and production smoke tests against **live IMGW-PIB
data** (no fixtures). Reproduce with the commands below; results were captured
on Linux with Docker 29.6.1 / Compose 5.1.4.

Historical scope note: this Stage 12 record predates bundled PRG geometry,
COSMO product rendering, daily SYNOP archive backfill, public API/client/export
stabilization, and bundled WMO OSCAR/Surface SYNOP station coordinates. It is
not a substitute for the current-main production validation planned in Stage 21
before tagging `v0.1.0-alpha`.

## Port overrides used in this run

The documented default ports were taken by unrelated local services, so the
run used the supported overrides (this is exactly what they exist for):

- Backend host port: `BACKEND_PORT=8010` (default 8000 was in use).
- Production public HTTP port: `PUBLIC_HTTP_PORT=8081` in `.env.production`
  (default 8080 was in use), with
  `METEOLENS_FRONTEND_ORIGIN=http://localhost:8081`.

On a host with free default ports, run the commands without overrides and
substitute 8000/8080 in the URLs below.

## Local development smoke test

Command:

```bash
BACKEND_PORT=8010 docker compose up --build -d
```

The backend synced the live IMGW cache on startup (`METEOLENS_SYNC_ON_STARTUP`)
and passed its healthcheck before the frontend started.

### Backend checks

| Check | Result |
| --- | --- |
| `GET /health` | `{"status": "ok", "service": "meteolens-backend", "version": "0.1.0", "environment": "development"}` |
| `GET /api/v1/sources` | all six sources `cache_status: fresh`, no parser errors |
| synop records | 62 (`parser_status: implemented`) |
| hydro records | 913 |
| meteo records | 785 |
| warningsmeteo records | 5 |
| warningshydro records | 50 |
| product manifest records | 42 (`implemented_manifest_only`) |
| `GET /api/v1/stations` | stations with explicit `missing_fields` (`lat`, `lon` for synop) |
| `GET /api/v1/stations/{id}` + `/observations` | `series_kind: history`, multi-point series |
| `GET /api/v1/warnings` + `/warnings/{id}` | 55 warnings; details keep `missing_area_geometry_dataset` explicit |
| `GET /api/v1/location/summary?lat=52.23&lon=21.01` | nearest stations + warnings returned |
| `GET /api/v1/export/station/{id}.csv` | rows carry `attribution` and `processed_notice` columns |
| `GET /api/v1/export/station/{id}.json` | top-level `attribution` + `processed_notice` |
| `GET /api/v1/export/station/{id}/observations.csv` | range export with `series_kind`/`interval` columns |
| `GET /api/v1/export/map.geojson` | `FeatureCollection` (599 hydro features) with `attribution`, `processed_notice`, and `missing_geometry` list |
| `GET /api/v1/products`, `/api/v1/map/timeline` | 42 products; timeline `layers: []` (no cached frame manifests — expected) |

### Frontend checks (`frontend/scripts/smoke.mjs`)

```bash
cd frontend
npx playwright install chromium   # first run only
node scripts/smoke.mjs http://localhost:5173 http://localhost:8010 ../docs/screenshots
```

Result: **12/12 checks passed.**

| Check | Result |
| --- | --- |
| Map shell renders with IMGW-PIB attribution bar | PASS |
| Timeline shell hidden matches empty `/api/v1/map/timeline` | PASS (documented empty state; renders only with cached product frame manifests) |
| Station details panel opens from search | PASS |
| Station details show retrieval timestamp and delay | PASS |
| Expert mode exposes raw source data | PASS |
| Station CSV/JSON export links present | PASS |
| Warning list renders | PASS (52 active warnings) |
| Warning details show validity + office metadata | PASS |
| Missing area geometry stays explicit ("Brak geometrii obszaru") | PASS |
| Export menu offers GeoJSON and PNG | PASS |
| Current-map PNG export downloads a file | PASS (`meteolens-mapa.png`) |
| Power-user panel opens in expert mode | PASS |

The same run captured the populated-cache screenshots committed under
`docs/screenshots/` and referenced from `README.md`. All of them show the
IMGW-PIB attribution bar and the processed-data notice.

## Production smoke test

Commands:

```bash
cp deploy/.env.production.example .env.production
# adjust PUBLIC_HTTP_PORT / METEOLENS_FRONTEND_ORIGIN if 8080 is taken
docker compose --env-file .env.production -f docker-compose.prod.yml up --build -d
```

| Check | Result |
| --- | --- |
| Configured public HTTP port opens | PASS (`http://localhost:8081`) |
| nginx `GET /healthz` | 200 |
| Static frontend served by nginx (no Vite dev server) | PASS (`assets/index-*.js` bundles) |
| Proxied `GET /health` | `"environment": "production"` |
| Proxied `GET /api/v1/sources` | all six sources `fresh` from live IMGW startup sync |
| Backend port not published to the host | PASS (only nginx exposed) |
| Frontend smoke script against `http://localhost:8081` | **12/12 checks passed** |

Torn down afterwards with
`docker compose --env-file .env.production -f docker-compose.prod.yml down`.

## Consistency fix required by this run

A fresh dev run followed by the documented production build used to fail: the
dev backend container writes `data/cache/*.json` as root with `0600`
permissions into the `./data` bind mount, and `frontend/Dockerfile.prod`
builds from the repository root, so the classic builder aborted with
`no permission to read from data/cache/...`. Fixed by adding a root
`.dockerignore` that restricts the root build context to `frontend/` and
`deploy/nginx/`. This is the "small consistency fix" allowed within Stage 12
scope.

## Known-limitation states confirmed during the run

- Synop stations report `missing_fields: ["lat", "lon"]` and stay off the map
  (62 listed, 0 rendered as markers).
- Warnings render as a list with `missing_area_geometry_dataset` — no reviewed
  geometry datasets are installed (`data/geometry/manifest.json` is empty).
- The product timeline is hidden because no product frame manifests are
  cached; `/api/v1/map/timeline` returns `layers: []`.
