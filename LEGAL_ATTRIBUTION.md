# LEGAL_ATTRIBUTION.md - Attribution And Legal Notes

This document is an implementation guide, not legal advice. Users must verify
the current IMGW-PIB terms before public, production, or commercial use.

Research dates: 2026-06-29 (base IMGW terms), 2026-07-05 (COSMO product
download verification and daily SYNOP archive format verification), 2026-07-07
(WMO OSCAR/Surface synop station-coordinate review).

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

### Reviewed IMGW Archive Dataset (Stage 15)

Stage 15 uses the same IMGW-PIB public data service for daily SYNOP archive
CSV/ZIP files under
`/data/dane_pomiarowo_obserwacyjne/dane_meteorologiczne/dobowe/synop/`.
No new non-IMGW provider is introduced. Imported rows must keep IMGW-PIB
attribution, the MeteoLens processed-data notice, observed timestamp,
import/retrieval timestamp, archive source URL, and missing/null status.

### Reviewed Geometry Datasets (Stage 13)

The administrative boundary datasets shipped in `data/geometry/`
(`teryt_voivodeships`, `teryt_counties`) are simplified derivatives of the
Państwowy Rejestr Granic (PRG). PRG boundary data is free public data under
art. 40a ust. 2 pkt 1 of the Polish Geodetic and Cartographic Law; public and
commercial use, caching, and redistribution are allowed with source
attribution. Use this attribution wherever the boundary geometry is shown or
exported alongside the IMGW-PIB attribution:

```text
Granice administracyjne: Państwowy Rejestr Granic (PRG), © GUGiK; kopia SHP: gis-support.pl; uproszczenie geometrii: MeteoLens.
```

The simplification is a MeteoLens transformation, so views and exports showing
these polygons must keep the processed-data notice. The full review (canonical
URLs, terms, limitations) lives in `docs/geometry/GEOMETRY_SOURCES.md` and in
the machine-readable manifest metadata exposed by `/api/v1/geometry/datasets`.

### Reviewed Synop Station Coordinates (Stage 18)

Stage 18 ships `synop_stations`, a reviewed Point dataset resolving current
IMGW SYNOP `id_stacji` values to WMO OSCAR/Surface station metadata by WIGOS ID
(`0-20000-0-<id_stacji>`). WMO describes OSCAR as its global repository of
observing-system capabilities, and WMO wis2box documentation describes fetching
and caching station metadata from OSCAR/Surface by WIGOS ID. The review uses WMO
Unified Data Policy Resolution 1 and the OSCAR/Surface station-metadata caching
guidance for public-use clearance.

Use this attribution wherever synop station coordinates are shown or exported:

```text
Współrzędne stacji synoptycznych: WMO OSCAR/Surface; identyfikatory stacji i dane pomiarowe: IMGW-PIB; przetworzenie: MeteoLens.
```

MeteoLens does not assert commercial-use clearance for the redistributed OSCAR
station-coordinate dataset; commercial deployments must re-review current
WMO/OSCAR terms. The full review and refresh pipeline live in
`docs/geometry/GEOMETRY_SOURCES.md` and
`docs/geometry/metadata/synop_stations.json`.

### Reviewed Product Dataset (Stage 14)

The Stage 14 product-rendering MVP uses public IMGW-PIB COSMO
`COSMO_HVD_*_00` GRIB1 files downloaded through
`danepubliczne.imgw.pl/api/data/product`. The product path was verified on
2026-07-05: COSMO GRIB files download directly from IMGW, while radar
composite file URLs redirect to HTML and remain blocked at the source. Full
technical notes live in `docs/products/PRODUCT_RESEARCH.md` and
`docs/products/RASTER_PIPELINE.md`.

Rendered COSMO overlays are processed MeteoLens outputs: source GRIB values are
decoded, converted from Kelvin to Celsius, resampled from the COSMO rotated
grid, colorized, cached, and served as PNG images. Every rendered product view,
PNG metadata payload, API response, screenshot, and export must keep the
IMGW-PIB attribution and the processed-data notice.

## Implementation Requirements

- API responses include `source`, `attribution`, and `processed_notice` fields
  or equivalent metadata.
- Exports include attribution and processed-data notices.
- UI components have a shared attribution component to avoid drift.
- Tests should cover presence of attribution metadata in export endpoints.

## Open Legal Questions

- TERYT polygons are resolved (PRG, see above). Which dataset will be used for
  hydrological basin polygons (candidate: MPHP, PGW Wody Polskie), and do its
  terms allow redistribution?
- WMO OSCAR/Surface synop coordinates are resolved for public use, but
  commercial deployments must re-review current WMO/OSCAR terms before
  downstream redistribution.
- Radar composite files are high-value, but current public file delivery is
  blocked at the source. Re-review terms, projection metadata, and download
  behavior before implementing radar rendering.
