# Populated-cache screenshots for README.md

Demo media must show real IMGW-backed data, not fixtures. The committed
screenshots were refreshed on 2026-07-14 from a live cache (see
`docs/release/STAGE_21_VALIDATION_2026-07-14.md`):

- `map-stations-light.png` — map view, reviewed SYNOP markers, resolved meteo
  warning polygons, explicit missing hydro geometry, and a COSMO timeline.
- `station-details-expert.png` — station details in expert mode with raw JSON.
- `warning-details-list.png` — meteorological warning details with resolved
  reviewed administrative geometry.
- `power-user-panel.png` — expert power-user panel with the freshness monitor.

## Re-capturing

1. Start the stack with live cache refresh:

   ```bash
   docker compose up --build
   ```

2. Wait until `/api/v1/sources` reports `fresh` or `stale` (not `empty`) for
   synop/hydro/meteo.

3. Either run the smoke script, which captures all four screenshots into the
   given directory as part of its checks:

   ```bash
   cd frontend
   npx playwright install chromium  # first run only
   node scripts/smoke.mjs http://localhost:5173 http://localhost:8000 ../docs/screenshots
   ```

   or capture manually: open the frontend, enable station layers, select a
   station with numeric values, and shoot the full map view with the
   attribution bar, the station details panel with timestamps and
   missing-field labels, and the warning list (or empty state).

4. Keep the IMGW-PIB attribution and processed-data notice legible in every
   crop, and update the references in `README.md` if filenames change.

Do not commit screenshots that hide stale/error cache states unless the caption
explicitly explains the limitation.
