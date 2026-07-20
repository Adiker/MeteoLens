# Stage 21 pre-tag suite — 2026-07-20

## Scope

Final automated pre-tag checks for cutting `v0.1.0-alpha`. This record
complements the live Compose validation in
[`STAGE_21_VALIDATION_2026-07-14.md`](STAGE_21_VALIDATION_2026-07-14.md) and
the reviewed SYNOP identifier reconciliation follow-up documented there. It
does not replace a per-host walkthrough of `deploy/PRODUCTION_CHECKLIST.md`.

## Environment

| Item | Value |
| --- | --- |
| Application base commit | `f4624e48afd8a48eb946d131239d2baef235a0a8` |
| Date (UTC) | 2026-07-20 |
| Host | Linux 7.1.4-arch1-1 x86_64 |
| Docker | 29.6.2 (build `dfc4efb1e2`) |
| Docker Compose | 5.3.1 |

Runtime behavior on this base commit already includes Stage 19-20 hardening,
the Stage 21 live validation path, SYNOP archive/`id_stacji` reconciliation,
archive ZIP resource caps, and product-render URL validation. The release cut
itself is documentation and publication only.

## Automated suite

| Area | Command / result |
| --- | --- |
| Backend lint | `cd backend && .venv/bin/ruff check .` — PASS |
| Backend tests | `cd backend && .venv/bin/pytest` — PASS, 249 tests |
| Frontend lint | `cd frontend && npm run lint` — PASS |
| Frontend unit tests | `cd frontend && npm test -- --run` — PASS, 87 tests |
| Production frontend build | `cd frontend && npm run build` — PASS; existing large-chunk warning retained as Stage 25 work |
| End-to-end fixtures | `cd frontend && npm run test:e2e` — PASS, 5 tests |

## Live Compose evidence retained

The 2026-07-14 live development and nginx production smoke tests, fresh-volume
and upgrade-path checks, COSMO render/cache, source-outage, bounded archive,
abuse-limit, and backup/restore evidence remain the authoritative live record.
The SYNOP live/archive mapping follow-up on that date removed the former
release blocker (`NSP=349190600` → `id_stacji=12600`, `series_origin=mixed`).

## Release actions covered by this cut

- Move `CHANGELOG.md` entries into a dated `0.1.0-alpha` section.
- Align README / roadmap / task status with the tagged alpha.
- Tag `v0.1.0-alpha` and publish a GitHub prerelease linking this record,
  the 2026-07-14 validation, release notes, screenshots, license, attribution,
  and known limitations.
