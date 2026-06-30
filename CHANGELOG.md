# CHANGELOG

All notable changes to MeteoLens will be documented in this file.

## Unreleased

- Added initial project research and documentation for Stages 0-1.
- Added Stage 2 application skeleton: FastAPI backend, React/Vite frontend,
  MapLibre map shell, Docker Compose, `.env.example`, CI, and basic tests.
- Added Stage 3 IMGW integration: HTTP client, source definitions, parser layer,
  normalized models, file cache, real-shape fixtures, and parser/cache tests.
- Added Stage 4 backend API endpoints for map layers, stations, warnings,
  location summaries, station CSV/JSON exports, and map GeoJSON exports backed
  by normalized cache records.
- Added Stage 4 backend tests for empty cache states, station/warning filters,
  missing geometry metadata, and export attribution.
- Documented IMGW-PIB source endpoints, archive entry points, fields, risks, and
  parser status.
- Documented architecture decisions for frontend, backend, cache, database,
  exports, and deployment.
- Documented attribution and processed-data requirements.
- Added Stage 5 frontend: map-first dashboard with layer registry/toggles,
  station markers, station/warning details panel with mobile bottom sheet,
  station search, "My location", ECharts station chart, CSV/JSON/GeoJSON/PNG
  exports, URL permalink state, keyboard shortcuts with help, light/dark/system
  theme, simple/expert mode, and loading/empty/stale/partial/error states.
- Added frontend dependency `echarts` and frontend unit tests for the app shell,
  state store, permalink serialization, formatting helpers, and API error
  parsing.
- Made Docker Compose host ports configurable via `BACKEND_PORT`/`FRONTEND_PORT`
  to avoid local port clashes; the frontend API base URL follows `BACKEND_PORT`.
- Addressed Stage 5 review feedback: filter warnings by current time, restore the
  permalink map view on first load, disable the map GeoJSON export when no layers
  are active, and read API error codes from FastAPI `detail.error`.
- Added MVP roadmap and implementation task queue.
