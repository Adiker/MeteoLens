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
  IMGW terms verification, and README demo screenshots.
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
  timeline animation requirements, and large-file cache retention. Binary
  parsing and rendering remain deferred until format, projection, licensing,
  file-size, and cache strategy are documented.
- Stage 11 - PWA, local alerts, dashboards, and power-user features: PWA
  planning, saved locations, saved map views, user dashboards, local alert
  rules, source availability/freshness dashboards, advanced expert filters,
  warning-vs-measurement comparison, trend/anomaly ideas, and generated API
  client planning. Local alerts must remain clearly separate from official
  warning responsibility.

## Backlog Ideas

- PDF reports.
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
