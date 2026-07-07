# ROADMAP.md - MeteoLens

## MVP

- FastAPI backend with IMGW client, parser layer, normalization, cache, and
  healthcheck.
- React/Vite frontend with map-first layout.
- Map layers for synop, hydro, meteo, meteorological warnings, hydrological
  warnings.
- Details panel for station and warning selection.
- Simple/expert mode.
- Search for locations and stations.
- "My location" view with nearest stations and active warnings.
- Basic station charts from cached observations.
- CSV/JSON station exports.
- GeoJSON visible-object export.
- PNG current-map export.
- Permalink for map position, zoom, active layers, filters, mode, and selection.
- Light/dark/system theme.
- Data timestamps, retrieval timestamps, delay, missing-field display, and
  source attribution.

Stages 0-6 cover the MVP foundation, usable map UI, and quality/test hardening.
The known limitations documented in `README.md` are accepted MVP gaps and feed
the future stages below.

## v2

- Stage 7 - Public demo and production hardening: production Docker setup,
  static frontend serving, reverse proxy/TLS notes, production CORS guidance,
  restart policies, persistence, IMGW retry/backoff guidance, observability,
  public deployment checklist, MIT License documentation in deployment notes,
  IMGW terms verification, and documented screenshot capture requirements.
- Stage 8 - Observation history and real time series: historical observation
  persistence, time-series API, date/metric/aggregation filters, charts backed
  by real multi-point data, station comparison, rankings, time-range exports,
  and historical cache retention.
- Stage 9 - Geometry datasets and spatial warnings: legal/source-reviewed
  TERYT boundaries, basin/catchment geometries, official station coordinate
  reconciliation, warning polygons, location-based warning matching, and
  province/county/basin filters where geometry is available.

## v3

- Stage 10 - Radar, product files, GRIB, and timeline animation: IMGW product
  file research, stable/risky product ID documentation, radar-like and GRIB
  source review, raster/product ingestion design, MapLibre rendering strategy,
  timeline animation requirements, and large-file cache retention. At Stage 10,
  binary parsing and rendering stayed deferred until format, projection,
  licensing, file-size, and cache strategy were documented; Stage 14 later
  implemented the reviewed COSMO rendering path while radar stayed blocked at
  the source.
- Stage 11 - PWA, local alerts, dashboards, and power-user features: PWA
  planning, saved locations, saved map views, user dashboards, local alert
  rules, source availability/freshness dashboards, advanced expert filters,
  warning-vs-measurement comparison, trend/anomaly ideas, and generated API
  client planning. Local alerts must remain clearly separate from official
  warning responsibility.

## v4

Stage 12 (done) proved the current app can be smoke-tested and shown with real
data; Stages 13-14 continue the path: add reviewed geometry data, then render
one product layer only after source, format, legal, and cache constraints are
clear.

- Stage 12 - Public alpha release polish (done, 2026-07-03): recorded local and
  production smoke tests against live IMGW data
  (`docs/release/SMOKE_TEST_2026-07-03.md`), populated-cache screenshots,
  README alpha status, a `v0.1.0-alpha` checklist, and aligned release docs
  that keep missing geometry, stale cache, and non-renderable products visible.
- Stage 13 - Reviewed geometry dataset MVP: choose legally reviewed public
  geometry and station-coordinate sources, document licensing and redistribution
  implications, validate GeoJSON and identifier coverage, test geometry
  fallbacks, and render warning polygons only for reviewed datasets.
- Stage 14 - Radar/product rendering MVP: choose one realistic product path,
  refresh and retain selected frame manifests/renderable files, expose
  renderable-layer descriptors only when frames can actually render, and keep
  metadata-only timeline states labelled as not renderable.

## v5

Stages 15-17 deepen and stabilize the data product after alpha basics are
honest: archive backfill makes charts useful on fresh deployments, API/SDK/export
work makes the system easier to integrate without reading backend code, and
Stage 17 aligns the documentation/status trail after Stage 16.

- Stage 15 - Historical archive backfill (done): research current IMGW archive formats,
  document legal notes, add an opt-in bounded and resumable server-side import
  path for at least one clear source, preserve timestamps/nulls/attribution, and
  label imported history separately from live refresh history.
- Stage 16 - Public API, SDK, and power-user exports (done): stabilize the
  public API surface, prepare a TypeScript client with generated OpenAPI
  metadata, add example scripts for common workflows, improve
  station/warning/map exports, and document versioning, backwards
  compatibility, rate limits, and responsible use.
- Stage 17 - Post-Stage-16 stabilization (done): documentation-only cleanup
  that aligns `CLAUDE.md`, `ARCHITECTURE.md`, `TASKS.md`, `ROADMAP.md`,
  `CHANGELOG.md`, API/UI notes, and the tested status after Stage 16 without
  changing runtime behavior.

## v6 Candidates

These are planned candidates, not implemented features:

- Stage 18 - Reviewed synop station coordinates: import only a legally reviewed
  coordinate dataset so synop stations can appear as map markers with visible
  `coordinate_source` metadata.
- Stage 19 - Hydro basin geometry MVP: review basin geometry licensing and
  `kod_zlewni` mapping before enabling hydro warning polygons.
- Stage 20 - Hydrological archive backfill: extend bounded server-side archive
  imports beyond daily SYNOP once hydro archive parsing and null/status handling
  are verified.
- Stage 21 - PDF reports MVP: generate server-side reports from cached
  MeteoLens data with attribution, processed-data notices, timestamps, and
  missing-data metadata.
- Stage 22 - Performance and observability: reduce frontend bundle pressure and
  add clearer operational signals for cache freshness, fetch failures, product
  rendering, and archive imports.

## Backlog Ideas

- PDF reports.
- Reviewed synop station coordinates.
- Reviewed hydro basin geometry.
- Hydrological archive backfill.
- Observability and frontend bundle performance.
- Heatmaps and explicitly labelled interpolation.
- Station metadata browser.
- Warning history and warning-change timeline.
- Additional public data sources after source/legal review.

## Product Decisions

- Keep `meteolens` as the code package name.
- Use Vite instead of Next.js for MVP because the primary experience is an
  interactive SPA dashboard.
- Use MapLibre GL instead of Leaflet for stronger layer styling, future raster
  and tile workflows, and scalable GeoJSON handling.
- Use ECharts for dense time-series charts.
- Keep radar, GRIB, and archive analytics outside MVP.
- Do not treat mock data as a product feature.
- Do not present MeteoLens local alerts as official alerts.
