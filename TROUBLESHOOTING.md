# TROUBLESHOOTING.md - MeteoLens

## Source Unavailable

Symptoms:

- map layer shows source error,
- API returns `source_unavailable` or `source_timeout`,
- cache is stale or empty.

Actions:

- Check the IMGW endpoint directly.
- Check backend logs for status code, timeout, and retrieval timestamp.
- Confirm `METEOLENS_SYNC_ON_STARTUP=true` is set when the cache should be
  populated at backend startup.
- Check `GET /api/v1/sources`; `empty` means the source has not been cached,
  `error` means the last fetch failed, and `stale` can still serve the previous
  successful payload.
- Keep stale data visibly labelled if serving stale cache is enabled.

## Port Already In Use

Symptoms:

- `docker compose up` fails with `failed to bind host port 0.0.0.0:8000/tcp:
  address already in use` (or the same for `5173`).

Cause: another local process already listens on that host port. Find it with
`ss -ltnp | grep :8000`.

Actions:

- Stop the conflicting process, or
- Publish MeteoLens on a different host port via `BACKEND_PORT` / `FRONTEND_PORT`
  (see `.env.example`), e.g. `BACKEND_PORT=8010 docker compose up --build`. The
  frontend's `VITE_API_BASE_URL` follows `BACKEND_PORT` automatically, so the
  browser still reaches the backend.

## CORS

Final frontend should call the MeteoLens backend, not IMGW directly. If browser
CORS errors appear, check that the frontend API base URL points to the backend
and that backend CORS config allows the local frontend origin.

## Missing Data

IMGW responses can contain `null` fields or omit fields. MeteoLens must display
missing values and list missing fields in expert mode. Do not convert missing
values to zero.

## Archive Backfill

Symptoms:

- `POST /api/v1/archive/backfill/synop-daily` returns `422`,
- station chart still shows a snapshot after an import,
- imported rows disappear after a cleanup run.

Actions:

- Confirm the requested range is within `METEOLENS_ARCHIVE_BACKFILL_MAX_DAYS`.
- Confirm the archive range does not exceed
  `METEOLENS_ARCHIVE_BACKFILL_MAX_FILES`; current-year daily SYNOP imports are
  monthly ZIPs, while older years can resolve to many station-code ZIPs.
- Check the response `status`, `files_processed`, `parser_warnings`, and
  `errors`; failed runs are recorded in `archive_import_runs`.
- Query `/api/v1/stations/{id}/observations?metric=temperature` for a stable
  station ID such as `synop:349190600`; map/list discovery still requires live
  cache data and reviewed coordinates.
- Remember that imported rows use the same SQLite retention policy as live
  history. `METEOLENS_OBSERVATION_RETENTION_DAYS` can prune old archive rows.
- Do not call IMGW archive ZIPs from the browser. Archive fetching is backend
  only.

## Synop Stations Without Coordinates

`api/data/synop` currently does not include `lat/lon`. The synop map layer needs
an official station metadata source. Until then, synop records can appear in
tables/details but should not be silently placed on the map.

## Warning Geometry Missing

Meteorological warnings return TERYT code lists. Hydrological warnings return
area/basin information. If polygons are missing:

- confirm the geometry dataset is installed,
- verify code mapping,
- show warning details without polygon geometry,
- label the layer as partial instead of hiding warnings.

## Parsing Files And Encodings

Archive CSV/TXT files may use encodings that are not UTF-8. Parsers should detect
or explicitly configure encoding and tests should include representative
fixtures.

## Product API Problems

Some products listed by `api/data/product` may fail at the detail endpoint.
Treat this as source risk:

- store the failure,
- show a clear unsupported/unavailable state,
- do not fake radar/model data.

## Radar And GRIB

Radar and GRIB products are post-MVP. They need:

- file manifest parsing,
- binary format readers,
- coordinate/projection handling,
- tile or raster rendering,
- cache retention policy.

Do not add them to MVP UI as working layers until real parsing and rendering are
implemented.

## Attribution Missing

If an export or UI view lacks attribution, treat it as a release blocker. Check
shared attribution components and export metadata builders.

## Production Readiness And Recovery

`/health/live` only proves that the backend process can answer requests.
`/health/ready` returns `degraded` when IMGW is unavailable but cached data can
still be served; inspect `/api/v1/sources` and Prometheus source metrics before
restarting a healthy cache-backed service. A `503 not_ready` indicates SQLite,
startup, or `/data` write failure: check disk space, ownership of the named
volume (UID 10001), and the backend JSON logs with the response's
`X-Request-ID`.

When `/data` free-space alerts fire, stop archive imports and cold product
renders, remove only documented regenerable product cache through its retention
settings, create an essential backup, and increase host storage. Never delete
`meteolens.sqlite3`, geometry, or a backup archive to free space.

For failed upgrades, retain the previous image and `.env.production`, stop the
new stack, return to the previous image, and verify readiness plus source state.
Restore a backup into a fresh empty volume only when persistent data is damaged;
run `data-ops verify` before any restore and preserve the failed volume until
the recovery is confirmed.
