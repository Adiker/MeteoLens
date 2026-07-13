import json
import os

import pytest

from app.core.config import Settings
from app.db.engine import init_db
from app.operations.backup import _chown_tree, create_backup, restore_backup, verify_backup
from tests.settings_helpers import apply_test_settings


def _settings(tmp_path) -> Settings:
    return Settings(
        cache_dir=tmp_path / "data" / "cache",
        geometry_dir=tmp_path / "data" / "geometry",
        database_url=f"sqlite:///{tmp_path / 'data' / 'meteolens.sqlite3'}",
    )


def test_essential_backup_restores_sqlite_cache_and_geometry(monkeypatch, tmp_path) -> None:
    settings = _settings(tmp_path)
    apply_test_settings(monkeypatch, settings)
    init_db()
    settings.cache_dir.mkdir(parents=True)
    settings.geometry_dir.mkdir(parents=True)
    (settings.cache_dir / "synop.json").write_text('{"source_key":"synop"}', encoding="utf-8")
    (settings.geometry_dir / "manifest.json").write_text('{"datasets":[]}', encoding="utf-8")

    archive = create_backup(scope="essential", output_dir=tmp_path / "backups")
    assert verify_backup(archive)["verified"] is True

    target = tmp_path / "restored"
    chown_calls: list[tuple[object, int, int, bool]] = []

    def fake_chown(path, uid, gid, *, follow_symlinks=True):
        chown_calls.append((path, uid, gid, follow_symlinks))

    monkeypatch.setattr(os, "geteuid", lambda: 0)
    monkeypatch.setattr(os, "chown", fake_chown)
    result = restore_backup(archive_path=archive, target_dir=target)

    assert result["restored"] is True
    assert (target / "meteolens.sqlite3").exists()
    assert (target / "cache" / "synop.json").exists()
    assert (target / "geometry" / "manifest.json").exists()
    assert not (target / "products").exists()
    assert (target, 10001, 10001, True) in chown_calls
    assert (target / "meteolens.sqlite3", 10001, 10001, False) in chown_calls


def test_full_backup_requires_explicit_offline_confirmation(monkeypatch, tmp_path) -> None:
    settings = _settings(tmp_path)
    apply_test_settings(monkeypatch, settings)
    init_db()

    with pytest.raises(ValueError, match="offline-confirmed"):
        create_backup(scope="full", output_dir=tmp_path / "backups")


def test_backup_verification_rejects_tampered_manifest(monkeypatch, tmp_path) -> None:
    settings = _settings(tmp_path)
    apply_test_settings(monkeypatch, settings)
    init_db()
    archive = create_backup(scope="essential", output_dir=tmp_path / "backups")

    # Corruption must fail validation rather than restore partial data.
    archive.write_bytes(b"not a tar archive")
    with pytest.raises((ValueError, OSError, EOFError, json.JSONDecodeError)):
        verify_backup(archive)


def test_chown_tree_assigns_restored_files_to_backend_uid(monkeypatch, tmp_path) -> None:
    restored = tmp_path / "restored"
    restored.mkdir()
    (restored / "meteolens.sqlite3").write_bytes(b"db")
    calls: list[tuple[object, int, int, bool]] = []

    def fake_chown(path, uid, gid, *, follow_symlinks=True):
        calls.append((path, uid, gid, follow_symlinks))

    monkeypatch.setattr(os, "chown", fake_chown)

    _chown_tree(restored, uid=10001, gid=10001)

    assert (restored, 10001, 10001, True) in calls
    assert (restored / "meteolens.sqlite3", 10001, 10001, False) in calls
