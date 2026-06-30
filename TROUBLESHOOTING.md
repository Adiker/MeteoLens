# TROUBLESHOOTING.md - MeteoLens

## Source Unavailable

Symptoms:

- map layer shows source error,
- API returns `source_unavailable` or `source_timeout`,
- cache is stale or empty.

Actions:

- Check the IMGW endpoint directly.
- Check backend logs for status code, timeout, and retrieval timestamp.
- Keep stale data visibly labelled if serving stale cache is enabled.

## CORS

Final frontend should call the MeteoLens backend, not IMGW directly. If browser
CORS errors appear, check that the frontend API base URL points to the backend
and that backend CORS config allows the local frontend origin.

## Missing Data

IMGW responses can contain `null` fields or omit fields. MeteoLens must display
missing values and list missing fields in expert mode. Do not convert missing
values to zero.

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

