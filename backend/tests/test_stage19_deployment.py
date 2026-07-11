from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_nginx_has_request_limits_security_headers_and_product_limit() -> None:
    nginx = (ROOT / "deploy" / "nginx" / "frontend.conf").read_text(encoding="utf-8")
    nginx_root = (ROOT / "deploy" / "nginx" / "nginx.conf").read_text(encoding="utf-8")

    assert "client_max_body_size 64k" in nginx
    assert "Content-Security-Policy" in nginx
    assert "X-Content-Type-Options" in nginx
    assert "Referrer-Policy" in nginx
    assert "limit_req zone=public_api" in nginx
    assert "limit_req zone=product_render" in nginx
    assert "proxy_read_timeout 240s" in nginx
    assert "limit_req_zone $binary_remote_addr zone=public_api" in nginx_root


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


def test_ai_workflows_require_trusted_comment_authors_and_pin_actions() -> None:
    claude = (ROOT / ".github" / "workflows" / "claude.yml").read_text(encoding="utf-8")
    opencode = (ROOT / ".github" / "workflows" / "opencode.yml").read_text(encoding="utf-8")
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "author_association" in claude
    assert "author_association" in opencode
    assert "@latest" not in opencode
    assert "actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683" in ci


def test_security_workflow_covers_dependencies_secrets_and_container_images() -> None:
    workflow = (ROOT / ".github" / "workflows" / "security.yml").read_text(encoding="utf-8")

    assert "dependency-review-action@" in workflow
    assert "gitleaks-action@" in workflow
    assert "trivy-action@" in workflow
    assert "docker build --file backend/Dockerfile.prod" in workflow
