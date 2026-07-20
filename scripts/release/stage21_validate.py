#!/usr/bin/env python3
"""Small, dependency-free live validation helper for the Stage 21 release.

The script deliberately does not start containers, alter Docker volumes, or
publish Git objects.  It talks only to a supplied MeteoLens HTTP endpoint and
writes compact evidence files.  Administrative credentials are read from an
environment variable, never from command-line arguments or output.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin
from urllib.request import Request, urlopen


@dataclass
class Check:
    name: str
    passed: bool
    detail: str


class ValidationError(RuntimeError):
    """Expected release-validation failure."""


class Client:
    def __init__(self, base_url: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.timeout = timeout

    def request(
        self,
        path: str,
        *,
        method: str = "GET",
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        request = Request(
            urljoin(self.base_url, path.lstrip("/")),
            method=method,
            headers=headers or {},
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:  # noqa: S310 -- chosen URL is explicit input
                return response.status, dict(response.headers.items()), response.read()
        except HTTPError as exc:
            return exc.code, dict(exc.headers.items()), exc.read()
        except URLError as exc:
            raise ValidationError(f"request {method} {path} failed: {exc.reason}") from exc

    def json(self, path: str, **kwargs: Any) -> tuple[int, dict[str, str], dict[str, Any]]:
        status, headers, body = self.request(path, **kwargs)
        try:
            return status, headers, json.loads(body)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"{path} did not return JSON: {body[:200]!r}") from exc


class Evidence:
    def __init__(self, directory: Path, mode: str) -> None:
        self.directory = directory
        self.mode = mode
        self.checks: list[Check] = []
        self.payloads: dict[str, Any] = {}

    def check(self, name: str, condition: bool, detail: str) -> None:
        self.checks.append(Check(name, condition, detail))
        print(f"{'PASS' if condition else 'FAIL'}  {name} — {detail}")

    def payload(self, name: str, payload: Any) -> None:
        self.payloads[name] = payload

    def finish(self) -> int:
        self.directory.mkdir(parents=True, exist_ok=True)
        output = {
            "mode": self.mode,
            "recorded_at": datetime.now(UTC).isoformat(),
            "checks": [asdict(check) for check in self.checks],
            "payloads": self.payloads,
        }
        target = self.directory / f"stage21-{self.mode}.json"
        target.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        failed = [check for check in self.checks if not check.passed]
        print(f"\n{len(self.checks) - len(failed)}/{len(self.checks)} checks passed; evidence: {target}")
        return 1 if failed else 0


def require_status(status: int, expected: int, path: str) -> None:
    if status != expected:
        raise ValidationError(f"{path}: expected HTTP {expected}, got {status}")


def header_value(headers: dict[str, str], name: str) -> str | None:
    """Return an HTTP header without relying on a client's display casing."""
    target = name.lower()
    return next((value for key, value in headers.items() if key.lower() == target), None)


def baseline(client: Client, evidence: Evidence) -> None:
    status, _, health = client.json("/health/live")
    require_status(status, 200, "/health/live")
    evidence.payload("health_live", health)
    evidence.check("liveness", health.get("status") == "ok", f"status={health.get('status')}")

    status, _, ready = client.json("/health/ready")
    require_status(status, 200, "/health/ready")
    evidence.payload("health_ready", ready)
    evidence.check("production readiness", ready.get("status") == "ready", f"status={ready.get('status')}")

    status, _, sources = client.json("/api/v1/sources")
    require_status(status, 200, "/api/v1/sources")
    evidence.payload("sources", sources)
    descriptors = sources.get("sources", [])
    expected = {"synop", "hydro", "meteo", "warningsmeteo", "warningshydro", "product"}
    found = {item.get("key") for item in descriptors}
    evidence.check("all IMGW source descriptors", expected <= found, f"found={sorted(found)}")
    bad = [
        item.get("key")
        for item in descriptors
        if item.get("cache_status") in {"empty", "invalid", "error"}
    ]
    evidence.check("live source cache usable", not bad, f"unusable={bad}")


def geometry(client: Client, evidence: Evidence) -> None:
    status, _, payload = client.json("/api/v1/geometry/datasets")
    require_status(status, 200, "/api/v1/geometry/datasets")
    evidence.payload("geometry_datasets", payload)
    datasets = {item.get("key"): item for item in payload.get("datasets", [])}
    expected = {
        "synop_stations": 62,
        "teryt_counties": 380,
        "teryt_voivodeships": 16,
        "hydro_basins": 103,
    }
    for key, count in expected.items():
        item = datasets.get(key, {})
        evidence.check(
            f"bundled geometry {key}",
            item.get("loaded") is True and item.get("feature_count") == count,
            f"loaded={item.get('loaded')} features={item.get('feature_count')}",
        )
    hydro = datasets.get("hydro_basins", {})
    evidence.check(
        "hydro basin geometry bundled and reviewed",
        hydro.get("loaded") is True and hydro.get("review_status") == "approved",
        f"loaded={hydro.get('loaded')} review={hydro.get('review_status')}",
    )

    status, _, stations = client.json("/api/v1/stations?type=synop&limit=200")
    require_status(status, 200, "/api/v1/stations?type=synop&limit=200")
    evidence.payload("synop_stations", stations)
    records = stations.get("stations", [])
    enriched = [item for item in records if item.get("lat") is not None and item.get("coordinate_source")]
    evidence.check("SYNOP coordinates and attribution", bool(enriched), f"enriched={len(enriched)} total={len(records)}")


def exports(client: Client, evidence: Evidence) -> None:
    status, _, stations = client.json("/api/v1/stations?limit=200")
    require_status(status, 200, "/api/v1/stations?limit=200")
    station = next((item for item in stations.get("stations", []) if item.get("id")), None)
    if station is None:
        raise ValidationError("no cached station is available for export validation")
    station_id = str(station["id"])
    encoded = quote(station_id, safe=":")
    checks = {
        "station JSON": f"/api/v1/export/station/{encoded}.json",
        "observations JSON": f"/api/v1/export/station/{encoded}/observations.json",
        "map GeoJSON": "/api/v1/export/map.geojson",
        "warnings GeoJSON": "/api/v1/export/warnings.geojson",
        "map state": "/api/v1/export/map-state.json",
    }
    for name, path in checks.items():
        status, _, payload = client.json(path)
        require_status(status, 200, path)
        evidence.payload(name.replace(" ", "_").lower(), payload)
        evidence.check(
            f"{name} attribution",
            bool(payload.get("attribution")) and bool(payload.get("processed_notice")),
            f"station={station_id}",
        )

    for name, path in {
        "station CSV": f"/api/v1/export/station/{encoded}.csv",
        "observations CSV": f"/api/v1/export/station/{encoded}/observations.csv",
    }.items():
        status, _, body = client.request(path)
        require_status(status, 200, path)
        text = body.decode("utf-8", errors="replace")
        evidence.check(f"{name} metadata columns", "attribution" in text and "processed_notice" in text, f"station={station_id}")


def render(client: Client, evidence: Evidence) -> str:
    status, _, frames = client.json("/api/v1/products/COSMO_HVD_00_00/frames?limit=120")
    require_status(status, 200, "COSMO frames")
    evidence.payload("cosmo_frames", frames)
    frame = next((item for item in frames.get("frames", []) if item.get("renderable") and item.get("render_url")), None)
    if frame is None:
        raise ValidationError("no live renderable COSMO frame is cached")
    render_url = str(frame["render_url"])

    def download() -> tuple[int, dict[str, str], bytes]:
        return client.request(render_url)

    started = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        first, second = list(pool.map(lambda _: download(), range(2)))
    elapsed = time.monotonic() - started
    for index, (status_code, headers, body) in enumerate((first, second), start=1):
        evidence.check(
            f"cold COSMO render request {index}",
            status_code == 200
            and (header_value(headers, "Content-Type") or "").startswith("image/png")
            and body.startswith(b"\x89PNG"),
            f"status={status_code} bytes={len(body)}",
        )
    digest_one = hashlib.sha256(first[2]).hexdigest()
    digest_two = hashlib.sha256(second[2]).hexdigest()
    evidence.check("coalesced COSMO responses match", digest_one == digest_two, f"sha256={digest_one} elapsed={elapsed:.2f}s")
    evidence.payload("cosmo_render", {"render_url": render_url, "sha256": digest_one, "elapsed_seconds": elapsed})

    status, _, replay = client.request(render_url)
    evidence.check("cached COSMO replay", status == 200 and replay.startswith(b"\x89PNG"), f"status={status} bytes={len(replay)}")
    status, _, updated = client.json("/api/v1/products/COSMO_HVD_00_00/frames?limit=120")
    require_status(status, 200, "COSMO replay frames")
    cached_frame = next((item for item in updated.get("frames", []) if item.get("render_url") == render_url), {})
    evidence.check("COSMO frame reports render_ready", cached_frame.get("render_ready") is True, f"render_ready={cached_frame.get('render_ready')}")
    return render_url


def archive(client: Client, evidence: Evidence, args: argparse.Namespace) -> None:
    path = f"/api/v1/archive/backfill/synop-daily?from={args.archive_date}&to={args.archive_date}"
    token = os.environ.get(args.admin_token_env) if args.admin_token_env else None
    if token:
        status, _, unauthorized = client.json(path, method="POST")
        evidence.check("archive requires admin authentication", status == 401, f"status={status} code={unauthorized.get('detail', {})}")
        status, headers, payload = client.json(path, method="POST", headers={"X-MeteoLens-Admin-Token": token})
        evidence.payload("archive_result", payload)
        evidence.check("bounded archive backfill", status == 200 and payload.get("status") in {"completed", "completed_with_warnings"}, f"status={status}")
        status, headers, repeated = client.json(path, method="POST", headers={"X-MeteoLens-Admin-Token": token})
        evidence.payload("archive_repeat", repeated)
        retry_after = header_value(headers, "Retry-After")
        evidence.check("archive cooldown", status == 429 and bool(retry_after), f"status={status} retry_after={retry_after}")
    else:
        status, _, payload = client.json(path, method="POST")
        evidence.payload("archive_disabled", payload)
        evidence.check("archive disabled without configured token", status == 403, f"status={status}")


def outage(client: Client, evidence: Evidence) -> None:
    status, _, ready = client.json("/health/ready")
    require_status(status, 200, "/health/ready")
    evidence.payload("outage_ready", ready)
    evidence.check("outage readiness is degraded", ready.get("status") == "degraded", f"status={ready.get('status')}")
    status, _, sources = client.json("/api/v1/sources")
    require_status(status, 200, "/api/v1/sources")
    evidence.payload("outage_sources", sources)
    source_states = [item.get("cache_status") for item in sources.get("sources", [])]
    evidence.check("source failure remains visible", any(value in {"error", "stale"} for value in source_states), f"states={source_states}")
    status, _, stations = client.json("/api/v1/stations?limit=1")
    require_status(status, 200, "/api/v1/stations?limit=1")
    evidence.check("cached stations survive outage", bool(stations.get("stations")), f"count={len(stations.get('stations', []))}")


def abuse(client: Client, evidence: Evidence, args: argparse.Namespace) -> None:
    if not args.render_url:
        raise ValidationError("abuse mode requires --render-url from a prior render run")
    count = args.requests

    def request_once(_: int) -> int:
        status, _, _ = client.request(args.render_url)
        return status

    with concurrent.futures.ThreadPoolExecutor(max_workers=count) as pool:
        statuses = list(pool.map(request_once, range(count)))
    limited = sum(status in {429, 503} for status in statuses)
    evidence.payload("abuse_statuses", statuses)
    evidence.check("nginx limits cached render burst", limited > 0, f"statuses={statuses}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="MeteoLens public HTTP origin")
    parser.add_argument("--evidence-dir", required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--admin-token-env", default=None)
    parser.add_argument("--archive-date", default="2026-05-01")
    parser.add_argument("--render-url", default=None)
    parser.add_argument("--requests", type=int, default=15)
    parser.add_argument("mode", choices=("baseline", "geometry", "exports", "render", "archive", "outage", "abuse"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    client = Client(args.base_url, args.timeout)
    evidence = Evidence(args.evidence_dir, args.mode)
    try:
        {
            "baseline": baseline,
            "geometry": geometry,
            "exports": exports,
            "render": render,
            "archive": archive,
            "outage": outage,
            "abuse": abuse,
        }[args.mode](client, evidence) if args.mode not in {"archive", "abuse"} else {"archive": archive, "abuse": abuse}[args.mode](client, evidence, args)
    except ValidationError as exc:
        evidence.check("validation request", False, str(exc))
    return evidence.finish()


if __name__ == "__main__":
    raise SystemExit(main())
