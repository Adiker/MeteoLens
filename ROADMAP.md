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

## v2

- Archive observation browsing.
- Station comparison.
- Rankings for temperature, precipitation, wind, and water level.
- Warning history and warning-change timeline.
- Better TERYT/basin geometry coverage.
- Export polish and PDF reports.
- PWA support.

## v3

- Radar product research and rendering pipeline.
- GRIB/model layer research and rendering pipeline.
- Heatmaps and explicitly labelled interpolation.
- Local alerts.
- Trend detection.
- Warning-vs-measurement comparison.

## Backlog Ideas

- User-defined dashboards.
- Saved map views.
- Advanced expert filters.
- Source availability dashboard.
- Data freshness monitor.
- Station metadata browser.
- Public API client generation from OpenAPI.

## Product Decisions

- Keep `meteolens` as the code package name.
- Use Vite instead of Next.js for MVP because the primary experience is an
  interactive SPA dashboard.
- Use MapLibre GL instead of Leaflet for stronger layer styling, future raster
  and tile workflows, and scalable GeoJSON handling.
- Use ECharts for dense time-series charts.
- Keep radar, GRIB, and archive analytics outside MVP.

