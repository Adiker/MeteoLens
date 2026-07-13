from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_nginx_has_request_limits_security_headers_and_product_limit() -> None:
    nginx = (ROOT / "deploy" / "nginx" / "frontend.conf").read_text(encoding="utf-8")
    nginx_root = (ROOT / "deploy" / "nginx" / "nginx.conf").read_text(encoding="utf-8")

    assert "client_max_body_size 64k" in nginx
    assert "Content-Security-Policy" in nginx
    assert "connect-src 'self' https://tile.openstreetmap.org" in nginx
    assert "img-src 'self' data: blob: https://tile.openstreetmap.org" in nginx
    assert "X-Content-Type-Options" in nginx
    assert "Referrer-Policy" in nginx
    assert "limit_req zone=public_api" in nginx
    assert "limit_req zone=product_render" in nginx
    assert "proxy_read_timeout 240s" in nginx
    assert "limit_req_zone $binary_remote_addr zone=public_api" in nginx_root
    assert "set_real_ip_from 172.16.0.0/12" in nginx_root
    assert "real_ip_header X-Forwarded-For" in nginx_root


def test_caddy_keeps_nginx_as_the_single_application_entrypoint() -> None:
    caddy = (ROOT / "deploy" / "caddy" / "Caddyfile.example").read_text(
        encoding="utf-8"
    )

    assert "reverse_proxy frontend:8080" in caddy
    assert "backend:8000" not in caddy
    assert "frontend:80\n" not in caddy


def test_production_containers_are_restricted_and_backend_is_non_root() -> None:
    compose = (ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")
    backend_dockerfile = (ROOT / "backend" / "Dockerfile.prod").read_text(encoding="utf-8")
    frontend_dockerfile = (ROOT / "frontend" / "Dockerfile.prod").read_text(encoding="utf-8")

    assert 'user: "10001:10001"' in compose
    assert "read_only: true" in compose
    assert "no-new-privileges:true" in compose
    assert "cap_drop:" in compose
    assert "USER meteolens" in backend_dockerfile
    assert "USER nginx" in frontend_dockerfile
    assert "meteolens-data:/data" in compose


def test_data_init_takes_volume_ownership_before_geometry_upgrade() -> None:
    entrypoint = (ROOT / "backend" / "docker-entrypoint.prod.sh").read_text(
        encoding="utf-8"
    )

    take_ownership = entrypoint.index("chown -R root:root /data")
    merge_geometry = entrypoint.index("if [ -f \"$BUNDLED_GEOMETRY_DIR/manifest.json\" ]")
    hand_back = entrypoint.index("chown -R meteolens:meteolens /data")

    assert take_ownership < merge_geometry < hand_back


def test_ai_workflows_require_trusted_comment_authors_and_pin_actions() -> None:
    claude = (ROOT / ".github" / "workflows" / "claude.yml").read_text(encoding="utf-8")
    automatic_review = (
        ROOT / ".github" / "workflows" / "claude-code-review.yml"
    ).read_text(encoding="utf-8")
    verifier = (ROOT / ".github" / "workflows" / "claude-verifier.yml").read_text(
        encoding="utf-8"
    )
    opencode = (ROOT / ".github" / "workflows" / "opencode.yml").read_text(encoding="utf-8")
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    dependabot = (ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")

    assert "author_association" in claude
    assert "author_association" in opencode
    assert "@latest" not in opencode
    assert "actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0" in ci
    assert "astral-sh/setup-uv@11f9893b081a58869d3b5fccaea48c9e9e46f990" in ci
    assert "uv sync --frozen --extra dev" in ci
    assert "runs-on: ubuntu-24.04" in ci
    assert "if: false" in automatic_review
    assert "false &&" in verifier
    assert 'package-ecosystem: "github-actions"' in dependabot


def test_security_workflow_covers_dependencies_secrets_and_container_images() -> None:
    workflow = (ROOT / ".github" / "workflows" / "security.yml").read_text(encoding="utf-8")

    assert "dependency-review-action@" in workflow
    assert "gitleaks-action@" in workflow
    assert "trivy-action@" in workflow
    assert "docker build --file backend/Dockerfile.prod" in workflow
