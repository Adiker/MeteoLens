#!/bin/sh
set -eu

GEOMETRY_DIR="${METEOLENS_GEOMETRY_DIR:-/data/geometry}"
BUNDLED_GEOMETRY_DIR="${METEOLENS_BUNDLED_GEOMETRY_DIR:-/app/bundled/geometry}"

if [ ! -f "$GEOMETRY_DIR/manifest.json" ] && [ -f "$BUNDLED_GEOMETRY_DIR/manifest.json" ]; then
  mkdir -p "$GEOMETRY_DIR"
  cp -a "$BUNDLED_GEOMETRY_DIR/." "$GEOMETRY_DIR/"
  echo "Seeded reviewed geometry datasets into $GEOMETRY_DIR"
fi

exec "$@"
