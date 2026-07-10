# AGENTS.md - MeteoLens

Comprehensive project docs are in `ARCHITECTURE.md`. This file contains the
mandatory guardrails for AI agents and automation working in this repository.

## Git Workflow

- Never commit directly to `main` unless the user explicitly asks for it.
- Work on branches with one of these prefixes: `feature/`, `fix/`,
  `refactor/`, `docs/`, `chore/`.
- Do not force-push `main`.
- Do not delete branches without explicit consent.
- Do not rewrite published history without explicit consent.
- Before opening a PR, run the tests relevant to the changed parts.
- If tests are not available yet, state that clearly in the PR description.

## Documentation Rules

- Update `README.md` for end-user behavior, setup, exports, screenshots, and
  troubleshooting.
- Update `ARCHITECTURE.md` for backend/frontend structure, data flow, cache,
  database, public API, parser architecture, deployment, and tests.
- Update `DATA_SOURCES.md` when IMGW-PIB sources, endpoint fields, formats,
  parser status, or source risk changes.
- Update `API_CONTRACT.md` for every public backend API change.
- Update `UI_UX.md` when user-visible behavior or layout changes.
- Update `LEGAL_ATTRIBUTION.md` for attribution, licensing, or processed-data
  notice changes.
- Update `TASKS.md` when scope is completed, split, blocked, or reprioritized.
- If documentation does not need changes, say that explicitly in the PR
  description.

## IMGW Data Guardrails

- Use only public IMGW-PIB data or other data that can legally be fetched and
  processed.
- Do not add unofficial or legally risky sources without documenting the risk in
  `DATA_SOURCES.md` and `LEGAL_ATTRIBUTION.md`.
- Do not implement Blitzortung or unofficial lightning detection unless the
  licensing and usage terms are explicitly cleared first.
- Do not hardcode IMGW data as a final solution.
- Do not mask data download errors.
- Do not replace missing values with zero.
- Show missing values as missing values.
- Preserve measurement timestamp, retrieval timestamp, and data delay.
- Keep source attribution visible in UI, exports, and documentation.
- If data is normalized, aggregated, interpolated, converted, or otherwise
  transformed, show the processed-data notice.

## Parser And API Rules

- Do not mix IMGW client code, parsers, normalization, cache, and API route
  logic in one file.
- Parser changes must add or update parser tests.
- Public API responses must include source metadata and missing-field metadata.
- Keep raw IMGW payloads available for expert/debug mode when feasible.
- Avoid speculative interpolation in MVP. If interpolation is later added, make
  it opt-in and visibly labelled.

## Frontend Rules

- The map is the primary view.
- The UI must have loading, empty, and error states.
- Expert mode must expose raw JSON/source metadata for selected objects.
- Mobile details must use a bottom-sheet style layout.
- Do not hide data quality problems behind polished visuals.

## Stage Discipline

- Stage 0-1 is documentation and research only.
- Stage 2 may add scaffolding, Docker Compose, healthchecks, and basic tests.
- Stage 3 may add IMGW clients/parsers/cache.
- Stage 4 may add public backend API endpoints.
- Stage 5 may add the usable frontend.
- Stage 6 is quality, test expansion, and known-limitations cleanup.
- Stage 7 may harden production deployment and public-demo operations.
- Stage 8 may add local observation history and real time-series behavior.
- Stage 9 may add geometry pipelines and spatial warning behavior, but only for
  reviewed geometry data.
- Stage 10 may add product/radar research, metadata APIs, and timeline shells;
  rendering requires documented format, projection, licensing, and cache policy.
- Stage 11 may add PWA, local-only power-user tools, dashboards, and alert rules
  that stay separate from official IMGW warning responsibility.
- Stage 12 is release-polish documentation and smoke testing only unless a small
  consistency fix is needed.
- Stage 13 may import and render reviewed geometry datasets only after source
  and legal review is documented.
- Stage 14 may render a product layer only when the selected product path is
  legally usable and technically documented.
- Stage 15 may add opt-in archive backfill only through bounded, rate-limited
  server-side imports.
- Stage 16 may stabilize public API docs, generated clients, examples, and
  exports while preserving attribution and processed-data notices.
- Stage 17 may align documentation/status without runtime changes.
- Stage 18 may bundle reviewed synop station coordinates after source/legal
  review.
- Stage 19 must address public-internet security and abuse protection before
  unrestricted deployment.
- Stage 20 must add production observability, backup, and recovery before
  release validation.
- Stage 21 may tag and publish `v0.1.0-alpha` only after current-main
  production validation and unresolved release blockers are cleared.
- Stage 22 may add hydro basin geometry only after reviewed source/legal and
  `kod_zlewni` mapping work.
- Stage 23 may add hydrological archive backfill only for verified archive
  families through bounded server-side imports.
- Stage 24 may add warning history only with explicit source-correction,
  duplicate, retention, attribution, and official-warning-disclaimer handling.
- Stage 25 may harden performance only with measured budgets and regression
  thresholds.
- Stage 26 may add PDF reports only after security and resource controls are in
  place and fixture-based deterministic report tests exist.
