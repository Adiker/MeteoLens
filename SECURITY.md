# Security policy

## Reporting a vulnerability

Do not publish suspected vulnerabilities, exposed credentials, or sensitive
proofs-of-concept in a public issue. Contact the repository owner privately
through the email address on the GitHub profile with a minimal reproduction,
affected revision, and impact. We will acknowledge the report, assess it, and
coordinate a fix before public disclosure.

## Deployment model and limits

MeteoLens has three HTTP route categories: public read-only data, exports, and
metadata routes; expensive product-frame rendering; and administrative archive
backfill. Archive backfill is disabled unless `METEOLENS_ADMIN_TOKEN` is
configured. Enabled deployments require that exact value in
`X-MeteoLens-Admin-Token`; it is an operator credential, not a user account
system. Store it outside git and never expose it to browser code.

The production nginx entrypoint applies a 64 KB request-body maximum, finite
timeouts, per-IP public and product-render request limits, and HTTP security
headers. The backend coalesces duplicate in-flight renders, limits render
concurrency, permits only one archive import, and applies an archive duplicate
range cooldown. Product download size remains bounded. Product render downloads
validate manifest URLs immediately before every HTTP request: HTTPS, the configured
IMGW host, approved IMGW download paths, and a DNS resolution that rejects
loopback, link-local, private, and other disallowed addresses. Cached manifests
or binaries do not bypass those checks.

The documented Caddy TLS proxy sends all traffic through nginx rather than
bypassing these controls. Nginx accepts forwarded client addresses only from
its configured trusted proxy ranges. If the proxy uses a custom network, narrow
the trusted range to that network before treating the limits as per-client.

The production backend is non-root, read-only outside `/data`, capability-free,
and uses `no-new-privileges`. Nginx is likewise non-root and read-only apart
from its temporary filesystem.

## CI and supply-chain checks

AI workflows with paid-service tokens run only when an `OWNER`, `MEMBER`, or
`COLLABORATOR` invokes them. Fork pull requests receive read-only CI/security
checks but not those credentials. Workflow permissions are scoped per job and
actions are commit-pinned. Action pins, the fixed `ubuntu-24.04` runner, and the
daily GitHub Actions Dependabot configuration follow the repository owner's
`keyboard-volume-app` maintenance pattern. MeteoLens keeps its own backend,
frontend, E2E, and production-container jobs rather than copying C++ jobs.

Manual `@claude` and `/oc` workflows remain available only to trusted actors.
Automatic Claude PR review and Claude verification of Codex reviews are
scaffolded separately but fail closed behind explicit `if: false` guards until
their paid execution and OAuth behavior are deliberately revalidated.

`.github/workflows/security.yml` performs pull-request dependency review,
Gitleaks secret scanning, and a Trivy scan of the production backend image.
These checks reduce risk but do not replace dependency updates, image rebuilds,
or host patching.

## Logging and privacy

Operational logs must not contain authorization headers, admin tokens, cookies,
signed URLs, or request query strings. The backend redacts common credential and
signed-URL parameters before source/error logging. Do not log precise caller
coordinates; the location route path is sufficient for routine diagnostics.

## Remaining limitations

Rate limits are per nginx instance and per IP, not shared across replicas. The
admin token is a shared secret rather than identity-based access control, and
in-process render/import gates do not coordinate multiple backend replicas.
Use a CDN/WAF plus a shared rate limiter and work queue/lock before horizontally
scaling public expensive operations.
