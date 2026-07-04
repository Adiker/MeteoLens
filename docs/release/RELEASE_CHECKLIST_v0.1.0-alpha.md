# v0.1.0-alpha release checklist

Short checklist for tagging and publishing the first public alpha. Deployment
hardening items live in `deploy/PRODUCTION_CHECKLIST.md`; this list covers the
release itself.

## Before tagging

- [x] Backend tests green (`cd backend && .venv/bin/pytest`) — 123 passed.
- [x] Backend lint green (`.venv/bin/ruff check .`).
- [x] Frontend tests green (`cd frontend && npm test`) — 74 passed.
- [x] Frontend lint green (`npm run lint`).
- [x] Local development smoke test recorded against live IMGW data
  (`docs/release/SMOKE_TEST_2026-07-03.md`).
- [x] Production smoke test recorded, public HTTP port verified open
  (`docs/release/SMOKE_TEST_2026-07-03.md`).
- [x] Populated-cache screenshots captured from real IMGW-backed data with
  visible attribution (`docs/screenshots/`, referenced from `README.md`).
- [x] `README.md` states public-alpha status and keeps Known Limitations
  visible.
- [x] `README.md`, `TASKS.md`, `CHANGELOG.md`, and
  `deploy/PRODUCTION_CHECKLIST.md` describe the same alpha readiness state.

## Tagging

- [ ] Update `CHANGELOG.md`: move the `Unreleased` entries under a
  `## 0.1.0-alpha - <date>` heading.
- [ ] Tag the release commit: `git tag v0.1.0-alpha && git push origin v0.1.0-alpha`.
- [ ] Create the GitHub release, marked as a pre-release, linking the
  smoke-test record and the Known Limitations section.

## After tagging

- [ ] Verify the release notes render the screenshots and attribution
  correctly on GitHub.
- [ ] If a public demo instance is deployed, walk through
  `deploy/PRODUCTION_CHECKLIST.md` on the target host (legal review of current
  IMGW-PIB terms stays with the deployer).
