# MeteoLens v0.1.0-alpha — release notes candidate

> This file is prepared for the first prerelease. As of 2026-07-14,
> `v0.1.0-alpha` has not been tagged or published.

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

## Validation

The candidate passed backend lint/tests (212 tests), frontend lint/tests (87
tests), production build, fixture E2E (5 tests), live development and nginx
production browser smoke tests (13/13 each), fresh-volume setup, persistent
volume upgrade, COSMO render/cache, outage, bounded archive, abuse-limit, and
backup/restore checks. Full evidence and rollback steps are in
[`STAGE_21_VALIDATION_2026-07-14.md`](STAGE_21_VALIDATION_2026-07-14.md).

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
