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
- Added MVP roadmap and implementation task queue.
