# IMGW Product And Radar Research

Research dates: **2026-07-01** (catalog classification), **2026-07-05**
(download-path verification for Stage 14)

This document classifies public IMGW-PIB `api/data/product` identifiers and
records which product paths are actually downloadable. As of Stage 14 MeteoLens
renders one product path (COSMO 2 m temperature) as a real map layer; all other
products remain metadata/timeline only.

## Stage 14 Download Verification (2026-07-05)

Live probes against `danepubliczne.imgw.pl` produced two decisive findings:

1. **Radar composite files are not publicly downloadable.** Every
   `getfiledown` URL from the `COMPO_SRI.comp.sri` and
   `COMPO_CMAX_250.comp.cmax` detail manifests — including the
   `*_echoOnly.png` previews — responds `307 Temporary Redirect` to the HTML
   datastore page, with or without a `ci_session` cookie, browser headers,
   referer, or the datastore regulations flow (which is purely client-side
   `localStorage`). The datastore's own file listing
   (`POST /pl/datastore/getFilesList`) emits malformed relative links
   (`datastore/getfiledownOper/...`, missing slash) that return CodeIgniter
   404 pages. Treat the radar composite path as **blocked at the source** until
   IMGW fixes public file delivery; rendering status is `download_blocked`.
2. **COSMO GRIB files download correctly.** The same `getfiledown` route
   serves `Oper/COSMO/...` files with HTTP 200: `readme.txt` as `text/plain`
   and forecast files as `application/*` GRIB1 binaries (verified magic
   `GRIB`, edition 1; the constant-field file `lfff00000000c` was ~19.7 MB).

The COSMO `readme.txt` fully documents the format and grid, which unblocks the
Stage 14 rendering guardrail (documented format + projection):

- Format: **GRIB1**, one record per field/level, simple packing.
- Grid: **rotated lat/lon** (GRIB1 data representation type 10), pole at
  lon **-170°**, lat **32.5°**, origin lon 10°E / lat 57.5°N, first rotated
  point lon **-10°** / lat **-19°**, `dlon = dlat = 0.0625°`,
  **415 × 460** points, 40 model levels.
- Record catalog is enumerated in the readme; the Stage 14 MVP renders
  **2 m air temperature** (record 365: parameter 11, level type 105, level 2).
- Runs at 00/06/12/18 UTC, 60 h length, hourly steps; filenames encode
  `run_time`, `valid_time`, and the `lfffDDHHMMSS` lead (plus a `...c`
  constant-field file per run that must not be treated as a forecast frame).

Legal basis recorded from `danepubliczne.imgw.pl/pl/apiinfo`: data are made
available under the Polish open-data act (ustawa z 11.08.2021 o otwartych
danych) with IMGW-PIB as the distributing institute; reuse is permitted with
source attribution, which MeteoLens shows together with the processed-data
notice on every rendered view.

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
- **2026-07-05 update:** direct downloads are confirmed blocked — every file
  URL (binaries and PNG previews alike) 307-redirects to the datastore HTML
  page regardless of session, referer, or browser-like headers. See
  "Stage 14 Download Verification" above. Rendering status is
  `download_blocked`.

Technical risks:

- Proprietary formats; no open parser in MeteoLens yet.
- High cadence and large manifests require pagination and cache caps.
- PNG previews cannot be prototyped until IMGW restores public file delivery,
  and they still need projection metadata.

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

## MeteoLens Behavior (Stage 10 + Stage 14)

Implemented now:

- `GET /api/v1/products` — manifest + research classification
- `GET /api/v1/products/{id}/frames` — frame metadata parsed from cached manifest files
- `GET /api/v1/products/{id}/render/{filename}` — rendered PNG overlay for
  renderable COSMO frames (2 m temperature), server-side download + render
  cache with retention limits
- `GET /api/v1/map/timeline` — time-aware layer descriptors; COSMO layers
  carry `frames_renderable=true` plus image bounds and a render URL template
- Scheduled refresh of detail manifests for configured product IDs
- Frontend timeline with play/pause/step and a MapLibre image overlay for
  renderable frames; explicit metadata-only labels remain for everything else

Still deferred:

- Radar composite rendering (blocked at the source; see download verification)
- Full multi-variable GRIB decoding, tile pyramids, GeoTIFF exports

See also: [RASTER_PIPELINE.md](./RASTER_PIPELINE.md).
