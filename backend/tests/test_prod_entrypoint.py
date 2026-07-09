import json
import os
import shutil
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENTRYPOINT = PROJECT_ROOT / "backend" / "docker-entrypoint.prod.sh"
BUNDLED_GEOMETRY = PROJECT_ROOT / "data" / "geometry"


def _copy_without_synop(source: Path, target: Path) -> None:
    target.mkdir()
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    manifest["datasets"] = [
        entry for entry in manifest["datasets"] if entry["key"] != "synop_stations"
    ]
    for entry in manifest["datasets"]:
        shutil.copy2(source / entry["file"], target / entry["file"])
    (target / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def test_prod_entrypoint_merges_new_bundled_geometry(tmp_path) -> None:
    geometry_dir = tmp_path / "geometry"
    _copy_without_synop(BUNDLED_GEOMETRY, geometry_dir)

    env = {
        **os.environ,
        "METEOLENS_GEOMETRY_DIR": str(geometry_dir),
        "METEOLENS_BUNDLED_GEOMETRY_DIR": str(BUNDLED_GEOMETRY),
    }

    result = subprocess.run(
        ["sh", str(ENTRYPOINT), "true"],
        check=True,
        env=env,
        text=True,
        capture_output=True,
    )

    manifest = json.loads((geometry_dir / "manifest.json").read_text(encoding="utf-8"))
    keys = {entry["key"] for entry in manifest["datasets"]}
    assert "synop_stations" in keys
    assert (geometry_dir / "synop_stations.geojson").exists()
    assert "Merged bundled geometry datasets" in result.stdout


def test_prod_entrypoint_does_not_overwrite_existing_manifest(tmp_path) -> None:
    geometry_dir = tmp_path / "geometry"
    shutil.copytree(BUNDLED_GEOMETRY, geometry_dir)
    manifest_path = geometry_dir / "manifest.json"
    before = manifest_path.read_text(encoding="utf-8")

    env = {
        **os.environ,
        "METEOLENS_GEOMETRY_DIR": str(geometry_dir),
        "METEOLENS_BUNDLED_GEOMETRY_DIR": str(BUNDLED_GEOMETRY),
    }

    result = subprocess.run(
        ["sh", str(ENTRYPOINT), "true"],
        check=True,
        env=env,
        text=True,
        capture_output=True,
    )

    assert manifest_path.read_text(encoding="utf-8") == before
    assert result.stdout == ""
