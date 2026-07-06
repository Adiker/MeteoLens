# Public API Client

Stage 16 adds a lightweight TypeScript client under
`packages/meteolens-api-client/`. It is intentionally small: handwritten fetch
helpers for common workflows, plus generated OpenAPI metadata committed in
`src/generated.ts` so route drift is visible in tests and reviews.

## Source Of Truth

- Live FastAPI OpenAPI schema: `/openapi.json`
- Human-readable contract: [`API_CONTRACT.md`](../../API_CONTRACT.md)
- Client generator: [`scripts/api/generate_ts_client.py`](../../scripts/api/generate_ts_client.py)
- Generated metadata: [`packages/meteolens-api-client/src/generated.ts`](../../packages/meteolens-api-client/src/generated.ts)

Regenerate after changing public routes or response models:

```bash
backend/.venv/bin/python scripts/api/generate_ts_client.py
```

Then type-check the package:

```bash
cd packages/meteolens-api-client
npm run check
```

## Supported Helpers

The client currently covers the workflows most useful for integrations:

- `listStations`
- `getStationObservations`
- `stationObservationsCsvUrl`
- `stationObservationsJsonUrl`
- `getFreshnessStatus`
- `getActiveWarningsForLocation`
- `warningGeoJsonUrl`

It does not publish to npm yet. Treat it as a repo-local SDK template until a
tagged release process and package-publishing policy exist.

## Examples

Runnable Node examples live in [`examples/api/`](../../examples/api/). They use
Node 18+ built-in `fetch` and the `METEOLENS_API_BASE_URL` environment variable.

Example:

```bash
METEOLENS_API_BASE_URL=http://localhost:8000 \
  node examples/api/list-stations.mjs --type hydro --limit 5
```

The examples call MeteoLens endpoints only. They do not fetch IMGW-PIB sources
directly from the user's machine.

## Versioning Rules

1. Regenerate client metadata from the backend OpenAPI schema before opening a
   PR that changes public routes or response models.
2. Treat additive OpenAPI changes as compatible within `/api/v1`.
3. Treat removed fields, renamed fields, changed field meaning, changed export
   column names, or changed default filter behavior as breaking.
4. Keep attribution, processed-data notices, source timestamps, and
   `alerting_disclaimer` fields visible in client-facing types and examples.
