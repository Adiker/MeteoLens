# MeteoLens API Examples

These examples use built-in Node.js `fetch` and require Node 18 or newer.

Set `METEOLENS_API_BASE_URL` when the API is not running on
`http://localhost:8000`.

```bash
METEOLENS_API_BASE_URL=http://localhost:8000 node examples/api/list-stations.mjs --type hydro --q Wisła
node examples/api/fetch-station-observations.mjs hydro:151140030 --metric water_level
node examples/api/export-station-range.mjs hydro:151140030 --format csv --from 2026-06-01T00:00:00+02:00
node examples/api/check-source-freshness.mjs
node examples/api/active-warnings-for-location.mjs 52.23 21.01 --radius-km 75
```

Every endpoint or export used here returns IMGW-PIB attribution and the
MeteoLens processed-data notice. MeteoLens local alerts and warning comparisons
are not official IMGW-PIB warnings.
