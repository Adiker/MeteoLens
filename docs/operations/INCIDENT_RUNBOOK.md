# MeteoLens Stage 20 Incident Runbook

## Triage

1. Check `/health/live` and `/health/ready`; preserve the `X-Request-ID`.
2. Inspect private Prometheus alerts and `/api/v1/sources` before restarting a
   cache-backed instance.
3. Record UTC time, active image digest, Compose version, volume name, and the
   relevant JSON logs. Never paste tokens, signed IMGW URLs, or location query
   strings into an incident record.

## Common actions

- **IMGW outage or stale cache:** leave the service running, present cached data
  as stale, inspect refresh/parser metrics, and retry only through configured
  scheduler/backoff.
- **SQLite or `/data` not ready:** stop imports/renders, make an essential
  backup if possible, inspect free space and UID 10001 ownership, then restore
  only into a fresh volume after verification.
- **Disk or memory alert:** stop cold renders and archive backfill, retain the
  database/geometry, use product retention or expand the host volume, then
  confirm `/health/ready` and source freshness.
- **Failed upgrade:** keep the failed volume, return to the previous image and
  environment, and restore data only if integrity checks fail.

## Recovery validation

After any restore, verify the backup checksum, `PRAGMA integrity_check`,
geometry status, `/health/ready`, `/api/v1/sources`, a station-history query,
and attribution in one export. Record the result in `docs/release/`.
