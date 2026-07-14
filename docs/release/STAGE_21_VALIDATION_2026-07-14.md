# Stage 21 current-main validation — 2026-07-14

## Scope and release state

This is the current-main validation record for the untagged
`v0.1.0-alpha` candidate. It is evidence for the Stage 21 gate, not a release
publication or public-demo approval. The exact validated application commit was
`0c8d6fd1331c969ffa02bf1e88a9708fe4241107` (2026-07-14).

The validation ran on Linux with Docker 29.6.1 (build `8900f1d330`) and Docker
Compose 5.3.1. It used isolated Compose project names, non-default loopback
ports, temporary worktrees, named volumes, and live public IMGW-PIB data. No
production credentials or persistent user data were committed to the repository.

## Automated checks

| Area | Command / result |
| --- | --- |
| Backend lint | `cd backend && uv run ruff check .` — PASS |
| Backend tests | `cd backend && uv run pytest` — PASS, 212 tests |
| Frontend lint | `cd frontend && npm run lint` — PASS |
| Frontend unit tests | `cd frontend && npm test` — PASS, 87 tests |
| Production frontend build | `cd frontend && npm run build` — PASS; existing large-chunk warning retained as Stage 25 performance work |
| End-to-end fixtures | `cd frontend && npm run test:e2e` — PASS, 5 tests |
| Production config | `docker compose --env-file .env.production -f docker-compose.prod.yml config` and `promtool check config` — PASS |
| Validation helper | `python3 -m py_compile scripts/release/stage21_validate.py` — PASS |

The release helper is intentionally stdlib-only. It records compact JSON
evidence and exercises only the explicitly supplied endpoint; it does not start
containers, mutate volumes, or publish Git objects.

## Live development and production smoke tests

Development Compose ran from the validated commit with
`BACKEND_PORT=18020 FRONTEND_PORT=15173`. The browser origin was
`http://localhost:15173`, matching the configured CORS origin. The backend
started with all six IMGW cache families fresh: SYNOP 62, hydro 913, meteo 785,
meteorological warnings 8, hydrological warnings 80, and product manifest 42.

`frontend/scripts/smoke.mjs` ran in Stage 21 mode against both the development
stack and the nginx production stack. Each run passed 13/13 checks, including
live attribution, station search/details, retrieval time and delay, expert raw
metadata, reviewed SYNOP `coordinate_source`, exports, warning validity and
geometry state, map PNG export, and the power-user panel.

The fresh production project exposed nginx on loopback port 18021, retained no
published backend port, and returned `0.1.0-alpha` from readiness. A direct
in-app visual check confirmed 62 SYNOP markers, 169 resolved meteorological
warning polygons, and 554 hydrological warnings explicitly reported without
geometry. The refreshed screenshots in `docs/screenshots/` come from that live
cache and keep IMGW-PIB attribution and the processed-data notice visible.

## Production data and behavior checks

| Check | Result |
| --- | --- |
| Bundled geometry | PASS: `synop_stations` 62, `teryt_counties` 380, `teryt_voivodeships` 16 loaded |
| Hydro basin limitation | PASS: `hydro_basins` not bundled; hydro warning geometry remains explicit |
| SYNOP coordinates | PASS: 62 enriched SYNOP records with reviewed source attribution |
| Exports | PASS: station/observation JSON, map/warning GeoJSON and map-state carry attribution + processed notice; CSV has metadata columns |
| COSMO render | PASS: two concurrent cold requests returned identical PNG, 234,209 bytes, SHA-256 `b21a2a77de920951f3f10601db798e4e0cfc046c4548dee5c35184a31bcd6859`, then cached replay passed |
| Render metrics | PASS: private Prometheus scrape observed one miss and two cache hits |
| Source outage | PASS: forcing the IMGW base to an unavailable local address made readiness `degraded`, marked caches stale, and still served a cached station; normal source then recovered |
| Archive protection | PASS: disabled archive endpoint returned 403; configured endpoint returned 401 without its header, completed a bounded 2026-05-04 SYNOP import (57 rows / 570 archive observations) with admin authorization, then returned 429 with `Retry-After` on repeat |
| Expensive-route abuse smoke | PASS: a 15-request cached render burst produced nginx rate limiting (503s) without another cold download |

`/metrics` is intentionally not exposed via the public nginx route; it falls
through to the SPA while the private Prometheus profile scrapes `backend:8000`.

### Original release blocker: real SYNOP live/archive reconciliation

The bounded archive import did persist 570 `archive_import` observations and a
current station returned `live_refresh` history. However, real current SYNOP
records use IMGW `id_stacji` (for example `synop:12295`), while the daily
archive uses its own `NSP` identifier (for example `synop:349190600`). The two
identifiers were not reconciled, so no real station returned a `mixed` series.
Fixture tests cover the repository's mixed-series representation once identifiers
match, but they do not prove this source reconciliation. Name matching or
hardcoded IDs would violate the project's data guardrails. A reviewed,
documented mapping source and a repeatable import are required before release.

### Reconciliation follow-up — 2026-07-14

The blocker above is resolved in `fix/stage21-synop-id-reconciliation` by a
versioned mapping generated from two official IMGW-PIB inputs:

- `wykaz_stacji.csv`, whose documented columns contain archive `NSP`, station
  name, and the separate station code;
- `/api/data/synop`, which contains the current `id_stacji` values.

The importer derives a block-12 candidate only from the source station code and
requires an exact current `id_stacji`. It never compares station names. The
committed `2026-07-14` artifact records source URLs, retrieval times, hashes,
method, review status, 2,176 source records / 2,173 unique `NSP` entries, 61
mapped current stations, and one current station (`12001`, `Platforma`) without
an archive catalogue entry. Duplicate catalogue rows are grouped; multiple
current candidates fail artifact generation. Unmapped archive records remain
under `synop-archive:<NSP>` with parser warnings and mapping metadata.

A limited isolated live-data check then:

- refreshed only current SYNOP: PASS, 62 records, no parser warnings;
- imported only 2026-05-04: PASS, one ZIP, 57 archive rows / 570 observations;
- retained one archive station without a current map as
  `synop-archive:349200628` with `unmapped_not_current_synop`;
- queried `synop:12600` (`NSP=349190600`) for `temperature`: PASS,
  `series_kind=history`, `series_origin=mixed`,
  `origin_counts={"archive_import": 1, "live_refresh": 1}`;
- verified the archive point exposed `source_station_id=349190600`,
  `station_mapping_status=mapped`, and `station_mapping_version=2026-07-14`.

This follow-up removes the identifier blocker. It is deliberately narrower
than the original production validation and does not authorize tagging: the
affected automated checks and final pre-tag suite still need to pass on the
exact merged commit.

Follow-up automated checks on the fix branch passed: backend Ruff and 219
pytest tests; frontend ESLint, 87 Vitest tests, and production build; and five
Playwright E2E tests. The existing Stage 25 large-chunk build warning remains.

## Fresh install, upgrade, and recovery

- Fresh named-volume production install: PASS. Health and all six source caches
  were usable after startup.
- Persistent-volume upgrade: PASS. A Stage 17 volume was created from commit
  `3e59799c0aadc689655c5a84ffd635c73a288693`, then started by the validated
  runtime image. `data-init` merged bundled SYNOP geometry; readiness was
  `0.1.0-alpha`, all three reviewed geometry datasets loaded, and the backend
  process ran as UID/GID 10001.
- Backup: PASS. The essential `/data` archive was created and verified before
  restore; SHA-256
  `91b08740cce9bb5a1bcb358aa81581506d538c0fe5a8ce41b5eccea87beb30a0`.
- Restore: PASS. A separate production project restored the archive with
  refresh disabled, returned ready health, loaded all reviewed geometry, and
  SQLite `PRAGMA integrity_check` returned `ok`.

## Legal, attribution, and release limitations

Attribution and processed-data notices were checked in the UI and exports.
The maintainers re-checked the public IMGW-PIB data portal and the documented
PRG/GUGiK and WMO OSCAR/Surface source records. This confirms the repository's
documentation is current enough for the candidate; it is not a legal opinion
or blanket permission. Every deployer must review current source terms before
public or commercial use, as required by `LEGAL_ATTRIBUTION.md` and
`deploy/PRODUCTION_CHECKLIST.md`.

The known alpha limits remain unchanged: hydro basin polygons are absent,
non-SYNOP archive families are not backfilled, radar files are unavailable for
rendering, only the documented COSMO temperature path is renderable, and this
small Compose deployment is not a substitute for an official warning service.
SYNOP reconciliation is bounded to reviewed map entries; missing and future
identifiers remain explicit archive-only records rather than guessed matches.

## Rollback

Before a later tag/deployment, record the previous image/commit, environment
file permissions, named-volume name, and a verified `/data` backup. If the new
stack fails, stop that stack, restore the prior image and environment, and
restore `/data` only when persistent state is actually damaged. Then repeat
`/health`, `/health/ready`, `/api/v1/sources`, a map load, an export, and the
visible attribution check. The pre-Stage-21 baseline used here was main commit
`33963ddc15a7d5ba4784d3f59528b9b680072dc9`.

## Remaining release actions

No tag, GitHub release, or public-demo approval was created during this work.
Before publishing, rerun the affected checks plus the small pre-tag suite
against the exact final merged commit, move `CHANGELOG.md` entries to a dated
`0.1.0-alpha` section, tag that commit, create a GitHub prerelease, and verify
the rendered release notes.
