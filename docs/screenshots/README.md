# Capture populated-cache screenshots for README.md

Stage 12 demo media should show real IMGW-backed data, not fixtures.

## Steps

1. Start the stack with live cache refresh:

   ```bash
   docker compose up --build
   ```

2. Wait until `/api/v1/sources` reports `fresh` or `stale` (not `empty`) for synop/hydro/meteo.

3. Open the frontend, enable station layers, select a station with numeric values, and capture:
   - full map view with attribution bar visible,
   - station details panel with timestamps and missing-field labels,
   - warning list or empty-state if no active warnings.

4. Save PNG files here using descriptive names, for example:
   - `map-stations-light.png`
   - `station-details-expert.png`

5. Reference the images from `README.md` and keep attribution legible in every crop.

Do not commit screenshots that hide stale/error cache states unless the caption
explicitly explains the limitation.
