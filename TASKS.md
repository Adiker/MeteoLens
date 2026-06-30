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

- [ ] Add `/health`.
- [ ] Add `/api/v1/sources`.
- [ ] Add `/api/v1/map/layers`.
- [ ] Add `/api/v1/stations`.
- [ ] Add `/api/v1/stations/{id}`.
- [ ] Add `/api/v1/stations/{id}/observations`.
- [ ] Add `/api/v1/warnings`.
- [ ] Add `/api/v1/warnings/{id}`.
- [ ] Add `/api/v1/location/summary`.
- [ ] Add CSV/JSON/GeoJSON export endpoints.
- [ ] Update `API_CONTRACT.md` after implementation.

## Stage 5 - Frontend

- [ ] Add map shell centered on Poland.
- [ ] Add layer registry and toggles.
- [ ] Add legends.
- [ ] Add station and warning markers/polygons.
- [ ] Add details panel and mobile bottom sheet.
- [ ] Add search.
- [ ] Add "My location".
- [ ] Add charts.
- [ ] Add export controls.
- [ ] Add permalink state.
- [ ] Add keyboard shortcuts and shortcut help.
- [ ] Add light/dark/system mode.
- [ ] Add simple/expert mode.
- [ ] Add loading, empty, stale, partial, and error states.

## Stage 6 - Quality

- [ ] Add backend parser/API test coverage.
- [ ] Add frontend component tests.
- [ ] Add basic E2E tests.
- [ ] Verify attribution in UI and exports.
- [ ] Verify missing values are not converted to zero.
- [ ] Document known limitations before MVP release.
