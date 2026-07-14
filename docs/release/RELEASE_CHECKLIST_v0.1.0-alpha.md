# v0.1.0-alpha release checklist

Short checklist for tagging and publishing the first public alpha. Deployment
hardening items live in `deploy/PRODUCTION_CHECKLIST.md`; this list covers the
release itself.

The 2026-07-03 smoke-test record is a useful historical baseline, but it
predates bundled PRG geometry, COSMO rendering, daily SYNOP archive backfill,
public API/client/export work, and bundled WMO OSCAR/Surface SYNOP coordinates.
The current validation record is
[`STAGE_21_VALIDATION_2026-07-14.md`](STAGE_21_VALIDATION_2026-07-14.md).
Do not tag `v0.1.0-alpha` until its pre-tag checks have been repeated for the
exact release commit.

## Before tagging

- [x] Stage 19 public-internet security and abuse-protection acceptance
  criteria are met.
- [x] Stage 20 production observability, backup, and recovery acceptance
  criteria are met.
- [x] Backend tests green against the validated current-main commit.
- [x] Backend lint green against the validated current-main commit.
- [x] Frontend tests green against the validated current-main commit.
- [x] Frontend lint green against the validated current-main commit.
- [x] Frontend production build green against the validated current-main commit.
- [x] E2E tests green against the validated current-main commit.
- [x] Current-main local development smoke test recorded against live IMGW data.
- [x] Current-main production smoke test recorded against live IMGW data,
  including exact commit SHA, date, Docker version, Compose version, and test
  environment.
- [x] Fresh named-volume production install passes.
- [x] Upgrade from an existing pre-Stage-18 volume passes.
- [x] Bundled PRG geometry and meteo warning polygons verified.
- [x] Bundled SYNOP station coordinates, map markers, and `coordinate_source`
  metadata verified.
- [x] Explicit missing hydro basin geometry verified.
- [x] One real COSMO temperature frame render verified.
- [x] Cached replay of the rendered COSMO frame verified.
- [x] Render failure and IMGW source-unavailable states verified.
- [x] Bounded archive backfill verified.
- [x] Live/archive/mixed observation series verified with real IMGW station
  identifiers. The reviewed mapping resolved `NSP=349190600` to
  `id_stacji=12600`; the 2026-07-14 limited live follow-up returned `mixed` with
  `origin_counts={"archive_import":1,"live_refresh":1}`. Final pre-tag
  current-main validation remains required.
- [x] Exports, attribution, processed-data notices, and known limitations
  verified.
- [x] Backup and restore procedure verified and recorded.
- [x] Small abuse/load smoke test for expensive routes recorded.
- [x] Claude and OpenCode workflows restricted to trusted actors or repository
  collaborators.
- [x] Public users cannot trigger credential-backed AI workflows unless
  explicitly allowed.
- [x] Backend production container runs as a non-root user.
- [x] Production proxy safeguards, TLS/security headers, CORS, rate limits, and
  endpoint protections are documented and testable.
- [x] Current attribution and legal review checked, including IMGW-PIB, PRG/GUGiK,
  and WMO OSCAR/Surface limitations.
- [x] Populated-cache screenshots updated from current implementation with
  visible attribution.
- [x] `README.md` states public-alpha candidate status and keeps Known Limitations
  visible.
- [x] `README.md`, `TASKS.md`, `ROADMAP.md`, `CHANGELOG.md`, and
  `deploy/PRODUCTION_CHECKLIST.md` describe the same release-readiness state.
- [x] `SECURITY.md` exists or the vulnerability-reporting policy is documented
  in the release notes.

## Tagging

- [ ] Update `CHANGELOG.md`: move the relevant `Unreleased` entries under a
  `## 0.1.0-alpha - <date>` heading.
- [x] Align backend and frontend version metadata with the alpha candidate;
  README remains deliberately labelled as a candidate until tagging.
- [ ] Tag the release commit: `git tag v0.1.0-alpha && git push origin v0.1.0-alpha`.
- [ ] Create the GitHub release, marked as a pre-release, linking the
  smoke-test record and the Known Limitations section.

## After tagging

- [ ] Verify the release notes render the screenshots and attribution
  correctly on GitHub.
- [ ] If a public demo instance is deployed, walk through
  `deploy/PRODUCTION_CHECKLIST.md` on the target host (legal review of current
  IMGW-PIB terms stays with the deployer).
- [ ] Verify rollback steps from the release record.
