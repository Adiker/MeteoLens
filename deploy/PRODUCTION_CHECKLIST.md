# MeteoLens production deployment checklist

Use this checklist before exposing a public demo or production instance. The
boxes are intentionally unchecked: complete them per deployment on the target
host. A reference run of the smoke-test items is recorded in
`docs/release/SMOKE_TEST_2026-07-03.md`; the frontend checks can be repeated
with `frontend/scripts/smoke.mjs`.

## Legal and attribution

- [ ] Current IMGW-PIB terms reviewed for the intended public or commercial use
  (see `LEGAL_ATTRIBUTION.md` → "Commercial And Public Use").
- [ ] MIT License referenced in deployment notes and repository README.
- [ ] IMGW-PIB attribution visible in the UI and exports.
- [ ] Processed-data notice visible wherever data is normalized or transformed.
- [ ] Known limitations from README remain visible (no hidden data-quality gaps).

## Infrastructure

- [ ] Local development smoke test recorded with `docker compose up --build`,
  `/health`, `/api/v1/sources`, frontend map load, station details, warning
  details/list, exports, expert panel, and timeline shell.
- [ ] `docker compose -f docker-compose.prod.yml up --build` succeeds on the target host.
- [ ] Production smoke test recorded with
  `docker compose --env-file .env.production -f docker-compose.prod.yml up --build`.
- [ ] Configured public HTTP port opens during the production smoke test.
- [ ] Frontend is served as static assets (nginx), not the Vite dev server.
- [ ] Backend image built from `backend/Dockerfile.prod` without dev dependencies.
- [ ] Reverse proxy and TLS configured (`deploy/caddy/Caddyfile.example` or equivalent).
- [ ] Production CORS origins set via `METEOLENS_FRONTEND_ORIGIN` (comma-separated if needed).
- [ ] Production CORS origins are exact public HTTPS origins; no wildcard or localhost origin is used.
- [ ] Persistent volume mounted at `/data` for SQLite and IMGW cache.
- [ ] `METEOLENS_ADMIN_TOKEN` is absent (archive import disabled) or stored in the deployment secret manager and tested only through the admin header.
- [ ] Backend has no host port, runs as UID 10001, has a read-only root filesystem, dropped capabilities, and `no-new-privileges` enabled.
- [ ] `/data` is the only persistent writable backend path; the `data-init` service completed successfully on a fresh volume.
- [ ] `restart: unless-stopped` policies active for backend and frontend services.
- [ ] Backups planned for `/data` (database + cache metadata).

## IMGW access discipline

- [ ] Refresh intervals match `METEOLENS_REFRESH_*` defaults or documented overrides.
- [ ] Timeout/retry/backoff configured via `METEOLENS_IMGW_*` settings.
- [ ] Stale cache and source failures remain visible in `/api/v1/sources`.
- [ ] No direct IMGW calls from the browser.
- [ ] nginx request-size, timeout, public request-rate, and product-render-rate safeguards are active.
- [ ] Product render concurrency and archive duplicate-import cooldown retain their Stage 19 defaults unless capacity has been reviewed.

## Observability

- [ ] `/health` monitored for liveness.
- [ ] `/api/v1/sources` monitored for cache freshness and parser errors.
- [ ] Container logs reviewed for `meteolens.source` fetch outcomes.
- [ ] API errors logged under `meteolens.api` with path and error code.
- [ ] Logs checked to confirm that authorization values, signed URLs, and caller location query strings are not present.

## CI and repository security

- [ ] AI/comment workflows remain restricted to repository owners, members, and collaborators.
- [ ] Fork pull requests run only read-only CI/security checks and do not receive paid-AI secrets.
- [ ] Scheduled dependency review, secret scan, and container-image scan results are reviewed.

## Demo media

- [ ] README screenshots captured from a populated real cache (not mock data).
- [ ] Screenshots include attribution and processed-data notice where applicable.

## Commands

Local production smoke test:

```bash
cp deploy/.env.production.example .env.production
docker compose --env-file .env.production -f docker-compose.prod.yml up --build
```

Then open `http://localhost:8080` (or your configured `PUBLIC_HTTP_PORT`).
