# IMGW Product And Radar Research

Research date: **2026-07-01**

This document classifies public IMGW-PIB `api/data/product` identifiers before any
binary parser or map rendering work begins. MeteoLens currently exposes manifest
metadata, parsed frame timestamps, and a timeline UI shell only.

## Summary

| Status | Count | Meaning |
| --- | ---: | --- |
| `stable_retrievable` | 10 | Listed in manifest and detail endpoint returns a file list |
| `listed_missing` | 32 | Listed in manifest but detail endpoint returned HTTP 404 |
| Total manifest entries | 42 | From live `GET /api/data/product` on 2026-07-01 |

High-value stable products:

- **8× COSMO GRIB model runs** (`COSMO_HVD_*`) — ~63 forecast-lead files each
- **`COMPO_SRI.comp.sri`** — ~4 380 recent SRI composite frames
- **`COMPO_CMAX_250.comp.cmax`** — ~4 320 recent CMAX composite frames

## Stable And Retrievable Products

### GRIB / model (`grib_model`)

| Product ID | Description | Files (sample) | Format notes |
| --- | --- | ---: | --- |
| `COSMO_HVD_00_00` | Prognoza meteo GRIB model COSMO 2k8 00/00 | 63 | Binary GRIB-like files named `{run}_{valid}_lfff{lead}` |
| `COSMO_HVD_00_01` | Prognoza meteo GRIB model COSMO 2k8 00/01 | 63 | Same pattern |
| `COSMO_HVD_06_00` | Prognoza meteo GRIB model COSMO 2k8 06/00 | 63 | Same pattern |
| `COSMO_HVD_06_01` | Prognoza meteo GRIB model COSMO 2k8 06/01 | 63 | Same pattern |
| `COSMO_HVD_12_00` | Prognoza meteo GRIB model COSMO 2k8 12/00 | 63 | Same pattern |
| `COSMO_HVD_12_01` | Prognoza meteo GRIB model COSMO 2k8 12/01 | 63 | Same pattern |
| `COSMO_HVD_18_00` | Prognoza meteo GRIB model COSMO 2k8 18/00 | 63 | Same pattern |
| `COSMO_HVD_18_01` | Prognoza meteo GRIB model COSMO 2k8 18/01 | 63 | Same pattern |

Sample manifest entry:

```json
{
  "file": "202606300000_202606300000_lfff00000000",
  "url": "https://danepubliczne.imgw.pl/pl/d/..."
}
```

Technical risks:

- Binary GRIB decoding is not implemented.
- Projection, grid extent, and variable naming are not described by the JSON API.
- Individual files can be large; bulk download needs retention and eviction rules.

Legal note: verify current IMGW-PIB terms before public redistribution of decoded
model fields or derived tiles.

### Radar-like composites (`radar_composite`)

| Product ID | Description | Files (sample) | Format notes |
| --- | --- | ---: | --- |
| `COMPO_SRI.comp.sri` | Composite SRI | 4380 | Proprietary `.sri` binaries; occasional `_echoOnly.png` previews |
| `COMPO_CMAX_250.comp.cmax` | Composite CMAX | 4320 | Proprietary `.cmax` binaries; occasional `_echoOnly.png` previews |

Sample radar filename: `2026062803300000dBR.sri`

- Frame time is encoded in the first 14 digits (`YYYYMMDDHHmmss`).
- Public HEAD/GET responses for `.sri`/`.cmax` URLs returned `text/html` during
  research, so direct file access may require additional path/session checks before
  production download.

Technical risks:

- Proprietary formats; no open parser in MeteoLens yet.
- High cadence and large manifests require pagination and cache caps.
- PNG previews may be easier to prototype but still need projection metadata.

## Listed But Missing At Detail Endpoint (`listed_missing`)

These IDs appear in the public manifest but returned
`{"status":false,"message":"Product could not be found"}` on
`GET /api/data/product/id/{id}` during research:

- Composite radar derivatives: `COMPO_CAPPI.comp.cappi_buf`,
  `COMPO_CAPPI.comp.cappi_h5`, `COMPO_EHT.comp.eht`, `COMPO_PAC.comp.pac`,
  `COMPO_SRI.comp.sri_h5`
- Per-site VVP: `brz.vvp`, `gdy.vvp`, `gsa.vvp`, `leg.vvp`, `pas.vvp`, `poz.vvp`,
  `ram.vvp`, `rze.vvp`, `swi.vvp`, `uzr.vvp`
- Per-site SRI: `*_200_leads.sri` for `gdy`, `gsa`, `leg`, `pas`, `poz`, `ram`,
  `rze`, `swi`, `uzr`
- Per-site CAPPI: `*_compo_pcz.cappi` for `brz`, `gsa`, `leg`, `pas`, `poz`, `ram`,
  `rze`, `swi`

Treat these as unstable catalog entries until IMGW restores the detail endpoint or
documents replacement IDs.

## MERGE And Other Radar Names

The manifest did not expose a distinct `MERGE` product ID on 2026-07-01. Composite
products use `COMPO_*` prefixes instead. Re-check the manifest after IMGW catalog
changes.

## MeteoLens Stage 10 Behavior

Implemented now:

- `GET /api/v1/products` — manifest + research classification
- `GET /api/v1/products/{id}/frames` — frame metadata parsed from cached manifest files
- `GET /api/v1/map/timeline` — time-aware layer descriptors for cached products
- Frontend timeline shell with explicit metadata-only / non-renderable labels

Deferred until formats, projection, licensing, and cache policy are complete:

- Binary GRIB / radar parsing
- Tile generation or GeoTIFF rendering for MapLibre
- Automatic IMGW product-detail refresh on every API request (manual/ops seeding or
  scheduled job TBD)

See also: [RASTER_PIPELINE.md](./RASTER_PIPELINE.md).
