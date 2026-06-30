# MeteoLens

MeteoLens is a planned web application for visualising public IMGW-PIB weather
and hydrological data for Poland. The project is currently in **Stages 0-1:
research and documentation**. Application code starts in Stage 2.

The working package name is `meteolens`. Possible future product names:
PogodoScope, HydroMeteo Atlas, MeteoMapa PL.

## What It Will Do

- Show Poland as the main interactive map view.
- Display layers for synoptic stations, hydrological stations, meteorological
  stations, meteorological warnings, and hydrological warnings.
- Show measurement timestamp, retrieval timestamp, data delay, source, missing
  values, and processed-data notices.
- Provide simple and expert modes.
- Support search, "My location", station details, warning details, charts,
  exports, keyboard shortcuts, permalinked map state, and light/dark/system
  themes.

## Current Status

Implemented now:

- IMGW-PIB source research.
- Architecture decision record in documentation.
- Public backend API contract draft.
- UI/UX specification.
- Legal attribution rules.
- Implementation backlog and staged task list.
- FastAPI backend with `/health`, `/api/v1/sources`, map layers, stations,
  warnings, location summary, and CSV/JSON/GeoJSON exports backed by the cache.
- React/Vite map-first frontend: layer toggles, station markers, station and
  warning details (with mobile bottom sheet), station search, "My location",
  ECharts station chart, CSV/JSON/GeoJSON/PNG exports, URL permalinks, keyboard
  shortcuts, light/dark/system theme, simple/expert mode, and explicit
  loading/empty/stale/partial/error states.
- Docker Compose, `.env.example`, basic CI, lint, and tests.
- IMGW-PIB HTTP client, parser layer, normalized models, file cache, and parser
  tests for current synop/hydro/meteo/warning endpoints plus product manifests.

Not implemented yet:

- Warning area polygons (waiting on TERYT/basin geometry datasets; warnings
  currently render as a filterable list).
- Timeline/animation over archive or radar data.
- Automatic public cache refresh (cache is populated by backend internals).

## Data Sources

Primary source: IMGW-PIB public data service at
[danepubliczne.imgw.pl](https://danepubliczne.imgw.pl/).

The initial source set is documented in [DATA_SOURCES.md](DATA_SOURCES.md):

- current synoptic data,
- current hydrological data,
- current meteorological data,
- current meteorological warnings,
- current hydrological warnings,
- product/file API,
- archived warnings,
- measurement and observation archives.

## Quick Start

Run the backend locally:

```bash
cd backend
python -m venv .venv
.venv/bin/pip install ".[dev]"
.venv/bin/uvicorn app.main:app --reload
```

Run the frontend locally:

```bash
cd frontend
npm install
npm run dev
```

The frontend reads the backend base URL from `VITE_API_BASE_URL` (default
`http://localhost:8000`). With an empty cache the UI shows explicit empty/stale
states instead of mock data, so populate the backend cache to see live markers.

Run both with Docker Compose:

```bash
docker compose up --build
```

Local URLs:

- Frontend: `http://localhost:5173`
- Backend healthcheck: `http://localhost:8000/health`
- Backend source status: `http://localhost:8000/api/v1/sources`

## Planned Stack

- Frontend: React, TypeScript, Vite, Tailwind CSS, shadcn/ui, MapLibre GL,
  Apache ECharts, TanStack Query, Zustand.
- Backend: Python, FastAPI, Pydantic, httpx, scheduler, SQLite for MVP, Alembic
  with a migration path to PostgreSQL/PostGIS/TimescaleDB.
- Deployment: Docker Compose for local and small production deployments.

## Screenshots And Mockups

The Stage 5 map-first UI is implemented; screenshot assets under `docs/` are not
captured yet and should be added from a populated cache. The target layout is
specified in [UI_UX.md](UI_UX.md).

## Planned Exports

- CSV for selected station data.
- JSON for selected station or object details.
- GeoJSON for visible map objects.
- PNG for the current map view.
- PDF reports after MVP.

Every export must include IMGW-PIB attribution and, when applicable, a processed
data notice.

## Attribution

MeteoLens uses data from Instytut Meteorologii i Gospodarki Wodnej - Państwowy
Instytut Badawczy (IMGW-PIB). UI, exports, and documentation must identify
IMGW-PIB as the source. If MeteoLens normalizes, aggregates, interpolates, or
otherwise transforms data, the output must also say that IMGW-PIB data has been
processed.

See [LEGAL_ATTRIBUTION.md](LEGAL_ATTRIBUTION.md).

## Troubleshooting

Known early risks:

- Some endpoint fields can be `null`; MeteoLens must show missing data instead
  of replacing it with zero.
- `api/data/synop` does not include coordinates in the current response, so the
  map layer needs a separate official station list or must mark geometry as
  unavailable.
- Some product IDs listed by the product API may not be retrievable through the
  detail endpoint.
- Radar and GRIB products need separate research and parsers.

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## Development Checks

Backend:

```bash
cd backend
.venv/bin/ruff check .
.venv/bin/pytest
```

Frontend:

```bash
cd frontend
npm run lint
npm test
npm run build
```
