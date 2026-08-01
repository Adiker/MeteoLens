# Stage 24 Validation - 2026-07-27

## Scope

This record validates prospective warning history for the live IMGW-PIB
`warningsmeteo` and `warningshydro` JSON sources. Stage 24 does not import the
separate monthly warning archive families and does not correlate warning
changes with station observations. Every API, UI, and export surface exposes
the local `history_started_at` completeness boundary.

## Identity And Snapshot Integrity

Automated coverage proves:

- additive, idempotent initialization preserves existing observation history;
- each parsed refresh writes the snapshot, members, versions, histories, and
  events in one transaction, with an injected failure rolling back all rows;
- meteo identity is exact source plus `id`; hydro identity is exact source plus
  `numer` plus `biuro`;
- missing identity components remain in separate ambiguous histories and are
  never joined by phenomenon, text, or area;
- identical duplicates collapse and are counted, while conflicting duplicates
  remain visible without advancing the affected history; repeated persistence
  of the same deduplicated snapshot does not manufacture another conflict event;
- snapshot identity includes parser warnings and duplicate-quality counters, so
  changes in source quality remain auditable instead of being overwritten;
- pruning a closed history never permits its public history identifier to be
  reused, because the per-identity generation ledger survives retention cleanup;
- the first successful snapshot produces `first_observed`, not a fabricated
  issue event, and an identical refresh creates no new version or event;
- creation, appearance, update, extension, escalation, downgrade, finite
  expiry, two-complete-snapshot removal, reappearance, explicit structured
  cancellation/correction, and duplicate conflict are deterministic and
  covered;
- hydrological level `-1` and open-ended validity are not misclassified by
  numeric level or finite-expiry rules;
- partial snapshots preserve valid records but cannot close missing histories;
- source fetch/parser failures and `404` responses do not create snapshots or
  mutate retained history.

## API, UI, Export, And Retention Evidence

The tests cover exact event filters, stable opaque-cursor pagination, empty and
error states, current-warning history links, retained detail after a cache
record disappears, CSV/JSON parity, attribution, processed-data notice, local
completeness boundary, ambiguity, and the official-warning disclaimer.

The React tests cover the `Aktywne`/`Historia` browser, filters, permalink
round-trip with validated dates and change kinds, accessible tab state, current
and retained historical detail, conflict-only detail without an arbitrary
current version, vertical before/after timeline, and simple/expert views. Date
filters cover full calendar days in `Europe/Warsaw`, including DST boundaries.
Playwright drives the real API and seeded SQLite history through a filtered
`removed_from_source` event into its retained timeline.

The prune command is dry-run by default, requires `--confirm`, deletes only
whole closed histories older than `--before`, preserves active histories,
reports history/version/snapshot/event counts, and rolls back an injected
failure. The existing essential backup/verify/restore test now verifies a
warning-history row in the restored SQLite database.

Concurrent synchronous API requests use separate thread-affine connections to
the same SQLite file. A regression test proves two worker threads receive
distinct connection objects and observe the same committed warning-history
state.

## Real-Source Smoke

Two consecutive refreshes of each live warning endpoint ran against an isolated
temporary cache and SQLite database, removed automatically after the check:

```text
warningsmeteo: error/error (HTTP 404)
after first:  histories=0 versions=0 events=0 snapshots=0
after second: histories=0 versions=0 events=0 snapshots=0

warningshydro: success/success
after first:  histories=67 versions=67 events=67 snapshots=1
after second: histories=67 versions=67 events=67 snapshots=1
```

The live `warningsmeteo` `404` therefore behaved as a fetch failure and did not
manufacture an empty snapshot. The immediately repeated successful
`warningshydro` response was idempotent; the identical set reused its
deduplicated snapshot.

## Automated Gates

Commands and results:

```text
backend: uv run --python 3.12 pytest -q       291 passed
backend: uv run --python 3.12 ruff check .    passed
frontend: npm test -- --run                  101 passed
frontend: npm run lint                        passed
frontend: npm run build                       passed
frontend: npm run test:e2e                    6 passed
TypeScript client: tsc --noEmit               passed
OpenAPI client: regenerate + SHA-256 check    unchanged
production backend image: docker build        passed
production Compose + Prometheus config        passed
repository: git diff --check                  passed
```

Non-blocking toolchain notices were the existing Starlette `TestClient`
deprecation warning, Vite's existing large chart-chunk advisory, and the
existing `npm ci` report of two high-severity dependency findings. Stage 25
retains responsibility for measured performance work; dependency remediation
should be handled separately rather than by an unreviewed forced update.

## Acceptance

Stage 24 acceptance criteria are met for prospective live-source history.
Official warning archives remain a documented future extension, disappearance
without an explicit source signal remains labelled unconfirmed, and MeteoLens
continues to state that it is not an official warning service. Approval still
requires review of the complete diff; this validation record does not replace
that review.
