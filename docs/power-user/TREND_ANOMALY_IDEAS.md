# Trend And Anomaly Detection Ideas

Planning document only — no automated anomaly engine is implemented in Stage 11.

## Candidate Signals

| Signal | Inputs | Notes |
| --- | --- | --- |
| Station spike | Observation history time series | Needs Stage 8 persistence and sufficient retention |
| Warning vs measurement mismatch | `/api/v1/compare/warning-station/{id}` | Implemented as manual expert comparison |
| Source stale streak | `/api/v1/status/freshness` | Useful for ops dashboards |
| Radar frame gap | Product frame metadata | Detect missing timestamps in manifest slices |
| Basin/station divergence | Hydro level + warning areas | Requires reliable geometry and thresholds |

## UX Principles

- Label anomalies as **suspected** until verified against source timestamps.
- Never replace IMGW warning levels with derived scores.
- Show source time, retrieval time, and missing-field metadata beside any hint.

## Suggested Future Pipeline

1. Persist rolling baselines per station/metric in SQLite or TimescaleDB.
2. Add opt-in expert panels that explain why a point was flagged.
3. Keep exports and API responses free of hidden interpolation.

See also: [OPENAPI_CLIENT.md](./OPENAPI_CLIENT.md).
