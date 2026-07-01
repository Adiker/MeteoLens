"""Load reviewed geometry datasets from the local cache directory."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)


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
            dataset = GeometryDataset(
                key=entry["key"],
                title=entry.get("title", entry["key"]),
                source=entry.get("source", "unknown"),
                license_note=entry.get("license_note", ""),
            )
            file_name = entry.get("file")
            if not file_name:
                dataset.error = "manifest entry missing file"
                self._datasets[dataset.key] = dataset
                continue
            file_path = self.geometry_dir / file_name
            if not file_path.exists():
                dataset.error = f"missing file {file_name}"
                self._datasets[dataset.key] = dataset
                continue
            try:
                payload = json.loads(file_path.read_text(encoding="utf-8"))
                dataset.features = _features_from_geojson(
                    payload,
                    dataset_key=dataset.key,
                    source_file=file_name,
                )
                dataset.loaded = True
            except (OSError, ValueError, TypeError, KeyError) as exc:
                dataset.error = str(exc)
            self._datasets[dataset.key] = dataset

    @property
    def datasets(self) -> list[GeometryDataset]:
        return list(self._datasets.values())

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
        return None

    def status(self) -> list[dict[str, Any]]:
        return [
            {
                "key": dataset.key,
                "title": dataset.title,
                "source": dataset.source,
                "license_note": dataset.license_note,
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
