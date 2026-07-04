# DATA_SOURCES.md - IMGW-PIB Sources

Research date: 2026-06-29.

Primary service: [danepubliczne.imgw.pl](https://danepubliczne.imgw.pl/).
Official API information:
[https://danepubliczne.imgw.pl/pl/apiinfo](https://danepubliczne.imgw.pl/pl/apiinfo).

Statuses:

- `planned`: documented for implementation.
- `implemented`: parser/API support exists.
- `risky`: source exists but has technical/legal/format uncertainty.
- `blocked`: cannot be implemented without another decision or source.

## Current Synoptic Data

- Name: current synoptic station data.
- Endpoint: `https://danepubliczne.imgw.pl/api/data/synop`.
- Formats: JSON by default; API page documents XML, CSV, HTML via
  `/format/{format}`.
- Station filters: `/id/{id}` and `/station/{name}`.
- Example fields: `id_stacji`, `stacja`, `data_pomiaru`,
  `godzina_pomiaru`, `temperatura`, `predkosc_wiatru`, `kierunek_wiatru`,
  `wilgotnosc_wzgledna`, `suma_opadu`, `cisnienie`.
- Coordinates: not present in the current endpoint response.
- Update frequency: appears near-hourly, but exact frequency must be documented
  after longer observation or official confirmation.
- Stability: stable core API, but geometry requires another source.
- Limitations: numeric values arrive as strings; some fields can be `null`;
  `godzina_pomiaru` must be combined with `data_pomiaru`.
- Cache: 10-minute MVP TTL, store raw payload and parsed rows.
- Parser: `synop`.
- Normalized model: `Station`, `Observation`.
- Status: `implemented`.

## Current Hydrological Data

- Name: current hydrological station data.
- Endpoint: `https://danepubliczne.imgw.pl/api/data/hydro`.
- Format: JSON.
- Example fields: `id_stacji`, `stacja`, `rzeka`, `wojewodztwo`, `lon`, `lat`,
  `stan_wody`, `stan_wody_data_pomiaru`, `temperatura_wody`,
  `temperatura_wody_data_pomiaru`, `przeplyw`, `przeplyw_data`,
  `zjawisko_lodowe`, `zjawisko_lodowe_data_pomiaru`, `zjawisko_zarastania`,
  `zjawisko_zarastania_data_pomiaru`.
- Coordinates: present as `lon` and `lat`.
- Update frequency: often sub-hourly/hourly per field; exact source cadence must
  be verified.
- Stability: good candidate for MVP.
- Limitations: each metric has its own timestamp; old ice/vegetation timestamps
  can coexist with current water-level timestamps.
- Cache: 10-minute MVP TTL, keep per-metric timestamps.
- Parser: `hydro`.
- Normalized model: `Station`, `Observation`.
- Status: `implemented`.

## Current Meteorological Data

- Name: current meteorological station data.
- Endpoint: `https://danepubliczne.imgw.pl/api/data/meteo`.
- Format: JSON.
- Example fields: `kod_stacji`, `nazwa_stacji`, `lon`, `lat`,
  `temperatura_gruntu`, `temperatura_gruntu_data`, `temperatura_powietrza`,
  `temperatura_powietrza_data`, `wiatr_kierunek`, `wiatr_kierunek_data`,
  `wiatr_srednia_predkosc`, `wiatr_predkosc_maksymalna`,
  `wilgotnosc_wzgledna`, `opad_10min`, and per-field timestamps.
- Coordinates: present as `lon` and `lat`.
- Update frequency: appears near-10-minute for some fields, but exact cadence
  must be verified.
- Stability: good candidate for MVP.
- Limitations: many fields can be `null`; timestamps differ by metric.
- Cache: 10-minute MVP TTL.
- Parser: `meteo`.
- Normalized model: `Station`, `Observation`.
- Status: `implemented`.

## Current Meteorological Warnings

- Name: active meteorological warnings.
- Endpoint: `https://danepubliczne.imgw.pl/api/data/warningsmeteo`.
- Format: JSON.
- Example fields: `id`, `nazwa_zdarzenia`, `stopien`,
  `prawdopodobienstwo`, `obowiazuje_od`, `obowiazuje_do`, `opublikowano`,
  `tresc`, `komentarz`, `biuro`, `teryt`.
- Geometry: endpoint returns TERYT code lists, not polygon geometry.
- Update frequency: event-driven; poll every 5 minutes in MVP.
- Stability: good candidate for MVP, but geometry dependency is external.
- Limitations: requires public administrative boundaries keyed by TERYT.
- Cache: 5-minute MVP TTL.
- Parser: `warningsmeteo`.
- Normalized model: `Warning`, `WarningArea`.
- Status: `implemented`.

## Current Hydrological Warnings

- Name: active hydrological warnings.
- Endpoint: `https://danepubliczne.imgw.pl/api/data/warningshydro`.
- Format: JSON.
- Example fields: `opublikowano`, `stopień`, `data_od`, `data_do`,
  `prawdopodobienstwo`, `numer`, `biuro`, `zdarzenie`, `przebieg`,
  `komentarz`, `obszary`, `wojewodztwo`, `opis`, `kod_zlewni`.
- Geometry: basin/area codes need mapping before polygon display.
- Update frequency: event-driven; poll every 5 minutes in MVP.
- Stability: good candidate for MVP details; map polygons need more research.
- Limitations: level can be special, e.g. `-1` for hydrological drought.
  `numer` values are recycled over time, so `numer` alone is not a stable
  unique key; the parser folds `opublikowano` into the normalized warning id
  to keep ids unique.
- Cache: 5-minute MVP TTL.
- Parser: `warningshydro`.
- Normalized model: `Warning`, `WarningArea`.
- Status: `implemented`.

## Product/File API

- Name: public product list.
- Endpoint: `https://danepubliczne.imgw.pl/api/data/product`.
- Detail endpoint: `https://danepubliczne.imgw.pl/api/data/product/id/{id}`.
- Format: JSON product list; detail endpoint can return file lists.
- Example products: COSMO GRIB model products, radar-like products such as
  CAPPI/SRI identifiers.
- Update frequency: varies by product.
- Stability: mixed. COSMO detail returned file lists during research. Some
  listed radar-like IDs returned `Product could not be found`.
- Limitations: GRIB/radar formats need dedicated parsers and probably a tiling
  pipeline before map display.
- Cache: product list 60 minutes; product file manifests 30-60 minutes.
- Parser: `product_manifest`; GRIB/radar parsers are separate post-MVP work.
- Normalized model: `ProductManifest`, later `RasterProduct` or
  `ModelProduct`.
- Status: `implemented` for the manifest parser; `risky` for individual
  GRIB/radar file parsing and rendering.

Stage 10 research must classify product IDs before any product layer is exposed:

- stable and retrievable,
- listed but temporarily unavailable,
- listed but missing at the detail endpoint,
- technically risky due to binary format, projection, file size, or cadence,
- legally risky or requiring current terms review.

Research results (2026-07-01): 10 stable/retrievable IDs (8× COSMO GRIB, composite
SRI, composite CMAX), 32 listed-but-missing IDs, no distinct MERGE identifier in
the manifest. Full tables live in
[`docs/products/PRODUCT_RESEARCH.md`](docs/products/PRODUCT_RESEARCH.md).

Radar-like products such as CAPPI, SRI, and MERGE, and model/GRIB products such
as COSMO files, remain research targets only. Do not implement binary parsing,
tile generation, or map rendering until file formats, projection metadata,
licensing, cache size, retention, and attribution requirements are documented.
Stage 10 adds manifest classification APIs, cached frame metadata, a map timeline
descriptor, and a frontend timeline shell — see
[`docs/products/RASTER_PIPELINE.md`](docs/products/RASTER_PIPELINE.md).

## Archived Meteorological Warnings

- Name: archived meteorological warnings.
- Directory: `https://danepubliczne.imgw.pl/data/arch/ost_meteo/`.
- Format: indexed year/month archive directories with compressed files.
- Example structure: yearly directories from 2017 through 2026 were visible
  during research.
- Update frequency: archive updates as historical files are published.
- Stability: useful for post-MVP archive and warning-change analysis.
- Limitations: file schemas and compression layout need parser research.
- Cache: manual/daily archive manifest refresh.
- Parser: `archive_warnings_meteo`.
- Normalized model: `Warning`, `WarningRevision`.
- Status: `planned` for post-MVP.

## Archived Hydrological Warnings

- Name: archived hydrological warnings.
- Directory: `https://danepubliczne.imgw.pl/data/arch/ost_hydro/`.
- Format: indexed year/month archive directories with compressed files.
- Example structure: yearly directories from 2017 through 2026 were visible
  during research.
- Update frequency: archive updates as historical files are published.
- Stability: useful for post-MVP archive and warning-change analysis.
- Limitations: file schemas and compression layout need parser research.
- Cache: manual/daily archive manifest refresh.
- Parser: `archive_warnings_hydro`.
- Normalized model: `Warning`, `WarningRevision`.
- Status: `planned` for post-MVP.

## Measurement And Observation Archives

- Name: archived measurement and observation data.
- Directory:
  `https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/`.
- Subdirectories: `dane_meteorologiczne`, `dane_hydrologiczne`,
  `dane_aktynometryczne`, `Biuletyn_PSHM`, `Roczniki`.
- Meteorological reference files observed: `Opis.txt`, `wykaz_stacji.csv`,
  map PDFs, daily/monthly/term directories.
- Hydrological reference files observed: `lista_stacji_hydro.csv`,
  `hydrologia_info_ogolne.txt`, daily/monthly/annual directories.
- Format: CSV/TXT/PDF and nested directories; encodings may require detection.
- Update frequency: archive-specific.
- Stability: useful but larger than MVP.
- Limitations: encoding, schema variants, archive volume, and station list
  reconciliation.
- Cache: manifest-based refresh, file checksum, and parser version.
- Parser: `archive_observations`.
- Normalized model: `Station`, `Observation`, `ArchiveManifest`.
- Status: `planned` for post-MVP, with station metadata potentially useful for
  MVP synop geometry.

Stage 8 should use repeated current-source fetches and/or legally usable archive
files to build real observation history. Historical ingestion must preserve
observed timestamp, retrieval timestamp, data delay, missing/null values, source
attribution, and processed-data notices. Retention policy must be documented
before local caches grow without bounds.

## External Geometry Dependencies

MeteoLens needs public geometry datasets to render some IMGW data:

- TERYT administrative boundaries for meteorological warnings.
- Basin/catchment geometries for hydrological warning areas.
- Official station lists or documented station metadata for synop coordinates.

These datasets must be documented here before implementation and must pass the
same legal/attribution review as IMGW data.

Stage 13 status (full review in `docs/geometry/GEOMETRY_SOURCES.md`):

- `teryt_voivodeships`, `teryt_counties`: **implemented**. Source: Państwowy
  Rejestr Granic (PRG), © GUGiK — free public data under art. 40a ust. 2 pkt 1
  Prawa geodezyjnego i kartograficznego; converted from the GIS Support SHP
  mirror (2022 snapshot, EPSG:2180 → WGS84), simplified with Douglas-Peucker
  (500 m / 200 m) by `scripts/geometry/convert_prg_shapefiles.py`, and imported
  as a reviewed, validated derivative into `data/geometry/`. Attribution:
  "Granice administracyjne: PRG, © GUGiK; kopia SHP: gis-support.pl;
  uproszczenie geometrii: MeteoLens."
- `hydro_basins`: planned. Candidate MPHP (PGW Wody Polskie); licensing and
  IMGW `kod_zlewni` mapping unverified — hydro warnings stay list-only.
- `synop_stations`: planned. IMGW `wykaz_stacji.csv` has no coordinates;
  candidate WMO OSCAR/Surface (WIGOS `0-20000-0-12xxx` matches IMGW
  `id_stacji`). The backend enrichment mechanism is implemented; synop stations
  stay off the map until a reviewed dataset is imported.

Stage 9 source research must document candidate datasets with:

- provider and canonical URL,
- dataset version or publication date,
- license/terms and attribution text,
- whether public and commercial use are allowed,
- update cadence and expected cache/refresh process,
- geometry format and coordinate reference system,
- code system and mapping key, such as TERYT, basin code, or station ID,
- known gaps and unresolved mapping behavior,
- implementation status: `planned`, `implemented`, `risky`, or `blocked`.

No unofficial or legally unclear geometry dataset should be treated as an
implemented source. If a warning area or station cannot be resolved to reviewed
geometry, API and UI metadata must show the missing mapping explicitly.
