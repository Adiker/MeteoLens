# LEGAL_ATTRIBUTION.md - Attribution And Legal Notes

This document is an implementation guide, not legal advice. Users must verify
the current IMGW-PIB terms before public, production, or commercial use.

Research date: 2026-06-29.

Source terms reviewed:
[https://danepubliczne.imgw.pl/pl/regulations](https://danepubliczne.imgw.pl/pl/regulations).

## Project License

MeteoLens code and documentation are released under the MIT License. See
[`LICENSE`](LICENSE).

This project license does not grant additional rights to IMGW-PIB data or any
other third-party datasets. Source data remains governed by the applicable
source terms, attribution requirements, and deployment-use restrictions.

## Source

Data source: Instytut Meteorologii i Gospodarki Wodnej - Panstwowy Instytut
Badawczy (IMGW-PIB), public data service
[danepubliczne.imgw.pl](https://danepubliczne.imgw.pl/).

## Mandatory Attribution

Every UI view, export, report, screenshot intended for sharing, and README must
identify IMGW-PIB as the data source.

Use this short attribution in UI:

```text
Źródło danych: IMGW-PIB.
```

Use this longer attribution in exports and documentation:

```text
Źródłem danych jest Instytut Meteorologii i Gospodarki Wodnej - Państwowy Instytut Badawczy (IMGW-PIB).
```

## Processed Data Notice

MeteoLens will parse, normalize, convert, cache, filter, and sometimes aggregate
public IMGW-PIB data. Any transformed output must include a processed-data
notice.

Use this short notice in UI:

```text
Dane IMGW-PIB zostały przetworzone przez MeteoLens.
```

Use this longer notice in exports and reports:

```text
Dane Instytutu Meteorologii i Gospodarki Wodnej - Państwowego Instytutu Badawczego zostały przetworzone przez MeteoLens.
```

## Where Attribution Must Appear

- Map attribution/footer.
- Station detail panel.
- Warning detail panel.
- Expert mode metadata.
- CSV exports as commented metadata or sidecar metadata where the CSV format
  allows it.
- JSON exports in a top-level `attribution` object.
- GeoJSON exports in top-level `properties.attribution` or `metadata`.
- PNG exports as visible caption or metadata sidecar if visible caption is not
  technically possible.
- Future PDF reports in footer and report metadata.
- README and documentation.

## Commercial And Public Use

The IMGW-PIB regulations include additional considerations for some commercial
or specialized uses. MeteoLens must not claim that public or commercial use is
always automatically cleared. Documentation and deployment notes should tell
operators to verify current terms before public or commercial deployment.

Stage 7 public demo work must include:

- verification of the current IMGW-PIB terms for the intended deployment,
- confirmation that the MIT License is documented in public deployment notes,
- confirmation that README screenshots and demo media carry attribution when
  shared publicly,
- deployment notes that do not claim production or commercial clearance without
  review.

## Data Quality And Responsibility

MeteoLens must communicate that:

- values can be delayed,
- source fields can be missing,
- some source data may be unverified,
- derived values are computed by MeteoLens, not directly issued by IMGW-PIB,
- users should not treat MeteoLens as an official warning system.

Stage 11 local alerts must keep this responsibility boundary visible. Local
rules based on nearby stations, thresholds, stale data, or active warnings are
MeteoLens convenience features, not official warning issuance.

## External Dataset Review

Stage 9 geometry datasets and Stage 10 product/raster datasets must pass
source/legal review before implementation. Each reviewed dataset should record:

- provider and canonical source URL,
- license or terms URL,
- attribution text,
- public-use and commercial-use status,
- allowed processing, caching, redistribution, and screenshot/export use,
- update cadence and version,
- known limitations or unresolved usage questions.

Do not add unofficial or legally unclear geometry, radar, product, GRIB, or
station-coordinate sources as implemented sources. If a source is technically
useful but unclear, mark it as requiring legal/source review in
`DATA_SOURCES.md`.

## Implementation Requirements

- API responses include `source`, `attribution`, and `processed_notice` fields
  or equivalent metadata.
- Exports include attribution and processed-data notices.
- UI components have a shared attribution component to avoid drift.
- Tests should cover presence of attribution metadata in export endpoints.

## Open Legal Questions

- Which external geometry datasets will be used for TERYT and basin polygons?
- Are any selected external datasets compatible with the MIT License and the
  intended deployment model?
- Which product/radar/model files are high-value open data and which require
  additional terms review?
