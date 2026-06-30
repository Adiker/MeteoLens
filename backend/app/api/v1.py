import csv
from datetime import UTC, datetime
from io import StringIO
from math import asin, cos, radians, sin, sqrt
from typing import Annotated, Any, Literal, NoReturn

from fastapi import APIRouter, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from app.core.config import get_settings
from app.imgw.cache import CachedSourcePayload, CacheStatus, SourceCache
from app.imgw.parsers.utils import SOURCE_TIMEZONE
from app.imgw.sources import SOURCE_BY_KEY, SOURCE_DEFINITIONS
from app.normalization.models import (
    ATTRIBUTION,
    PROCESSED_NOTICE,
    NormalizedRecord,
    Observation,
    SourceMetadata,
    Station,
    Warning,
)

router = APIRouter(prefix="/api/v1", tags=["v1"])
NORMALIZED_RECORD_ADAPTER = TypeAdapter(NormalizedRecord)
STATION_SOURCE_KEYS = ("synop", "hydro", "meteo")
WARNING_SOURCE_KEYS = ("warningsmeteo", "warningshydro")
MAP_LAYER_DEFINITIONS = {
    "synop_stations": {
        "title": "Stacje synoptyczne",
        "source_keys": ("synop",),
        "kind": "station",
        "station_type": "synop",
    },
    "hydro_stations": {
        "title": "Stacje hydrologiczne",
        "source_keys": ("hydro",),
        "kind": "station",
        "station_type": "hydro",
    },
    "meteo_stations": {
        "title": "Stacje meteorologiczne",
        "source_keys": ("meteo",),
        "kind": "station",
        "station_type": "meteo",
    },
    "warnings_meteo": {
        "title": "Ostrzeżenia meteorologiczne",
        "source_keys": ("warningsmeteo",),
        "kind": "warning",
        "warning_type": "meteo",
    },
    "warnings_hydro": {
        "title": "Ostrzeżenia hydrologiczne",
        "source_keys": ("warningshydro",),
        "kind": "warning",
        "warning_type": "hydro",
    },
}


class SourceDescriptor(BaseModel):
    key: str
    title: str
    url: str
    parser_status: str
    cache_status: str
    cache: CacheStatus
    notes: str | None = None


class SourcesResponse(BaseModel):
    retrieved_at: datetime
    sources: list[SourceDescriptor]


class CacheSourceState(BaseModel):
    source_key: str
    status: CacheStatus


class EmptyState(BaseModel):
    code: str
    message: str
    source_keys: list[str] = Field(default_factory=list)


class ApiEnvelope(BaseModel):
    generated_at: datetime
    cache: list[CacheSourceState]
    empty_state: EmptyState | None = None


class StationListItem(BaseModel):
    id: str
    source_id: str
    source_key: str
    station_type: Literal["synop", "hydro", "meteo"]
    name: str
    lat: float | None = None
    lon: float | None = None
    region: str | None = None
    watercourse: str | None = None
    latest_observed_at: datetime | None = None
    data_delay_seconds: int | None = None
    missing_fields: list[str] = Field(default_factory=list)
    source: SourceMetadata
    raw_available: bool = True


class StationsResponse(ApiEnvelope):
    stations: list[StationListItem]


class StationResponse(BaseModel):
    generated_at: datetime
    station: dict[str, Any]
    latest_observed_at: datetime | None = None
    data_delay_seconds: int | None = None
    raw_available: bool = True


class ObservationResponse(BaseModel):
    generated_at: datetime
    station_id: str
    source: SourceMetadata
    observations: list[dict[str, Any]]
    empty_state: EmptyState | None = None


class WarningsResponse(ApiEnvelope):
    warnings: list[dict[str, Any]]


class WarningResponse(BaseModel):
    generated_at: datetime
    warning: dict[str, Any]
    geometry_status: str
    raw_available: bool = True


class LocationSummaryResponse(ApiEnvelope):
    location: dict[str, float]
    radius_km: float
    nearest_stations: list[dict[str, Any]]
    warnings: list[dict[str, Any]]
    notes: list[str] = Field(default_factory=list)


class MapLayerResponse(BaseModel):
    key: str
    title: str
    source_keys: list[str]
    sources: list[SourceMetadata]
    geojson: dict[str, Any]
    records: list[dict[str, Any]] = Field(default_factory=list)
    missing_geometry: list[dict[str, Any]] = Field(default_factory=list)


class MapLayersResponse(ApiEnvelope):
    layers: list[MapLayerResponse]


@router.get("/sources", response_model=SourcesResponse)
def list_sources() -> SourcesResponse:
    settings = get_settings()
    base_url = str(settings.imgw_base_url).rstrip("/")
    cache = SourceCache(settings.cache_dir)
    sources = []
    for source in SOURCE_DEFINITIONS:
        cache_status = cache.status(
            source.key,
            ttl_seconds=source.default_ttl_seconds,
        )
        sources.append(
            SourceDescriptor(
                key=source.key,
                title=source.title,
                url=source.url(base_url),
                parser_status=source.parser_status,
                cache_status=cache_status.status,
                cache=cache_status,
                notes=source.notes,
            )
        )
    return SourcesResponse(retrieved_at=datetime.now(UTC), sources=sources)


@router.get("/map/layers", response_model=MapLayersResponse)
def get_map_layers(
    layers: Annotated[str | None, Query(description="Comma-separated layer keys.")] = None,
    bbox: Annotated[str | None, Query(description="minLon,minLat,maxLon,maxLat")] = None,
) -> MapLayersResponse:
    requested_layers = _parse_layers(layers)
    bbox_values = _parse_bbox(bbox)
    cache = _source_cache()
    states = _cache_states(
        cache,
        [source for layer in requested_layers for source in layer["source_keys"]],
    )
    records = _records_from_cache(cache, STATION_SOURCE_KEYS + WARNING_SOURCE_KEYS)
    response_layers: list[MapLayerResponse] = []

    for layer in requested_layers:
        layer_records = _records_for_layer(records, layer)
        features: list[dict[str, Any]] = []
        non_spatial_records: list[dict[str, Any]] = []
        missing_geometry: list[dict[str, Any]] = []
        sources = _unique_sources(layer_records)

        for record in layer_records:
            if isinstance(record, Station):
                if record.lat is None or record.lon is None:
                    missing_geometry.append(_missing_geometry(record))
                    continue
                if bbox_values is not None and not _inside_bbox(
                    record.lon,
                    record.lat,
                    bbox_values,
                ):
                    continue
                features.append(_station_feature(record))
            elif isinstance(record, Warning):
                non_spatial_records.append(_warning_map_record(record))
                missing_geometry.append(_missing_warning_geometry(record))

        response_layers.append(
            MapLayerResponse(
                key=str(layer["key"]),
                title=str(layer["title"]),
                source_keys=list(layer["source_keys"]),
                sources=sources,
                geojson={"type": "FeatureCollection", "features": features},
                records=non_spatial_records,
                missing_geometry=missing_geometry,
            )
        )

    return MapLayersResponse(
        generated_at=datetime.now(UTC),
        cache=states,
        empty_state=_collection_empty_state(
            records,
            _map_layers_have_content(response_layers),
            STATION_SOURCE_KEYS + WARNING_SOURCE_KEYS,
            filter_message="No map layer data matched the requested layers or bbox.",
        ),
        layers=response_layers,
    )


@router.get("/stations", response_model=StationsResponse)
def list_stations(
    station_type: Annotated[
        Literal["synop", "hydro", "meteo"] | None,
        Query(alias="type"),
    ] = None,
    q: str | None = None,
    bbox: Annotated[str | None, Query(description="minLon,minLat,maxLon,maxLat")] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> StationsResponse:
    bbox_values = _parse_bbox(bbox)
    cache = _source_cache()
    records = _stations_from_cache(cache)
    stations = [
        _station_list_item(station)
        for station in records
        if _station_matches(station, station_type=station_type, q=q, bbox=bbox_values)
    ][:limit]

    return StationsResponse(
        generated_at=datetime.now(UTC),
        cache=_cache_states(cache, STATION_SOURCE_KEYS),
        empty_state=_collection_empty_state(
            records,
            stations,
            STATION_SOURCE_KEYS,
            filter_message="No stations matched the requested filters.",
        ),
        stations=stations,
    )


@router.get("/stations/{station_id}", response_model=StationResponse)
def get_station(station_id: str) -> StationResponse:
    station = _get_station_or_404(station_id)
    latest_observed_at = _latest_observed_at(station.observations)
    return StationResponse(
        generated_at=datetime.now(UTC),
        station=station.model_dump(mode="json"),
        latest_observed_at=latest_observed_at,
        data_delay_seconds=_data_delay_seconds(latest_observed_at, station.source.retrieved_at),
    )


@router.get("/stations/{station_id}/observations", response_model=ObservationResponse)
def get_station_observations(
    station_id: str,
    metric: str | None = None,
    observed_from: Annotated[datetime | None, Query(alias="from")] = None,
    observed_to: Annotated[datetime | None, Query(alias="to")] = None,
) -> ObservationResponse:
    station = _get_station_or_404(station_id)
    observations = [
        _observation_payload(observation, station.source.retrieved_at)
        for observation in station.observations
        if _observation_matches(
            observation,
            metric=metric,
            observed_from=observed_from,
            observed_to=observed_to,
        )
    ]
    return ObservationResponse(
        generated_at=datetime.now(UTC),
        station_id=station.id,
        source=station.source,
        observations=observations,
        empty_state=None
        if observations
        else EmptyState(
            code="no_observations",
            message="No observations matched the requested filters.",
            source_keys=[station.source_key],
        ),
    )


@router.get("/warnings", response_model=WarningsResponse)
def list_warnings(
    warning_type: Annotated[
        Literal["meteo", "hydro"] | None,
        Query(alias="type"),
    ] = None,
    active_at: datetime | None = None,
    level: int | None = None,
    phenomenon: str | None = None,
    teryt: str | None = None,
    basin: str | None = None,
) -> WarningsResponse:
    cache = _source_cache()
    records = _warnings_from_cache(cache)
    warnings = [
        _warning_payload(warning)
        for warning in records
        if _warning_matches(
            warning,
            warning_type=warning_type,
            active_at=active_at,
            level=level,
            phenomenon=phenomenon,
            teryt=teryt,
            basin=basin,
        )
    ]
    return WarningsResponse(
        generated_at=datetime.now(UTC),
        cache=_cache_states(cache, WARNING_SOURCE_KEYS),
        empty_state=_collection_empty_state(
            records,
            warnings,
            WARNING_SOURCE_KEYS,
            filter_message="No warnings matched the requested filters.",
        ),
        warnings=warnings,
    )


@router.get("/warnings/{warning_id}", response_model=WarningResponse)
def get_warning(warning_id: str) -> WarningResponse:
    warning = _get_warning_or_404(warning_id)
    return WarningResponse(
        generated_at=datetime.now(UTC),
        warning=_warning_payload(warning),
        geometry_status="missing_area_geometry_dataset",
    )


@router.get("/location/summary", response_model=LocationSummaryResponse)
def get_location_summary(
    lat: Annotated[float, Query(ge=-90, le=90)],
    lon: Annotated[float, Query(ge=-180, le=180)],
    radius_km: Annotated[float, Query(gt=0, le=500)] = 50,
) -> LocationSummaryResponse:
    cache = _source_cache()
    all_stations = _stations_from_cache(cache)
    all_warnings = _warnings_from_cache(cache)
    stations = [
        station
        for station in all_stations
        if station.lat is not None and station.lon is not None
    ]
    station_distances = [
        (station, _distance_km(lat, lon, station.lat, station.lon))
        for station in stations
    ]
    nearest = [
        {
            **_station_list_item(station).model_dump(mode="json"),
            "distance_km": round(distance, 3),
        }
        for station, distance in sorted(station_distances, key=lambda item: item[1])
        if distance <= radius_km
    ][:10]
    now = datetime.now(UTC)
    active_warnings = [
        _warning_payload(warning)
        for warning in all_warnings
        if _warning_matches(warning, active_at=now)
    ]

    cached_records = all_stations + all_warnings
    return LocationSummaryResponse(
        generated_at=now,
        cache=_cache_states(cache, STATION_SOURCE_KEYS + WARNING_SOURCE_KEYS),
        location={"lat": lat, "lon": lon},
        radius_km=radius_km,
        nearest_stations=nearest,
        warnings=active_warnings,
        empty_state=_collection_empty_state(
            cached_records,
            nearest or active_warnings,
            STATION_SOURCE_KEYS + WARNING_SOURCE_KEYS,
            filter_code="no_location_data",
            filter_message="No cached station or warning data matched this location summary.",
        ),
        notes=[
            "Warnings are not spatially matched yet because TERYT and basin "
            "geometry datasets are not cached."
        ],
    )


@router.get("/export/station/{station_id}.csv")
def export_station_csv(station_id: str) -> PlainTextResponse:
    station = _get_station_or_404(station_id)
    buffer = StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "station_id",
            "station_name",
            "metric",
            "value",
            "unit",
            "observed_at",
            "retrieved_at",
            "data_delay_seconds",
            "missing",
            "raw_field",
            "source_key",
            "attribution",
            "processed_notice",
            "missing_fields",
        ],
    )
    writer.writeheader()
    for observation in station.observations:
        writer.writerow(
            {
                "station_id": station.id,
                "station_name": station.name,
                "metric": observation.metric,
                "value": "" if observation.value is None else observation.value,
                "unit": "" if observation.unit is None else observation.unit,
                "observed_at": observation.observed_at.isoformat()
                if observation.observed_at
                else "",
                "retrieved_at": station.source.retrieved_at.isoformat(),
                "data_delay_seconds": _data_delay_seconds(
                    observation.observed_at,
                    station.source.retrieved_at,
                ),
                "missing": observation.missing,
                "raw_field": observation.raw_field,
                "source_key": station.source_key,
                "attribution": station.source.attribution,
                "processed_notice": station.source.processed_notice,
                "missing_fields": ";".join(station.missing_fields),
            }
        )
    return PlainTextResponse(
        buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{station.id}.csv"'},
    )


@router.get("/export/station/{station_id}.json")
def export_station_json(station_id: str) -> JSONResponse:
    station = _get_station_or_404(station_id)
    return JSONResponse(
        content=jsonable_encoder(
            {
                "generated_at": datetime.now(UTC),
                "attribution": station.source.attribution,
                "processed_notice": station.source.processed_notice,
                "station": station.model_dump(mode="json"),
            }
        ),
        headers={"Content-Disposition": f'attachment; filename="{station.id}.json"'},
    )


@router.get("/export/map.geojson")
def export_map_geojson(
    layers: Annotated[str | None, Query(description="Comma-separated layer keys.")] = None,
    bbox: Annotated[str | None, Query(description="minLon,minLat,maxLon,maxLat")] = None,
) -> JSONResponse:
    response = get_map_layers(layers=layers, bbox=bbox)
    features: list[dict[str, Any]] = []
    non_spatial_records: list[dict[str, Any]] = []
    missing_geometry: list[dict[str, Any]] = []
    for layer in response.layers:
        features.extend(layer.geojson["features"])
        non_spatial_records.extend(layer.records)
        missing_geometry.extend(layer.missing_geometry)

    geojson = {
        "type": "FeatureCollection",
        "features": features,
        "generated_at": datetime.now(UTC),
        "attribution": ATTRIBUTION,
        "processed_notice": PROCESSED_NOTICE,
        "cache": [state.model_dump(mode="json") for state in response.cache],
        "non_spatial_records": non_spatial_records,
        "missing_geometry": missing_geometry,
    }
    return JSONResponse(
        content=jsonable_encoder(geojson),
        media_type="application/geo+json",
        headers={"Content-Disposition": 'attachment; filename="meteolens-map.geojson"'},
    )


def _source_cache() -> SourceCache:
    return SourceCache(get_settings().cache_dir)


def _cache_states(
    cache: SourceCache,
    source_keys: list[str] | tuple[str, ...],
) -> list[CacheSourceState]:
    unique_keys = list(dict.fromkeys(source_keys))
    return [
        CacheSourceState(
            source_key=source_key,
            status=cache.status(
                source_key,
                ttl_seconds=SOURCE_BY_KEY[source_key].default_ttl_seconds,
            ),
        )
        for source_key in unique_keys
    ]


def _read_cached_payload(cache: SourceCache, source_key: str) -> CachedSourcePayload | None:
    try:
        return cache.read(source_key)
    except (OSError, ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": "cache_invalid",
                    "message": f"Cached source {source_key} could not be read.",
                    "source_key": source_key,
                    "detail": str(exc),
                }
            },
        ) from exc


def _records_from_cache(
    cache: SourceCache,
    source_keys: tuple[str, ...],
) -> list[NormalizedRecord]:
    records: list[NormalizedRecord] = []
    for source_key in source_keys:
        payload = _read_cached_payload(cache, source_key)
        if payload is None or not payload.normalized_payload:
            continue
        for row in payload.normalized_payload:
            try:
                records.append(NORMALIZED_RECORD_ADAPTER.validate_python(row))
            except ValidationError as exc:
                raise HTTPException(
                    status_code=503,
                    detail={
                        "error": {
                            "code": "cache_invalid",
                            "message": (
                                f"Cached source {source_key} contains invalid normalized records."
                            ),
                            "source_key": source_key,
                            "detail": str(exc),
                        }
                    },
                ) from exc
    return records


def _stations_from_cache(cache: SourceCache) -> list[Station]:
    return [
        record
        for record in _records_from_cache(cache, STATION_SOURCE_KEYS)
        if isinstance(record, Station)
    ]


def _warnings_from_cache(cache: SourceCache) -> list[Warning]:
    return [
        record
        for record in _records_from_cache(cache, WARNING_SOURCE_KEYS)
        if isinstance(record, Warning)
    ]


def _collection_empty_state(
    cached_records: list[Any],
    filtered_results: list[Any] | bool,
    source_keys: tuple[str, ...],
    *,
    filter_code: str = "no_matching_records",
    filter_message: str = "No records matched the requested filters.",
) -> EmptyState | None:
    if not cached_records:
        return EmptyState(
            code="cache_empty",
            message="No cached normalized records are available. Refresh IMGW sources first.",
            source_keys=list(source_keys),
        )
    has_results = filtered_results if isinstance(filtered_results, bool) else bool(filtered_results)
    if not has_results:
        return EmptyState(
            code=filter_code,
            message=filter_message,
            source_keys=list(source_keys),
        )
    return None


def _map_layers_have_content(layers: list[MapLayerResponse]) -> bool:
    for layer in layers:
        if (
            layer.geojson["features"]
            or layer.records
            or layer.missing_geometry
        ):
            return True
    return False


def _get_station_or_404(station_id: str) -> Station:
    cache = _source_cache()
    stations = _stations_from_cache(cache)
    for station in stations:
        if station.id == station_id:
            return station
    _raise_not_found_or_empty(station_id, stations, STATION_SOURCE_KEYS, "station")


def _get_warning_or_404(warning_id: str) -> Warning:
    cache = _source_cache()
    warnings = _warnings_from_cache(cache)
    for warning in warnings:
        if warning.id == warning_id:
            return warning
    _raise_not_found_or_empty(warning_id, warnings, WARNING_SOURCE_KEYS, "warning")


def _raise_not_found_or_empty(
    record_id: str,
    records: list[Any],
    source_keys: tuple[str, ...],
    record_kind: str,
) -> NoReturn:
    if not records:
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": "cache_empty",
                    "message": f"No cached {record_kind} data is available.",
                    "source_keys": list(source_keys),
                }
            },
        )
    raise HTTPException(
        status_code=404,
        detail={
            "error": {
                "code": "not_found",
                "message": f"{record_kind.capitalize()} was not found.",
                "id": record_id,
            }
        },
    )


def _parse_layers(layers: str | None) -> list[dict[str, Any]]:
    if layers is None or not layers.strip():
        keys = list(MAP_LAYER_DEFINITIONS)
    else:
        keys = [key.strip() for key in layers.split(",") if key.strip()]

    unsupported = [key for key in keys if key not in MAP_LAYER_DEFINITIONS]
    if unsupported:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "unsupported_layer",
                    "message": "One or more map layers are not supported.",
                    "layers": unsupported,
                }
            },
        )

    return [{"key": key, **MAP_LAYER_DEFINITIONS[key]} for key in keys]


def _parse_bbox(bbox: str | None) -> tuple[float, float, float, float] | None:
    if bbox is None:
        return None
    try:
        min_lon, min_lat, max_lon, max_lat = [float(value) for value in bbox.split(",")]
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "invalid_filter",
                    "message": "bbox must use minLon,minLat,maxLon,maxLat.",
                }
            },
        ) from exc
    if min_lon > max_lon or min_lat > max_lat:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "invalid_filter",
                    "message": "bbox minimums must not exceed maximums.",
                }
            },
        )
    return min_lon, min_lat, max_lon, max_lat


def _inside_bbox(lon: float, lat: float, bbox: tuple[float, float, float, float]) -> bool:
    min_lon, min_lat, max_lon, max_lat = bbox
    return min_lon <= lon <= max_lon and min_lat <= lat <= max_lat


def _records_for_layer(
    records: list[NormalizedRecord],
    layer: dict[str, Any],
) -> list[NormalizedRecord]:
    if layer["kind"] == "station":
        return [
            record
            for record in records
            if isinstance(record, Station) and record.station_type == layer["station_type"]
        ]
    return [
        record
        for record in records
        if isinstance(record, Warning) and record.warning_type == layer["warning_type"]
    ]


def _unique_sources(records: list[NormalizedRecord]) -> list[SourceMetadata]:
    sources: dict[str, SourceMetadata] = {}
    for record in records:
        sources[record.source.source_key] = record.source
    return list(sources.values())


def _station_feature(station: Station) -> dict[str, Any]:
    return {
        "type": "Feature",
        "id": station.id,
        "geometry": {"type": "Point", "coordinates": [station.lon, station.lat]},
        "properties": {
            **_station_list_item(station).model_dump(mode="json"),
            "observations": [
                _observation_payload(observation, station.source.retrieved_at)
                for observation in station.observations
            ],
        },
    }


def _warning_map_record(warning: Warning) -> dict[str, Any]:
    return {
        **_warning_payload(warning),
        "geometry_status": "missing_area_geometry_dataset",
        "area_codes": [area.code for area in warning.areas],
    }


def _missing_geometry(station: Station) -> dict[str, Any]:
    return {
        "id": station.id,
        "source_key": station.source_key,
        "reason": "missing_lat_lon",
        "missing_fields": [
            field for field in ("lat", "lon") if getattr(station, field) is None
        ],
    }


def _missing_warning_geometry(warning: Warning) -> dict[str, Any]:
    return {
        "id": warning.id,
        "source_key": warning.source_key,
        "reason": "missing_area_geometry_dataset",
        "area_codes": [area.code for area in warning.areas],
    }


def _station_list_item(station: Station) -> StationListItem:
    latest_observed_at = _latest_observed_at(station.observations)
    return StationListItem(
        id=station.id,
        source_id=station.source_id,
        source_key=station.source_key,
        station_type=station.station_type,
        name=station.name,
        lat=station.lat,
        lon=station.lon,
        region=station.region,
        watercourse=station.watercourse,
        latest_observed_at=latest_observed_at,
        data_delay_seconds=_data_delay_seconds(latest_observed_at, station.source.retrieved_at),
        missing_fields=station.missing_fields,
        source=station.source,
    )


def _station_matches(
    station: Station,
    *,
    station_type: Literal["synop", "hydro", "meteo"] | None,
    q: str | None,
    bbox: tuple[float, float, float, float] | None,
) -> bool:
    if station_type is not None and station.station_type != station_type:
        return False
    if q is not None and q.casefold() not in station.name.casefold():
        return False
    if bbox is not None:
        if station.lon is None or station.lat is None:
            return False
        return _inside_bbox(station.lon, station.lat, bbox)
    return True


def _latest_observed_at(observations: list[Observation]) -> datetime | None:
    observed_at_values = [
        observation.observed_at
        for observation in observations
        if observation.observed_at is not None
    ]
    return max(observed_at_values) if observed_at_values else None


def _data_delay_seconds(observed_at: datetime | None, retrieved_at: datetime) -> int | None:
    if observed_at is None:
        return None
    return max(0, round((retrieved_at - observed_at).total_seconds()))


def _observation_payload(
    observation: Observation,
    retrieved_at: datetime,
) -> dict[str, Any]:
    payload = observation.model_dump(mode="json")
    payload["data_delay_seconds"] = _data_delay_seconds(observation.observed_at, retrieved_at)
    return payload


def _normalize_query_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=SOURCE_TIMEZONE)
    return value.astimezone(SOURCE_TIMEZONE)


def _compare_datetimes(left: datetime | None, right: datetime | None) -> int | None:
    if left is None or right is None:
        return None
    left_normalized = _normalize_query_datetime(left)
    right_normalized = _normalize_query_datetime(right)
    if left_normalized == right_normalized:
        return 0
    return -1 if left_normalized < right_normalized else 1


def _observation_matches(
    observation: Observation,
    *,
    metric: str | None,
    observed_from: datetime | None,
    observed_to: datetime | None,
) -> bool:
    if metric is not None and observation.metric != metric:
        return False
    observed_at = observation.observed_at
    if observed_from is not None:
        comparison = _compare_datetimes(observed_at, observed_from)
        if comparison is None or comparison < 0:
            return False
    if observed_to is not None:
        comparison = _compare_datetimes(observed_at, observed_to)
        if comparison is None or comparison > 0:
            return False
    return True


def _warning_payload(warning: Warning) -> dict[str, Any]:
    payload = warning.model_dump(mode="json")
    payload["area_codes"] = [area.code for area in warning.areas]
    payload["raw_available"] = True
    return payload


def _warning_matches(
    warning: Warning,
    *,
    warning_type: Literal["meteo", "hydro"] | None = None,
    active_at: datetime | None = None,
    level: int | None = None,
    phenomenon: str | None = None,
    teryt: str | None = None,
    basin: str | None = None,
) -> bool:
    if warning_type is not None and warning.warning_type != warning_type:
        return False
    if active_at is not None:
        normalized_active_at = _normalize_query_datetime(active_at)
        if warning.valid_from is not None:
            valid_from = _normalize_query_datetime(warning.valid_from)
            if normalized_active_at < valid_from:
                return False
        if warning.valid_to is not None:
            valid_to = _normalize_query_datetime(warning.valid_to)
            if normalized_active_at > valid_to:
                return False
    if level is not None and warning.level != level:
        return False
    if phenomenon is not None and phenomenon.casefold() not in warning.event.casefold():
        return False
    if teryt is not None and not any(
        area.area_type == "teryt" and area.code == teryt for area in warning.areas
    ):
        return False
    if basin is not None and not any(
        area.area_type == "basin" and area.code == basin for area in warning.areas
    ):
        return False
    return True


def _distance_km(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    radius_km = 6371.0
    dlat = radians(lat_b - lat_a)
    dlon = radians(lon_b - lon_a)
    a = (
        sin(dlat / 2) ** 2
        + cos(radians(lat_a)) * cos(radians(lat_b)) * sin(dlon / 2) ** 2
    )
    return 2 * radius_km * asin(sqrt(a))
