# MeteoLens v0.1.0-alpha — release notes

MeteoLens is an alpha web map for public IMGW-PIB weather and hydrological
data. It provides live station and warning views, transparent source metadata,
expert raw-data inspection, exports, local observation history, and a reviewed
COSMO 2 m temperature map overlay.

## Highlights

- Reviewed PRG administrative geometry resolves current meteorological warning
  areas; reviewed WMO OSCAR/Surface metadata places current SYNOP stations on
  the map with source attribution.
- Product timeline, opt-in COSMO temperature rendering, explicit cache state,
  and safeguards around the expensive render path.
- Public API documentation, generated TypeScript client, CSV/JSON/GeoJSON/map
  exports, and visible IMGW-PIB attribution plus processed-data notices.
- Production hardening: rate and concurrency limits, protected archive import,
  non-root containers, private metrics, JSON logs, backup/restore tooling, and
  runbooks.
- Reviewed SYNOP live/archive station-ID reconciliation so mapped stations can
  show honest `mixed` observation series without name-based matching.

## Validation

Live Compose validation is recorded in
[`STAGE_21_VALIDATION_2026-07-14.md`](STAGE_21_VALIDATION_2026-07-14.md).
The final automated pre-tag suite for the release base commit is in
[`STAGE_21_PRETAG_2026-07-20.md`](STAGE_21_PRETAG_2026-07-20.md): backend
lint/tests (249 tests), frontend lint/tests (87 tests), production build,
and fixture E2E (5 tests).

## Important limitations

- This is not an official warning or alert-delivery service.
- Hydro basin polygons are not bundled, so hydrological warnings remain
  explicitly list-only where `kod_zlewni` geometry is unavailable.
- Only the documented COSMO temperature product path renders on the map; radar
  downloads are currently blocked by the source and other product files remain
  metadata-only.
- Observation history is local to a deployment. Only bounded daily SYNOP
  backfill is implemented; hydro and other archive families are not imported.
- SYNOP archive/current reconciliation is limited to the reviewed, versioned
  IMGW station-code map. The 2026-07-14 artifact maps 61 current stations;
  `Platforma` and any historical/future identifiers without an approved entry
  remain explicit archive-only records and are never matched by name.
- Deployers must review current IMGW-PIB and other source terms before public
  or commercial use. Attribution is implemented, but this project does not
  provide legal advice.

See the complete [Known Limitations](../../README.md#known-limitations),
[`LEGAL_ATTRIBUTION.md`](../../LEGAL_ATTRIBUTION.md), and the per-host
[`deploy/PRODUCTION_CHECKLIST.md`](../../deploy/PRODUCTION_CHECKLIST.md).
