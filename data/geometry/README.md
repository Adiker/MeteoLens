# Geometry dataset manifest template

Copy reviewed geometry datasets into `data/geometry/` and list them in
`manifest.json`. MeteoLens loads datasets only from this directory; it does not
download geometry automatically.

Example entry:

```json
{
  "datasets": [
    {
      "key": "teryt_counties",
      "title": "TERYT county boundaries",
      "source": "https://example.gov.pl/...",
      "license_note": "Attribution and terms summary from source/legal review.",
      "file": "teryt_counties.geojson"
    }
  ]
}
```

See `docs/geometry/GEOMETRY_SOURCES.md` for the source/legal review checklist.

GeoJSON features must expose a stable `code` property (or `teryt` / `basin_code`)
matching IMGW warning area codes.
