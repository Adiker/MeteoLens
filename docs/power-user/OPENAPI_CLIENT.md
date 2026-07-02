# Generated Public API Client Plan

Stage 11 documents client generation; no generated SDK is committed yet.

## Source Of Truth

- FastAPI OpenAPI schema at `/openapi.json`
- Human-readable contract in [`API_CONTRACT.md`](../../API_CONTRACT.md)

## Recommended Workflow

```bash
# Example only — run after backend is up locally
curl -sS http://localhost:8000/openapi.json -o openapi.json
npx openapi-typescript openapi.json -o meteolens-api.d.ts
```

Alternative generators:

- `openapi-generator-cli` for Python/TypeScript fetch clients
- `fern` or `speakeasy` if versioning and publishing become requirements

## Versioning Rules

1. Regenerate clients only from tagged releases, not from every branch.
2. Treat additive OpenAPI changes as minor; removed fields as major.
3. Keep `alerting_disclaimer` and attribution fields required in generated types.

## Stage 11 Scope

- Document the command sequence above.
- Do **not** check generated artifacts into the repo until release automation exists.
