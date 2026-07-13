"""Create, verify, and restore portable MeteoLens /data backups."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import tarfile
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from app.core.config import get_settings
from app.db.engine import database_path_from_url

FORMAT_VERSION = 1
BACKEND_UID = 10001
BACKEND_GID = 10001


def create_backup(*, scope: str, output_dir: Path, offline_confirmed: bool = False) -> Path:
    if scope not in {"essential", "full"}:
        raise ValueError("scope must be essential or full")
    if scope == "full" and not offline_confirmed:
        raise ValueError("full backups require --offline-confirmed")
    settings = get_settings()
    data_dir = settings.cache_dir.parent
    db_path = database_path_from_url(settings.database_url)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    archive_path = output_dir / f"meteolens-{scope}-{timestamp}.tar.gz"
    with TemporaryDirectory(prefix="meteolens-backup-") as temp:
        staging = Path(temp)
        payload = staging / "data"
        payload.mkdir()
        snapshot_name = db_path.name or "meteolens.sqlite3"
        _sqlite_backup(db_path, payload / snapshot_name)
        _copy_if_exists(settings.cache_dir, payload / "cache")
        _copy_if_exists(settings.geometry_dir, payload / "geometry")
        _copy_if_exists(data_dir / ".operations", payload / ".operations")
        if scope == "full":
            _copy_if_exists(data_dir / "products", payload / "products")
        files = _manifest_files(staging)
        manifest = {
            "format_version": FORMAT_VERSION,
            "scope": scope,
            "created_at": datetime.now(UTC).isoformat(),
            "database_file": snapshot_name,
            "included": ["database", "cache", "geometry", "operations"]
            + (["products"] if scope == "full" else []),
            "excluded": [] if scope == "full" else ["products/binaries", "products/renders"],
            "files": files,
        }
        (staging / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        with tarfile.open(archive_path, "w:gz") as archive:
            archive.add(staging / "manifest.json", arcname="manifest.json")
            archive.add(payload, arcname="data")
    _write_state(
        data_dir / ".operations" / "last-backup.json",
        {
            "completed_at": datetime.now(UTC).isoformat(),
            "archive": archive_path.name,
            "scope": scope,
        },
    )
    return archive_path


def verify_backup(archive_path: Path) -> dict[str, object]:
    with TemporaryDirectory(prefix="meteolens-verify-") as temp:
        staging = Path(temp)
        _extract_safely(archive_path, staging)
        manifest = _read_manifest(staging)
        _verify_manifest(staging, manifest)
        database = staging / "data" / str(manifest["database_file"])
        with sqlite3.connect(database) as connection:
            result = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise ValueError(f"SQLite integrity check failed: {result}")
    return {"archive": archive_path.name, "verified": True, "scope": manifest["scope"]}


def restore_backup(*, archive_path: Path, target_dir: Path) -> dict[str, object]:
    if target_dir.exists() and any(target_dir.iterdir()):
        raise ValueError("restore target must be an empty fresh volume")
    target_dir.mkdir(parents=True, exist_ok=True)
    staging = target_dir / ".restore-staging"
    try:
        _extract_safely(archive_path, staging)
        manifest = _read_manifest(staging)
        _verify_manifest(staging, manifest)
        database = staging / "data" / str(manifest["database_file"])
        with sqlite3.connect(database) as connection:
            result = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise ValueError(f"SQLite integrity check failed: {result}")
        payload = staging / "data"
        for child in payload.iterdir():
            shutil.move(str(child), target_dir / child.name)
        _write_state(
            target_dir / ".operations" / "last-restore.json",
            {"completed_at": datetime.now(UTC).isoformat(), "archive": archive_path.name},
        )
        if os.geteuid() == 0:
            _chown_tree(target_dir, uid=BACKEND_UID, gid=BACKEND_GID)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return {"archive": archive_path.name, "restored": True, "scope": manifest["scope"]}


def _sqlite_backup(source: Path, destination: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(f"SQLite database not found: {source}")
    with (
        sqlite3.connect(source) as source_connection,
        sqlite3.connect(destination) as destination_connection,
    ):
        source_connection.backup(destination_connection)


def _copy_if_exists(source: Path, destination: Path) -> None:
    if not source.exists():
        return
    if source.is_dir():
        shutil.copytree(source, destination, dirs_exist_ok=True)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def _manifest_files(root: Path) -> list[dict[str, object]]:
    files = []
    for path in sorted((item for item in root.rglob("*") if item.is_file()), key=str):
        relative = path.relative_to(root).as_posix()
        files.append({"path": relative, "size": path.stat().st_size, "sha256": _sha256(path)})
    return files


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _extract_safely(archive_path: Path, destination: Path) -> None:
    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            for member in archive.getmembers():
                member_path = destination / member.name
                unsafe = member.islnk() or member.issym()
                outside_destination = not member_path.resolve().is_relative_to(
                    destination.resolve()
                )
                if unsafe or outside_destination:
                    raise ValueError("backup contains an unsafe archive path")
            archive.extractall(destination, filter="data")
    except (OSError, tarfile.TarError) as exc:
        raise ValueError("backup archive cannot be read") from exc


def _read_manifest(root: Path) -> dict[str, object]:
    try:
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("backup manifest is missing or invalid") from exc
    if manifest.get("format_version") != FORMAT_VERSION:
        raise ValueError("unsupported backup format")
    return manifest


def _verify_manifest(root: Path, manifest: dict[str, object]) -> None:
    files = manifest.get("files")
    if not isinstance(files, list):
        raise ValueError("backup manifest has no file inventory")
    for item in files:
        if not isinstance(item, dict):
            raise ValueError("backup manifest contains an invalid file entry")
        path = root / str(item.get("path", ""))
        if not path.is_file() or _sha256(path) != item.get("sha256"):
            raise ValueError(f"backup checksum mismatch: {item.get('path')}")


def _write_state(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")


def _chown_tree(root: Path, *, uid: int, gid: int) -> None:
    """Hand a restored volume back to the non-root production backend."""
    os.chown(root, uid, gid)
    for path in root.rglob("*"):
        os.chown(path, uid, gid, follow_symlinks=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create")
    create.add_argument("--scope", choices=("essential", "full"), default="essential")
    create.add_argument("--output-dir", type=Path, required=True)
    create.add_argument("--offline-confirmed", action="store_true")
    verify = subparsers.add_parser("verify")
    verify.add_argument("archive", type=Path)
    restore = subparsers.add_parser("restore")
    restore.add_argument("archive", type=Path)
    restore.add_argument("--target-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "create":
        result: object = create_backup(
            scope=args.scope, output_dir=args.output_dir, offline_confirmed=args.offline_confirmed
        )
        print(json.dumps({"archive": str(result)}, ensure_ascii=False))
    elif args.command == "verify":
        print(json.dumps(verify_backup(args.archive), ensure_ascii=False))
    else:
        result = restore_backup(archive_path=args.archive, target_dir=args.target_dir)
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
