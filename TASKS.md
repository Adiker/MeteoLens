# TASKS.md - MeteoLens Implementation Queue

## Stage 0 - Research

- [x] Verify IMGW-PIB API info page and current endpoint list.
- [x] Verify current `synop`, `hydro`, `meteo`, `warningsmeteo`,
  `warningshydro`, and `product` endpoints.
- [x] Verify archive directories for historical meteo/hydro warnings.
- [x] Verify measurement and observation archive entry points.
- [x] Document source fields, formats, risks, and parser status.
- [x] Document legal attribution requirements.

## Stage 1 - Documentation

- [x] Create `README.md`.
- [x] Create `AGENTS.md`.
- [x] Create `CLAUDE.md`.
- [x] Create `ARCHITECTURE.md`.
- [x] Create `DATA_SOURCES.md`.
- [x] Create `LEGAL_ATTRIBUTION.md`.
- [x] Create `ROADMAP.md`.
- [x] Create `TASKS.md`.
- [x] Create `API_CONTRACT.md`.
- [x] Create `UI_UX.md`.
- [x] Create `DEPLOYMENT.md`.
- [x] Create `TROUBLESHOOTING.md`.
- [x] Create `CHANGELOG.md`.
- [x] Create initial project directories.

## Stage 2 - Skeleton

- [x] Create `frontend/` with React, TypeScript, Vite.
- [x] Add Tailwind CSS and shadcn/ui-style utility setup.
- [x] Add MapLibre GL dependency and initial map shell.
- [x] Create `backend/` with FastAPI, Pydantic, httpx, pytest.
- [x] Add backend healthcheck endpoint.
- [x] Add Docker Compose.
- [x] Add `.env.example`.
- [x] Add lint/format/test commands.
- [x] Add basic CI workflow.

## Stage 3 - IMGW Integration

- [x] Add IMGW HTTP client with timeouts, retries, response metadata, and clear
  error reporting.
- [x] Add raw response cache model.
- [x] Add parser for `api/data/synop`.
- [x] Add parser for `api/data/hydro`.
- [x] Add parser for `api/data/meteo`.
- [x] Add parser for `api/data/warningsmeteo`.
- [x] Add parser for `api/data/warningshydro`.
- [x] Add product manifest parser for `api/data/product`.
- [x] Add normalization layer.
- [x] Add parser fixtures from real IMGW responses for tests.
- [x] Add tests for null handling, numeric conversion, and timestamps.

## Stage 4 - Backend API

- [x] Add `/health`.
- [x] Add `/api/v1/sources`.
- [x] Add `/api/v1/map/layers`.
- [x] Add `/api/v1/stations`.
- [x] Add `/api/v1/stations/{id}`.
- [x] Add `/api/v1/stations/{id}/observations`.
- [x] Add `/api/v1/warnings`.
- [x] Add `/api/v1/warnings/{id}`.
- [x] Add `/api/v1/location/summary`.
- [x] Add CSV/JSON/GeoJSON export endpoints.
- [x] Add backend tests for cache-backed API endpoints and exports.
- [x] Update `API_CONTRACT.md` after implementation.

## Stage 5 - Frontend

- [x] Add map shell centered on Poland.
- [x] Add layer registry and toggles.
- [x] Add legends.
- [x] Add station and warning markers/polygons. Stations render as coloured
  markers; warnings render as a filterable list because the backend exposes no
  area geometry yet (`missing_area_geometry_dataset`). Polygons land when TERYT
  and basin geometry datasets are cached.
- [x] Add details panel and mobile bottom sheet.
- [x] Add search.
- [x] Add "My location".
- [x] Add charts. Snapshot cache exposes one timestamp per station, so the chart
  shows current metric values; multi-frame time series follows archive data.
- [x] Add export controls (station CSV/JSON, map GeoJSON, current-map PNG).
- [x] Add permalink state.
- [x] Add keyboard shortcuts and shortcut help.
- [x] Add light/dark/system mode.
- [x] Add simple/expert mode.
- [x] Add loading, empty, stale, partial, and error states.

Deferred within Stage 5 scope: the bottom timeline/animation control is inert
until time-aware (archive/radar) data exists, and province/time-range quick
filters wait for area geometry and archive series.

## Stage 6 - Quality

- [ ] Add backend parser/API test coverage.
- [ ] Add frontend component tests.
- [ ] Add basic E2E tests.
- [ ] Verify attribution in UI and exports.
- [ ] Verify missing values are not converted to zero.
- [ ] Document known limitations before MVP release.
