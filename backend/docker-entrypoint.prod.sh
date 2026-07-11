#!/bin/sh
set -eu

GEOMETRY_DIR="${METEOLENS_GEOMETRY_DIR:-/data/geometry}"
BUNDLED_GEOMETRY_DIR="${METEOLENS_BUNDLED_GEOMETRY_DIR:-/app/bundled/geometry}"

if [ -f "$BUNDLED_GEOMETRY_DIR/manifest.json" ]; then
  mkdir -p "$GEOMETRY_DIR"
  if [ ! -f "$GEOMETRY_DIR/manifest.json" ]; then
    # Do not preserve owner/timestamp metadata here: the init container drops
    # all capabilities except CHOWN, and this runtime data is subsequently
    # assigned to the non-root application user.
    cp -R "$BUNDLED_GEOMETRY_DIR/." "$GEOMETRY_DIR/"
    echo "Seeded reviewed geometry datasets into $GEOMETRY_DIR"
  else
    python - <<'PY'
import json
import os
import shutil
from pathlib import Path

geometry_dir = Path(os.environ.get("METEOLENS_GEOMETRY_DIR", "/data/geometry"))
bundled_dir = Path(os.environ.get("METEOLENS_BUNDLED_GEOMETRY_DIR", "/app/bundled/geometry"))
target_manifest_path = geometry_dir / "manifest.json"
bundled_manifest_path = bundled_dir / "manifest.json"

target_manifest = json.loads(target_manifest_path.read_text(encoding="utf-8"))
bundled_manifest = json.loads(bundled_manifest_path.read_text(encoding="utf-8"))
target_datasets = target_manifest.setdefault("datasets", [])
existing_keys = {
    entry.get("key")
    for entry in target_datasets
    if isinstance(entry, dict) and entry.get("key")
}

added = []
for entry in bundled_manifest.get("datasets", []):
    if not isinstance(entry, dict):
        continue
    key = entry.get("key")
    file_name = entry.get("file")
    if not key or key in existing_keys:
        continue
    if not file_name:
        raise SystemExit(f"Bundled geometry dataset {key!r} has no file.")
    source_file = bundled_dir / file_name
    if not source_file.exists():
        raise SystemExit(f"Bundled geometry file missing: {source_file}")
    shutil.copy2(source_file, geometry_dir / file_name)
    target_datasets.append(entry)
    existing_keys.add(key)
    added.append(key)

if added:
    target_datasets.sort(key=lambda item: item.get("key", ""))
    target_manifest["format_version"] = max(
        int(target_manifest.get("format_version", 0) or 0),
        int(bundled_manifest.get("format_version", 0) or 0),
    )
    target_manifest_path.write_text(
        json.dumps(target_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "Merged bundled geometry datasets into "
        f"{geometry_dir}: {', '.join(sorted(added))}"
    )
PY
  fi
fi

# The one-shot Compose init service runs this script as root so a fresh named
# volume becomes writable by the long-running, non-root backend. This must run
# after geometry seeding: with capabilities dropped except CHOWN, root cannot
# create files in a directory it has already handed to the service user.
if [ "$(id -u)" = "0" ]; then
  mkdir -p /data
  chown -R meteolens:meteolens /data
fi

exec "$@"
