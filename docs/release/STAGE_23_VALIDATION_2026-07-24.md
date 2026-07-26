# Stage 23 Validation - 2026-07-24

## Scope

This record validates the bounded daily hydrological `CODZ` archive importer,
its additive API/database/frontend changes, and the explicit Stage 23
non-goals. `ZJAW`, monthly hydrological summaries, and semi-annual/annual
summary families remain unsupported.

## Source Reverification

Rechecked on 2026-07-24:

- [official daily hydrological catalogue](https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_hydrologiczne/dobowe/);
- [official CODZ field contract](https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_hydrologiczne/dobowe/CODZ_publiczne_format.txt);
- `UWAGA.txt` in the same catalogue;
- [current IMGW data regulations](https://danepubliczne.imgw.pl/pl/regulations).

The catalogue still separates `CODZ` and `ZJAW`. The 2023 and 2024
directories publish annual `codz_RRRR.zip` files. Fixture coverage also locks
the reviewed monthly filename, encoding, delimiter, and whole-row quotation
variants.

## Real-Source Smoke Import

The smoke ran against
`2024/codz_2024.zip` for the inclusive range 2024-01-01 through 2024-01-02,
using an isolated temporary SQLite database that was deleted on completion.

- source ZIP SHA-256:
  `c40ebcda7a6b7ee30c936531fd0f391ba34d5bdf1545b535c3347c39319651fa`;
- source `Last-Modified`: `Thu, 28 Aug 2025 12:27:29 GMT`;
- result: `completed`, one of one files processed;
- selected source rows: 1,746;
- normalized observations: 5,238 inserted;
- warnings, conflicts, and deletions: zero.

Independent extraction of the source rows for `PSKDSZS=149180020` produced:

```text
149180020, CHAŁUPKI, Odra (1), 2024, 03, 01, 198, 82.900, [empty], 01
149180020, CHAŁUPKI, Odra (1), 2024, 03, 02, 210, 92.400, [empty], 01
```

The persisted sample matched exactly: 198/210 cm, 82.9/92.4 m³/s, and missing
water temperature with `missing_reason=source_null`. Both dates were stored at
midnight UTC with `temporal_resolution=1d`,
`quality_status=not_provided_by_source` on numeric observations, exact station
ID `hydro:149180020`, source URL, ZIP hash, and Last-Modified.

## Correction And Integrity Evidence

Automated tests prove:

- identical source duplicates collapse and are counted;
- conflicting duplicates fail the file;
- a corrected value updates the archive observation;
- a row withdrawn from a completely parsed source slice is deleted and counted;
- a conflicting reparse leaves the previously committed file slice unchanged;
- rerunning the same range does not create duplicate observations;
- equal-time live/archive points remain separate and produce a true `mixed`
  response;
- two source codes with the same station name remain separate series;
- automatic retention removes only `live_refresh`;
- manual cleanup is dry-run first and deletes only after `--confirm`;
- fresh/existing SQLite migration succeeds, and an injected migration failure
  rolls back every schema change.

## Automated Gates

Commands and results:

```text
backend: uv run pytest -q                 275 passed
backend: uv run ruff check .              passed
frontend: npm test -- --run               92 passed
frontend: npm run lint                    passed
frontend: npm run build                   passed
frontend: npm run test:e2e                5 passed
TypeScript client: npm run check          passed
repository: git diff --check              passed
```

The full backend suite includes the existing essential backup/verify/restore
coverage. Non-blocking toolchain notices were the existing Starlette
`TestClient` deprecation warning and Vite's large-chunk advisory.

## Acceptance

Stage 23 acceptance criteria are met for the verified daily `CODZ` family.
Approval still requires normal review of the complete diff; green CI alone is
not the acceptance evidence. The real-source comparison and correction,
withdrawal, rollback, retention, cleanup, migration, API/export/client, UI, and
E2E tests above are part of the evidence.
