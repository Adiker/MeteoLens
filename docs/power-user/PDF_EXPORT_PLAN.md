# Optional PDF Export Plan

PDF reports are not implemented in Stage 16.

If added later, they should be generated server-side from already cached
MeteoLens API data, not by making the browser or report renderer fetch IMGW-PIB
sources directly.

Minimum requirements:

- include IMGW-PIB attribution on every report,
- include the MeteoLens processed-data notice whenever normalized, aggregated,
  rendered, or filtered data is shown,
- show source retrieval timestamps, observation timestamps, data delay, and
  missing values,
- show unresolved geometry or unavailable product frames explicitly,
- include the local-alert disclaimer when alerts, thresholds, or
  warning/station comparisons appear,
- avoid presenting MeteoLens as an official warning publisher,
- document page templates and visual QA steps before enabling the endpoint.

Likely first report templates:

- selected station observation range,
- selected location summary,
- source freshness snapshot,
- current map-state summary with links to GeoJSON/JSON exports.
