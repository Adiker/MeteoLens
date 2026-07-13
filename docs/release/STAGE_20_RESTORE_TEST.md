# Stage 20 Restore Test Record

Date: 2026-07-13 (local Docker recovery smoke test)

- Candidate base: `b66f91119e96fcc1af3f3282ac3618deb756ce96` plus the Stage 20
  working-tree changes in this branch.
- Docker: `29.6.1`; Docker Compose: `5.3.1`.
- Essential archive:
  `meteolens-essential-20260713T093214Z.tar.gz`, SHA-256
  `e33427c6a03d9cc2e4fa41b98f52ef512476b2003a8aaa8fa5abd7f1e8b5bc3a`.
- Source, backup, and restored target were three newly created named volumes:
  `meteolens-stage20-source`, `meteolens-stage20-backups`, and
  `meteolens-stage20-restored`.
- `data-ops verify` succeeded; restore into the empty target succeeded;
  `PRAGMA integrity_check` returned `ok`; the bundled geometry manifest loaded
  successfully after restore.
- Review follow-up repeated the fresh-volume restore with the production image;
  the restored database and cache were writable by the backend's non-root
  `10001:10001` user.
- Isolated production Compose smoke test also passed with startup refresh
  disabled: `/health/live` returned `ok`, `/health/ready` returned expected
  `degraded` for an empty cache, Prometheus scraped `backend:8000` as `up=1`,
  and public nginx did not expose OpenMetrics content at `/metrics`.

The automated backend test additionally checks SQLite/cache/geometry restoration
and corruption rejection. Stage 21 must repeat the full Compose smoke test on
the release commit, including `/health/ready`, `/api/v1/sources`, and a
station-history request.
