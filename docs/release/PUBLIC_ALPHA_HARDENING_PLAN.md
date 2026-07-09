# Public Alpha Hardening Plan

This is a planning document. It describes work that must happen before an
unrestricted public MeteoLens deployment is considered release-ready. It does
not claim that the controls below already exist.

## Why This Exists

MeteoLens is suitable as a public repository: it uses public IMGW-PIB data,
keeps source attribution visible, documents known limitations, and has an
auditable staged implementation history through Stage 18.

An unrestricted public deployment is a different risk profile. The current app
can perform expensive server-side work: daily SYNOP archive backfill writes into
local history, and COSMO product rendering can download an approximately 160 MB
GRIB file and perform CPU-heavy decoding/rendering on first request. The
production stack also needs explicit proxy limits, container hardening,
workflow restrictions, monitoring, backups, and a fresh validation run against
the current `main` branch before tagging `v0.1.0-alpha`.

The 2026-07-03 smoke-test record remains useful historical evidence, but it
predates bundled PRG geometry, COSMO product rendering, daily SYNOP archive
backfill, public API/client/export stabilization, and bundled WMO
OSCAR/Surface SYNOP station coordinates.

## Main Abuse And Failure Scenarios

- Anonymous users repeatedly call archive backfill and mutate `/data`.
- Anonymous users repeatedly request uncached COSMO renders and force large
  downloads or CPU-heavy rendering.
- Multiple product renders or imports exhaust disk, memory, CPU, or IMGW
  goodwill.
- Large or malformed requests tie up backend or proxy workers.
- Public comments trigger Claude or OpenCode workflows backed by paid
  credentials.
- Workflow dependencies or actions drift because versions are not pinned tightly
  enough.
- The backend container runs with more privileges than needed.
- `/data` is lost or corrupted without a tested backup and restore path.
- Operators cannot identify stale sources, parser failures, failed imports,
  cache exhaustion, or render failures without reading raw container output.
- Request logs expose secrets or unnecessary sensitive location data.

## Endpoint Categories

Public read endpoints are expected to stay unauthenticated but bounded:

- `GET /health`
- `GET /api/v1/sources`
- `GET /api/v1/map/layers`
- `GET /api/v1/stations`
- `GET /api/v1/stations/{id}`
- `GET /api/v1/stations/{id}/observations`
- `GET /api/v1/stations/compare`
- `GET /api/v1/rankings`
- `GET /api/v1/warnings`
- `GET /api/v1/warnings/{id}`
- `GET /api/v1/location/summary`
- `GET /api/v1/geometry/datasets`
- `GET /api/v1/status/freshness`
- `GET /api/v1/compare/warning-station/{station_id}`
- public export endpoints
- `GET /api/v1/products`
- `GET /api/v1/products/{product_id}/frames`
- `GET /api/v1/map/timeline`

Expensive endpoints may remain public only with stricter rate, concurrency, and
cache controls:

- `GET /api/v1/products/{product_id}/render/{file}`
- large exports or history queries when they approach configured limits

Administrative endpoints must not be anonymously available in public
deployments:

- `POST /api/v1/archive/backfill/synop-daily`
- future archive backfill endpoints
- future manual refresh, import, or cache-management endpoints

Stage 19 should turn this classification into testable backend/proxy behavior.

## Stage 19-21 Sequence

Stage 19 - Public Internet Security And Abuse Protection:

- protect or disable administrative imports by default,
- add admin authentication for administrative operations,
- add per-IP and route-specific rate limits,
- bound expensive product rendering and concurrent work,
- harden nginx, CORS, security headers, and production container privileges,
- restrict credential-backed AI workflows to trusted actors,
- add dependency, secret, and container scanning,
- document security and privacy limitations.

Stage 20 - Production Observability, Backup And Recovery:

- separate liveness and readiness,
- monitor IMGW freshness, parser failures, refreshes, product renders, imports,
  cache hits, and resource usage,
- make logs structured, rotation-safe, and privacy-aware,
- document `/data` backup scope,
- record a restore test,
- document upgrade, rollback, incident-response, and troubleshooting steps.

Stage 21 - Current-Main Production Validation And `v0.1.0-alpha` Release:

- rerun local and production smoke tests against the release commit,
- verify fresh-volume and persistent-volume upgrade paths,
- cover Stage 13-20 behavior,
- update screenshots and release notes,
- move `CHANGELOG.md` entries only when the release is actually cut,
- tag `v0.1.0-alpha` and create a GitHub prerelease.

## Release Gates

- Unauthenticated users cannot trigger administrative archive imports.
- Expensive product rendering is bounded and cannot be trivially multiplied.
- Public users cannot trigger credential-backed AI workflows unless explicitly
  allowed.
- The backend production container does not run as root.
- Production HTTP safeguards are documented and testable.
- Operators can identify stale or failed sources without raw container output.
- Disk and resource exhaustion risks are visible.
- `/data` can be backed up and restored through documented commands.
- A restore test is recorded.
- A production smoke-test record exists for the current release commit.
- Fresh install and persistent-volume upgrade paths pass.
- Known limitations remain prominent, and the release stays clearly labelled
  alpha.

## Rollout Strategy

1. Land Stage 19 as its own implementation PR with tests for endpoint
   protection, expensive-route bounds, workflow restrictions, proxy safeguards,
   and container hardening.
2. Land Stage 20 as its own implementation PR with monitoring, logging,
   resource-limit, backup, restore, and runbook updates.
3. Run Stage 21 validation from current `main` after Stages 19-20 merge.
4. Publish only a prerelease, with alpha limitations and deployer legal-review
   responsibilities visible.
5. Treat public demo exposure as an operator decision gated by
   `deploy/PRODUCTION_CHECKLIST.md`.

## Rollback Strategy

- Keep the previous production image tag available until the new release has
  passed smoke checks.
- Back up `/data` before deployment, upgrade, archive import, or large product
  cache changes.
- Record the active commit SHA, image IDs, environment file, Docker version,
  Compose version, and volume name before release validation.
- If deployment fails, stop the new stack, restore the previous image and
  environment, restore `/data` only if the failure corrupted persistent state,
  and rerun `/health`, `/api/v1/sources`, map load, export, and attribution
  checks.
- If source terms, workflow permissions, or endpoint protections are uncertain,
  keep the instance private or behind trusted access until resolved.

## Accepted Alpha Limitations

- MeteoLens is not an official warning service.
- Hydro basin polygons are not implemented until a reviewed basin dataset and
  `kod_zlewni` mapping are available.
- Hydrological archive imports beyond daily SYNOP are not implemented until the
  formats and quality/status metadata are verified.
- Radar rendering is not implemented while IMGW radar file downloads remain
  blocked at the source.
- WMO OSCAR/Surface SYNOP coordinates are reviewed for public use, but
  commercial deployments must re-review current WMO/OSCAR terms.
- The reference deployment remains Docker Compose for a small self-hosted
  instance, not a Kubernetes-scale platform.
- Local browser alert rules and comparisons remain convenience tools, not
  official alert delivery.

## Deferred Until After `v0.1.0-alpha`

- Stage 22 hydro basin geometry MVP.
- Stage 23 hydrological archive backfill.
- Stage 24 warning history and change timeline.
- Stage 25 deeper performance and scalability hardening beyond the release
  blockers.
- Stage 26 PDF reports and shareable weather briefings.
- Additional public data sources after source/legal review.
