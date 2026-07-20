"""Load reviewed geometry datasets from the local cache directory.

The manifest (`manifest.json`, format_version 2) lists every reviewed dataset
together with its provenance and legal-review metadata. Datasets without an
approved review entry are never loaded; they stay visible in the status API
with an explicit error so partial availability is not hidden.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.geometry.validation import validate_dataset

logger = logging.getLogger(__name__)

MANIFEST_FORMAT_VERSION = 2

REVIEW_METADATA_FIELDS = (
    "provider",
    "canonical_url",
    "license_url",
    "license_note",
    "attribution",
    "public_use",
    "commercial_use",
    "redistribution_note",
    "update_cadence",
    "known_limitations",
    "dataset_version",
)


@dataclass
class GeometryFeature:
    id: str
    code: str
    label: str | None
    geometry_type: str
    coordinates: Any
    source_file: str
    dataset_key: str
    province_code: str | None = None
    county_code: str | None = None
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class GeometryDataset:
    key: str
    title: str
    source: str
    license_note: str
    provider: str | None = None
    canonical_url: str | None = None
    license_url: str | None = None
    attribution: str | None = None
    public_use: bool | None = None
    commercial_use: bool | None = None
    redistribution_note: str | None = None
    update_cadence: str | None = None
    known_limitations: str | None = None
    dataset_version: str | None = None
    review_status: str | None = None
    reviewed_at: str | None = None
    reviewed_by: str | None = None
    review_notes: str | None = None
    features: list[GeometryFeature] = field(default_factory=list)
    loaded: bool = False
    error: str | None = None


class GeometryStore:
    def __init__(self, geometry_dir: Path) -> None:
        self.geometry_dir = geometry_dir
        self._datasets: dict[str, GeometryDataset] = {}

    def load_all(self) -> None:
        self.geometry_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = self.geometry_dir / "manifest.json"
        if not manifest_path.exists():
            logger.info("No geometry manifest at %s", manifest_path)
            return

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for entry in manifest.get("datasets", []):
            dataset = _dataset_from_manifest_entry(entry)
            self._datasets[dataset.key] = dataset
            if dataset.error is not None:
                continue

            if dataset.review_status != "approved":
                dataset.error = (
                    "dataset_not_reviewed: manifest entry has no approved review; "
                    "re-import it with the geometry import CLI"
                )
                continue

            file_name = entry.get("file")
            if not file_name:
                dataset.error = "manifest entry missing file"
                continue
            file_path = self.geometry_dir / file_name
            if not file_path.exists():
                dataset.error = f"missing file {file_name}"
                continue
            try:
                payload = json.loads(file_path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                dataset.error = str(exc)
                continue

            report = validate_dataset(dataset.key, payload)
            if not report.ok:
                dataset.error = "invalid_dataset: " + "; ".join(report.issues[:3])
                logger.warning(
                    "Geometry dataset %s rejected: %s", dataset.key, dataset.error
                )
                continue

            dataset.features = _features_from_geojson(
                payload,
                dataset_key=dataset.key,
                source_file=file_name,
            )
            dataset.loaded = True

    @property
    def datasets(self) -> list[GeometryDataset]:
        return list(self._datasets.values())

    def get_dataset(self, key: str) -> GeometryDataset | None:
        return self._datasets.get(key)

    def features_for_dataset(self, key: str) -> list[GeometryFeature]:
        dataset = self._datasets.get(key)
        if dataset is None:
            return []
        return dataset.features

    def find_by_code(self, *, dataset_key: str, code: str) -> GeometryFeature | None:
        normalized = code.strip()
        for feature in self.features_for_dataset(dataset_key):
            if feature.code == normalized:
                return feature
            # Hydro basins may dissolve multiple IMGW kod_zlewni onto one
            # geometry; aliases live in kod_zlewni_codes.
            aliases = feature.properties.get("kod_zlewni_codes")
            if isinstance(aliases, list) and normalized in {
                str(item).strip() for item in aliases if item not in (None, "")
            }:
                return feature
        return None

    def status(self) -> list[dict[str, Any]]:
        return [
            {
                "key": dataset.key,
                "title": dataset.title,
                "source": dataset.source,
                "license_note": dataset.license_note,
                "provider": dataset.provider,
                "canonical_url": dataset.canonical_url,
                "license_url": dataset.license_url,
                "attribution": dataset.attribution,
                "public_use": dataset.public_use,
                "commercial_use": dataset.commercial_use,
                "redistribution_note": dataset.redistribution_note,
                "update_cadence": dataset.update_cadence,
                "known_limitations": dataset.known_limitations,
                "dataset_version": dataset.dataset_version,
                "review_status": dataset.review_status,
                "reviewed_at": dataset.reviewed_at,
                "loaded": dataset.loaded,
                "feature_count": len(dataset.features),
                "error": dataset.error,
            }
            for dataset in self.datasets
        ]


@lru_cache
def get_geometry_store() -> GeometryStore:
    settings = get_settings()
    store = GeometryStore(settings.geometry_dir)
    store.load_all()
    return store


def reset_geometry_store() -> None:
    get_geometry_store.cache_clear()


def _dataset_from_manifest_entry(entry: dict[str, Any]) -> GeometryDataset:
    review = entry.get("review") or {}
    dataset = GeometryDataset(
        key=entry.get("key", "unknown"),
        title=entry.get("title", entry.get("key", "unknown")),
        source=entry.get("source", entry.get("provider", "unknown")),
        license_note=entry.get("license_note", ""),
        provider=entry.get("provider"),
        canonical_url=entry.get("canonical_url"),
        license_url=entry.get("license_url"),
        attribution=entry.get("attribution"),
        public_use=entry.get("public_use"),
        commercial_use=entry.get("commercial_use"),
        redistribution_note=entry.get("redistribution_note"),
        update_cadence=entry.get("update_cadence"),
        known_limitations=entry.get("known_limitations"),
        dataset_version=entry.get("dataset_version"),
        review_status=review.get("status"),
        reviewed_at=review.get("reviewed_at"),
        reviewed_by=review.get("reviewed_by"),
        review_notes=review.get("notes"),
    )
    if "key" not in entry:
        dataset.error = "manifest entry missing key"
    return dataset


def _features_from_geojson(
    payload: dict[str, Any],
    *,
    dataset_key: str,
    source_file: str,
) -> list[GeometryFeature]:
    features: list[GeometryFeature] = []
    for index, feature in enumerate(payload.get("features", [])):
        properties = feature.get("properties", {})
        code = str(
            properties.get("teryt")
            or properties.get("code")
            or properties.get("basin_code")
            or properties.get("TERYT")
            or properties.get("id")
            or index
        )
        geometry = feature.get("geometry") or {}
        province_code = properties.get("province_code")
        county_code = properties.get("county_code")
        features.append(
            GeometryFeature(
                id=f"{dataset_key}:{code}",
                code=code,
                label=properties.get("name") or properties.get("label"),
                geometry_type=geometry.get("type", "Unknown"),
                coordinates=geometry.get("coordinates"),
                source_file=source_file,
                dataset_key=dataset_key,
                province_code=str(province_code) if province_code is not None else None,
                county_code=str(county_code) if county_code is not None else None,
                properties=properties,
            )
        )
    return features
