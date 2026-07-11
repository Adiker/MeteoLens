# v0.1.0-alpha release checklist

Short checklist for tagging and publishing the first public alpha. Deployment
hardening items live in `deploy/PRODUCTION_CHECKLIST.md`; this list covers the
release itself.

The 2026-07-03 smoke-test record is a useful historical baseline, but it
predates bundled PRG geometry, COSMO rendering, daily SYNOP archive backfill,
public API/client/export work, and bundled WMO OSCAR/Surface SYNOP coordinates.
Do not tag `v0.1.0-alpha` until the current `main` branch has a fresh
production validation record and the Stage 19-20 public-deployment gates are
met.

## Before tagging

- [x] Stage 19 public-internet security and abuse-protection acceptance
  criteria are met.
- [ ] Stage 20 production observability, backup, and recovery acceptance
  criteria are met.
- [ ] Backend tests green against the release commit.
- [ ] Backend lint green against the release commit.
- [ ] Frontend tests green against the release commit.
- [ ] Frontend lint green against the release commit.
- [ ] Frontend production build green against the release commit.
- [ ] E2E tests green against the release commit.
- [ ] Current-main local development smoke test recorded against live IMGW data.
- [ ] Current-main production smoke test recorded against live IMGW data,
  including exact commit SHA, date, Docker version, Compose version, and test
  environment.
- [ ] Fresh named-volume production install passes.
- [ ] Upgrade from an existing pre-Stage-18 volume passes.
- [ ] Bundled PRG geometry and meteo warning polygons verified.
- [ ] Bundled SYNOP station coordinates, map markers, and `coordinate_source`
  metadata verified.
- [ ] Explicit missing hydro basin geometry verified.
- [ ] One real COSMO temperature frame render verified.
- [ ] Cached replay of the rendered COSMO frame verified.
- [ ] Render failure and IMGW source-unavailable states verified.
- [ ] Bounded archive backfill verified.
- [ ] Live/archive/mixed observation series verified.
- [ ] Exports, attribution, processed-data notices, and known limitations
  verified.
- [ ] Backup and restore procedure verified and recorded.
- [ ] Small abuse/load smoke test for expensive routes recorded.
- [ ] Claude and OpenCode workflows restricted to trusted actors or repository
  collaborators.
- [ ] Public users cannot trigger credential-backed AI workflows unless
  explicitly allowed.
- [ ] Backend production container runs as a non-root user.
- [ ] Production proxy safeguards, TLS/security headers, CORS, rate limits, and
  endpoint protections are documented and testable.
- [ ] Current attribution and legal review checked, including IMGW-PIB, PRG/GUGiK,
  and WMO OSCAR/Surface limitations.
- [ ] Populated-cache screenshots updated from current implementation with
  visible attribution.
- [ ] `README.md` states public-alpha status and keeps Known Limitations
  visible.
- [ ] `README.md`, `TASKS.md`, `ROADMAP.md`, `CHANGELOG.md`, and
  `deploy/PRODUCTION_CHECKLIST.md` describe the same release-readiness state.
- [ ] `SECURITY.md` exists or the vulnerability-reporting policy is documented
  in the release notes.

## Tagging

- [ ] Update `CHANGELOG.md`: move the relevant `Unreleased` entries under a
  `## 0.1.0-alpha - <date>` heading.
- [ ] Align backend, frontend, README, and release version metadata.
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
