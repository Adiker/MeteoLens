"""Import and validate reviewed geometry datasets.

Usage (from the ``backend/`` directory):

    python -m app.geometry.import_cli validate <dataset-key> <geojson-file>
    python -m app.geometry.import_cli import <dataset-key> <geojson-file> \
        --metadata <metadata.json> [--geometry-dir DIR]
    python -m app.geometry.import_cli status [--geometry-dir DIR]

``validate`` runs the full strict validation (syntax, geometry types,
required properties, identifier coverage, Poland coordinate bounds) without
touching the geometry cache. ``import`` additionally requires a metadata JSON
file documenting the source and legal review, copies the dataset into the
geometry directory, and registers it in ``manifest.json``. Reference metadata
files for reviewed sources live under ``docs/geometry/metadata/``.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import get_settings
from app.geometry.loader import (
    MANIFEST_FORMAT_VERSION,
    REVIEW_METADATA_FIELDS,
    GeometryStore,
)
from app.geometry.validation import ValidationReport, validate_dataset

REQUIRED_METADATA_FIELDS = ("title", *REVIEW_METADATA_FIELDS)
REQUIRED_REVIEW_FIELDS = ("status", "reviewed_at", "reviewed_by")


def _default_geometry_dir() -> Path:
    return get_settings().geometry_dir


def _load_geojson(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        print(f"error: cannot read {path}: {exc}", file=sys.stderr)
    except ValueError as exc:
        print(f"error: {path} is not valid JSON: {exc}", file=sys.stderr)
    return None


def _print_report(report: ValidationReport) -> None:
    print(f"dataset: {report.dataset_key}")
    print(f"features: {report.feature_count}")
    print(f"identifiers: {len(report.codes)}")
    if report.ok:
        print("validation: OK")
        return
    print(f"validation: FAILED ({len(report.issues)} issues)")
    for issue in report.issues[:20]:
        print(f"  - {issue}")
    if len(report.issues) > 20:
        print(f"  ... and {len(report.issues) - 20} more")


def _validate_metadata(metadata: dict) -> list[str]:
    problems = [
        f"metadata missing required field {field!r}"
        for field in REQUIRED_METADATA_FIELDS
        if metadata.get(field) in (None, "")
    ]
    review = metadata.get("review")
    if not isinstance(review, dict):
        problems.append("metadata missing required 'review' object")
        return problems
    problems.extend(
        f"metadata review missing required field {field!r}"
        for field in REQUIRED_REVIEW_FIELDS
        if review.get(field) in (None, "")
    )
    if review.get("status") not in (None, "approved"):
        problems.append(
            "review.status must be 'approved'; unreviewed datasets cannot be imported"
        )
    return problems


def cmd_validate(args: argparse.Namespace) -> int:
    payload = _load_geojson(Path(args.geojson))
    if payload is None:
        return 1
    report = validate_dataset(args.dataset_key, payload, strict_coverage=True)
    _print_report(report)
    return 0 if report.ok else 1


def cmd_import(args: argparse.Namespace) -> int:
    source_path = Path(args.geojson)
    payload = _load_geojson(source_path)
    if payload is None:
        return 1

    metadata_path = Path(args.metadata)
    metadata = _load_geojson(metadata_path)
    if metadata is None:
        return 1
    problems = _validate_metadata(metadata)
    if problems:
        for problem in problems:
            print(f"error: {problem}", file=sys.stderr)
        return 1

    report = validate_dataset(args.dataset_key, payload, strict_coverage=True)
    _print_report(report)
    if not report.ok:
        print("error: dataset failed validation; nothing imported", file=sys.stderr)
        return 1

    geometry_dir = Path(args.geometry_dir) if args.geometry_dir else _default_geometry_dir()
    geometry_dir.mkdir(parents=True, exist_ok=True)
    target_name = f"{args.dataset_key}.geojson"
    target_path = geometry_dir / target_name
    shutil.copyfile(source_path, target_path)

    manifest_path = geometry_dir / "manifest.json"
    manifest = {"format_version": MANIFEST_FORMAT_VERSION, "datasets": []}
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if isinstance(existing.get("datasets"), list):
            manifest["datasets"] = [
                entry
                for entry in existing["datasets"]
                if entry.get("key") != args.dataset_key
            ]

    entry = {
        "key": args.dataset_key,
        "file": target_name,
        "imported_at": datetime.now(UTC).isoformat(),
        "feature_count": report.feature_count,
        **{field: metadata[field] for field in REQUIRED_METADATA_FIELDS},
        "review": {**metadata["review"], "status": "approved"},
    }
    manifest["datasets"].append(entry)
    manifest["datasets"].sort(key=lambda item: item.get("key", ""))
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"imported: {target_path}")
    print(f"manifest: {manifest_path}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    geometry_dir = Path(args.geometry_dir) if args.geometry_dir else _default_geometry_dir()
    store = GeometryStore(geometry_dir)
    store.load_all()
    if not store.datasets:
        print(f"no datasets registered in {geometry_dir / 'manifest.json'}")
        return 0
    for item in store.status():
        state = "loaded" if item["loaded"] else f"error: {item['error']}"
        print(
            f"{item['key']}: {state}, features={item['feature_count']}, "
            f"provider={item['provider']}, reviewed_at={item['reviewed_at']}"
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.geometry.import_cli",
        description="Validate and import reviewed geometry datasets.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser(
        "validate", help="Validate a GeoJSON dataset without importing it."
    )
    validate_parser.add_argument("dataset_key")
    validate_parser.add_argument("geojson")
    validate_parser.set_defaults(func=cmd_validate)

    import_parser = subparsers.add_parser(
        "import", help="Validate and install a reviewed GeoJSON dataset."
    )
    import_parser.add_argument("dataset_key")
    import_parser.add_argument("geojson")
    import_parser.add_argument(
        "--metadata",
        required=True,
        help="JSON file with source, license, attribution, and review metadata.",
    )
    import_parser.add_argument("--geometry-dir", default=None)
    import_parser.set_defaults(func=cmd_import)

    status_parser = subparsers.add_parser(
        "status", help="Show the state of registered geometry datasets."
    )
    status_parser.add_argument("--geometry-dir", default=None)
    status_parser.set_defaults(func=cmd_status)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
