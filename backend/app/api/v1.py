import csv
from datetime import UTC, date, datetime
from io import StringIO
from math import asin, cos, radians, sin, sqrt
from typing import Annotated, Any, Literal, NoReturn
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from app.core.config import get_settings
from app.geometry.loader import get_geometry_store
from app.geometry.spatial import (
    resolve_warning_geometries,
    warning_matches_spatial_filters,
    warnings_matching_point,
)
from app.imgw.archive import ArchiveBackfillError, SynopDailyArchiveBackfiller
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
from app.products import rendering
from app.products.catalog import list_products, product_detail
from app.products.detail_cache import ProductDetailCache
from app.products.timeline import build_map_timeline
from app.services import observation_history as history_service
from app.services.freshness import ALERTING_DISCLAIMER, build_freshness_report

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
    coordinate_source: str | None = None
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
    series_kind: Literal["history", "snapshot"] = "snapshot"
    series_origin: Literal["live_refresh", "archive_import", "mixed"] = "live_refresh"
    origin_counts: dict[str, int] = Field(default_factory=dict)
    interval: str = "raw"
    empty_state: EmptyState | None = None


class ArchiveBackfillResponse(BaseModel):
    id: str
    source_key: str
    archive_kind: str
    status: str
    started_at: datetime
    finished_at: datetime
    observed_from: date
    observed_to: date
    files_total: int
    files_processed: int
    rows_seen: int
    observations_seen: int
    observations_inserted: int
    observations_updated: int
    observations_unchanged: int
    parser_warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    attribution: str = ATTRIBUTION
    processed_notice: str = PROCESSED_NOTICE


class CompareResponse(BaseModel):
    generated_at: datetime
    metric: str
    interval: str
    series: dict[str, list[dict[str, Any]]]
    attribution: str = ATTRIBUTION
    processed_notice: str = PROCESSED_NOTICE


class RankingsResponse(BaseModel):
    generated_at: datetime
    metric: str
    direction: Literal["highest", "lowest"]
    rankings: list[dict[str, Any]]
    attribution: str = ATTRIBUTION
    processed_notice: str = PROCESSED_NOTICE
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


class GeometryDatasetStatus(BaseModel):
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
    loaded: bool
    feature_count: int
    error: str | None = None


class GeometryDatasetsResponse(BaseModel):
    generated_at: datetime
    datasets: list[GeometryDatasetStatus]
    manifest_present: bool


class ProductsResponse(BaseModel):
    generated_at: datetime
    retrieved_at: datetime | None = None
    research_date: str
    attribution: str
    processed_notice: str
    products: list[dict[str, Any]]
    empty_state: EmptyState | None = None


class ProductFramesResponse(BaseModel):
    generated_at: datetime
    product_id: str
    description: str
    category: str
    availability: str
    rendering_status: str
    format_notes: str
    research_date: str
    source: SourceMetadata
    retrieved_at: datetime | None = None
    frames: list[dict[str, Any]]
    frame_count: int
    limit: int
    offset: int
    missing_frames: int
    stale: bool
    renderable: dict[str, Any] | None = None
    attribution: str
    processed_notice: str
    empty_state: EmptyState | None = None
    error: str | None = None


class TimelineLayer(BaseModel):
    key: str
    product_id: str
    title: str
    kind: str
    category: str
    rendering_status: str
    frame_count: int
    missing_frames: int
    frames_renderable: bool
    renderable: dict[str, Any] | None = None
    source_time: datetime | None = None
    first_frame_time: str | None = None
    last_frame_time: str | None = None
    stale: bool
    attribution: str
    processed_notice: str
    notes: list[str] = Field(default_factory=list)


class MapTimelineResponse(BaseModel):
    generated_at: datetime
    layers: list[TimelineLayer]
    empty_state: EmptyState | None = None


class SourceFreshnessItem(BaseModel):
    source_key: str
    title: str
    cache_status: str
    last_success_at: datetime | None = None
    age_seconds: int | None = None
    record_count: int | None = None
    parser_warnings: list[str] = Field(default_factory=list)
    error: str | None = None
    ttl_seconds: int
    stale: bool
    parser_status: str
    notes: str | None = None


class FreshnessResponse(BaseModel):
    generated_at: datetime
    overall_status: str
    sources: list[SourceFreshnessItem]
    notes: list[str] = Field(default_factory=list)
    attribution: str
    processed_notice: str
    alerting_disclaimer: str


class WarningStationComparisonResponse(BaseModel):
    generated_at: datetime
    station_id: str
    station: dict[str, Any]
    observations: list[dict[str, Any]]
    warnings: list[dict[str, Any]]
    notes: list[str] = Field(default_factory=list)
    alerting_disclaimer: str
    attribution: str
    processed_notice: str
    empty_state: EmptyState | None = None


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


@router.post("/archive/backfill/synop-daily", response_model=ArchiveBackfillResponse)
def backfill_synop_daily_archive(
    observed_from: Annotated[date, Query(alias="from")],
    observed_to: Annotated[date, Query(alias="to")],
) -> ArchiveBackfillResponse:
    """Import a bounded server-side slice of public IMGW daily SYNOP archives."""
    try:
        result = SynopDailyArchiveBackfiller(get_settings()).run(
            observed_from=observed_from,
            observed_to=observed_to,
        )
    except ArchiveBackfillError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": exc.code,
                    "message": str(exc),
                    "source_key": "synop",
                }
            },
        ) from exc
    return ArchiveBackfillResponse(**result.model_dump())


@router.get("/geometry/datasets", response_model=GeometryDatasetsResponse)
def list_geometry_datasets() -> GeometryDatasetsResponse:
    settings = get_settings()
    store = get_geometry_store()
    manifest_present = (settings.geometry_dir / "manifest.json").exists()
    return GeometryDatasetsResponse(
        generated_at=datetime.now(UTC),
        datasets=[GeometryDatasetStatus(**item) for item in store.status()],
        manifest_present=manifest_present,
    )


@router.get("/products", response_model=ProductsResponse)
def get_products() -> ProductsResponse:
    payload = list_products(get_settings())
    return ProductsResponse(**payload)


@router.get("/products/{product_id}/frames", response_model=ProductFramesResponse)
def get_product_frames(
    product_id: str,
    limit: Annotated[int, Query(ge=1, le=500)] = 120,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ProductFramesResponse:
    payload = product_detail(get_settings(), product_id, limit=limit, offset=offset)
    return ProductFramesResponse(**payload)


@router.get("/products/{product_id}/render/{filename}")
def get_product_render(
    product_id: str,
    filename: str,
    variable: str = "t2m",
) -> FileResponse:
    """Serve a rendered PNG overlay for one renderable product frame.

    Renders (and downloads the source GRIB) on first request, then serves the
    cached PNG. Non-renderable products or frames return explicit errors —
    metadata-only frames are never dressed up as rendered data.
    """
    settings = get_settings()
    if not rendering.product_is_renderable(product_id):
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "not_renderable",
                    "message": "This product has no renderable map layer.",
                    "product_id": product_id,
                }
            },
        )
    cached_detail = ProductDetailCache(settings.cache_dir).read(product_id)
    if cached_detail is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": "cache_empty",
                    "message": "Product frame manifest is not cached yet.",
                    "source_keys": ["product"],
                }
            },
        )
    row = next(
        (
            item
            for item in cached_detail.files
            if isinstance(item, dict) and item.get("file") == filename
        ),
        None,
    )
    if row is None or not str(row.get("url") or ""):
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "frame_missing",
                    "message": "The requested frame is not present in the manifest.",
                    "product_id": product_id,
                    "file": filename,
                }
            },
        )
    try:
        result = rendering.render_frame(
            settings,
            product_id=product_id,
            filename=filename,
            url=str(row["url"]),
            variable_key=variable,
        )
    except rendering.RenderError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={
                "error": {
                    "code": exc.code,
                    "message": str(exc),
                    "product_id": product_id,
                    "file": filename,
                }
            },
        ) from exc

    metadata = result.metadata
    headers = {
        "Cache-Control": "public, max-age=3600",
        "X-MeteoLens-Frame-Time": str(metadata.get("frame_time") or ""),
        "X-MeteoLens-Run-Time": str(metadata.get("run_time") or ""),
        "X-MeteoLens-Retrieved-At": str(metadata.get("retrieved_at") or ""),
        "X-MeteoLens-Rendered-At": str(metadata.get("rendered_at") or ""),
        "X-MeteoLens-Variable": str(metadata.get("variable") or ""),
    }
    return FileResponse(result.png_path, media_type="image/png", headers=headers)


@router.get("/map/timeline", response_model=MapTimelineResponse)
def get_map_timeline() -> MapTimelineResponse:
    payload = build_map_timeline(get_settings())
    return MapTimelineResponse(**payload)


@router.get("/status/freshness", response_model=FreshnessResponse)
def get_freshness_status() -> FreshnessResponse:
    payload = build_freshness_report(get_settings())
    return FreshnessResponse(**payload)


@router.get(
    "/compare/warning-station/{station_id}",
    response_model=WarningStationComparisonResponse,
)
def compare_warning_station(station_id: str) -> WarningStationComparisonResponse:
    station = _get_station_or_404(station_id)
    cache = _source_cache()
    all_warnings = _warnings_from_cache(cache)
    now = datetime.now(UTC)
    active_warnings = [
        warning for warning in all_warnings if _warning_matches(warning, active_at=now)
    ]
    notes: list[str] = []
    warnings: list[dict[str, Any]] = []
    if station.lat is not None and station.lon is not None:
        geometry_store = get_geometry_store()
        polygon_matches, fallback_warnings, match_notes = warnings_matching_point(
            lat=station.lat,
            lon=station.lon,
            warnings=active_warnings,
            store=geometry_store,
        )
        warnings = polygon_matches if polygon_matches else fallback_warnings
        notes.extend(match_notes)
    else:
        notes.append(
            "Station has no coordinates; spatial warning comparison is unavailable."
        )

    observations = [
        _observation_payload(observation, station.source.retrieved_at)
        for observation in station.observations
    ]
    return WarningStationComparisonResponse(
        generated_at=now,
        station_id=station_id,
        station=station.model_dump(mode="json"),
        observations=observations,
        warnings=warnings,
        notes=notes,
        alerting_disclaimer=ALERTING_DISCLAIMER,
        attribution=ATTRIBUTION,
        processed_notice=PROCESSED_NOTICE,
        empty_state=None
        if observations or warnings
        else EmptyState(
            code="no_matching_records",
            message="No observations or active warnings matched this station.",
            source_keys=[station.source_key, "warningsmeteo", "warningshydro"],
        ),
    )


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
    now = datetime.now(UTC)
    records = [
        record
        for record in _records_from_cache(cache, STATION_SOURCE_KEYS + WARNING_SOURCE_KEYS)
        if not isinstance(record, Warning) or _warning_matches(record, active_at=now)
    ]
    geometry_store = get_geometry_store()
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
                geometry = resolve_warning_geometries(record, geometry_store)
                warning_features = geometry["geojson"]["features"]
                if bbox_values is not None:
                    warning_features = [
                        feature
                        for feature in warning_features
                        if _feature_intersects_bbox(feature, bbox_values)
                    ]
                if warning_features or geometry["unresolved_areas"] or bbox_values is None:
                    warning_record = _warning_map_record(record, geometry)
                    non_spatial_records.append(warning_record)
                if warning_features:
                    features.extend(warning_features)
                if geometry["unresolved_areas"]:
                    missing_geometry.extend(
                        _missing_warning_geometry(record, geometry["unresolved_areas"])
                    )

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


@router.get("/stations/compare", response_model=CompareResponse)
def compare_stations(
    station_ids: Annotated[str, Query(description="Comma-separated stable station IDs.")],
    metric: str,
    observed_from: Annotated[datetime | None, Query(alias="from")] = None,
    observed_to: Annotated[datetime | None, Query(alias="to")] = None,
    interval: Literal["raw", "10m", "1h", "1d"] = "raw",
    limit: Annotated[int, Query(ge=1, le=5000)] = 200,
) -> CompareResponse:
    ids = [value.strip() for value in station_ids.split(",") if value.strip()]
    if not ids:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "invalid_filter",
                    "message": "station_ids must contain at least one station ID.",
                }
            },
        )
    for station_id in ids:
        _get_station_or_404(station_id)

    return CompareResponse(
        generated_at=datetime.now(UTC),
        metric=metric,
        interval=interval,
        series=history_service.compare_stations(
            station_ids=ids,
            metric=metric,
            observed_from=observed_from,
            observed_to=observed_to,
            interval=interval,
            limit=limit,
        ),
    )


@router.get("/rankings", response_model=RankingsResponse)
def get_rankings(
    metric: str,
    direction: Literal["highest", "lowest"] = "highest",
    station_type: Annotated[
        Literal["synop", "hydro", "meteo"] | None,
        Query(alias="type"),
    ] = None,
    observed_from: Annotated[datetime | None, Query(alias="from")] = None,
    observed_to: Annotated[datetime | None, Query(alias="to")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> RankingsResponse:
    rankings = history_service.rankings(
        metric=metric,
        direction=direction,
        station_type=station_type,
        observed_from=observed_from,
        observed_to=observed_to,
        limit=limit,
    )
    return RankingsResponse(
        generated_at=datetime.now(UTC),
        metric=metric,
        direction=direction,
        rankings=rankings,
        empty_state=None
        if rankings
        else EmptyState(
            code="no_history",
            message="No observation history matched the requested ranking filters.",
            source_keys=list(STATION_SOURCE_KEYS),
        ),
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
    interval: Literal["raw", "10m", "1h", "1d"] = "raw",
    limit: Annotated[int, Query(ge=1, le=5000)] = 500,
) -> ObservationResponse:
    station, history_summary, source = _station_context_for_observations(station_id)
    history = history_service.query_station_history(
        station_id=station_id,
        metric=metric,
        observed_from=observed_from,
        observed_to=observed_to,
        interval=interval,
        limit=limit,
    )
    if history:
        origin_summary = history_service.series_origin_summary(
            station_id=station_id,
            metric=metric,
            observed_from=observed_from,
            observed_to=observed_to,
        )
        observations = [
            point
            for point in history
            if _history_observation_matches(
                point,
                metric=metric,
                observed_from=observed_from,
                observed_to=observed_to,
            )
        ]
        series_kind: Literal["history", "snapshot"] = "history"
        series_origin = origin_summary["series_origin"]
        origin_counts = origin_summary["origin_counts"]
    elif station is not None:
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
        series_kind = "snapshot"
        series_origin = "live_refresh"
        origin_counts = {"live_refresh": len(observations)} if observations else {}
    else:
        observations = []
        series_kind = "history"
        series_origin = "archive_import"
        origin_counts = {}

    return ObservationResponse(
        generated_at=datetime.now(UTC),
        station_id=station_id,
        source=source,
        observations=observations,
        series_kind=series_kind,
        series_origin=series_origin,
        origin_counts=origin_counts,
        interval=interval,
        empty_state=None
        if observations
        else EmptyState(
            code="no_observations",
            message="No observations matched the requested filters.",
            source_keys=[
                station.source_key
                if station is not None
                else str(history_summary.get("source_key", "synop"))
            ],
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
    province: str | None = None,
    county: str | None = None,
) -> WarningsResponse:
    cache = _source_cache()
    geometry_store = get_geometry_store()
    records = _warnings_from_cache(cache)
    warnings = [
        _warning_payload(warning, geometry_store)
        for warning in records
        if _warning_matches(
            warning,
            warning_type=warning_type,
            active_at=active_at,
            level=level,
            phenomenon=phenomenon,
            teryt=teryt,
            basin=basin,
            province=province,
            county=county,
            geometry_store=geometry_store,
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
    geometry_store = get_geometry_store()
    geometry = resolve_warning_geometries(warning, geometry_store)
    return WarningResponse(
        generated_at=datetime.now(UTC),
        warning=_warning_payload(warning, geometry_store),
        geometry_status=geometry["geometry_status"],
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
        warning
        for warning in all_warnings
        if _warning_matches(warning, active_at=now)
    ]
    geometry_store = get_geometry_store()
    polygon_matches, fallback_warnings, notes = warnings_matching_point(
        lat=lat,
        lon=lon,
        warnings=active_warnings,
        store=geometry_store,
    )
    if polygon_matches:
        # Keep polygon matches, plus any active warning whose geometry could not be
        # fully resolved — we can't rule those out for this location. Warnings with
        # fully resolved geometry that simply didn't match are correctly dropped.
        warnings = polygon_matches + [
            warning for warning in fallback_warnings if warning["geometry_status"] != "resolved"
        ]
    else:
        warnings = fallback_warnings

    cached_records = all_stations + all_warnings
    return LocationSummaryResponse(
        generated_at=now,
        cache=_cache_states(cache, STATION_SOURCE_KEYS + WARNING_SOURCE_KEYS),
        location={"lat": lat, "lon": lon},
        radius_km=radius_km,
        nearest_stations=nearest,
        warnings=warnings,
        empty_state=_collection_empty_state(
            cached_records,
            nearest or warnings,
            STATION_SOURCE_KEYS + WARNING_SOURCE_KEYS,
            filter_code="no_location_data",
            filter_message="No cached station or warning data matched this location summary.",
        ),
        notes=notes,
    )


@router.get("/export/station/{station_id}/observations.csv")
def export_station_observations_csv(
    station_id: str,
    metric: str | None = None,
    observed_from: Annotated[datetime | None, Query(alias="from")] = None,
    observed_to: Annotated[datetime | None, Query(alias="to")] = None,
    interval: Literal["raw", "10m", "1h", "1d"] = "raw",
    limit: Annotated[int, Query(ge=1, le=5000)] = 500,
) -> PlainTextResponse:
    response = get_station_observations(
        station_id=station_id,
        metric=metric,
        observed_from=observed_from,
        observed_to=observed_to,
        interval=interval,
        limit=limit,
    )
    station, history_summary, source = _station_context_for_observations(station_id)
    station_name = (
        station.name
        if station is not None
        else str(history_summary.get("station_name") or station_id)
    )
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
            "origin",
            "import_run_id",
            "import_source_url",
            "source_key",
            "attribution",
            "processed_notice",
            "series_kind",
            "interval",
        ],
    )
    writer.writeheader()
    for observation in response.observations:
        writer.writerow(
            {
                "station_id": station_id,
                "station_name": station_name,
                "metric": observation.get("metric"),
                "value": "" if observation.get("value") is None else observation["value"],
                "unit": "" if observation.get("unit") is None else observation["unit"],
                "observed_at": observation.get("observed_at") or "",
                "retrieved_at": observation.get("retrieved_at")
                or source.retrieved_at.isoformat(),
                "data_delay_seconds": observation.get("data_delay_seconds"),
                "missing": observation.get("missing"),
                "raw_field": observation.get("raw_field"),
                "origin": observation.get("origin", response.series_origin),
                "import_run_id": observation.get("import_run_id") or "",
                "import_source_url": observation.get("import_source_url") or "",
                "source_key": source.source_key,
                "attribution": source.attribution,
                "processed_notice": source.processed_notice,
                "series_kind": response.series_kind,
                "interval": response.interval,
            }
        )
    return PlainTextResponse(
        buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{station_id}-observations.csv"'
        },
    )


@router.get("/export/station/{station_id}/observations.json")
def export_station_observations_json(
    station_id: str,
    metric: str | None = None,
    observed_from: Annotated[datetime | None, Query(alias="from")] = None,
    observed_to: Annotated[datetime | None, Query(alias="to")] = None,
    interval: Literal["raw", "10m", "1h", "1d"] = "raw",
    limit: Annotated[int, Query(ge=1, le=5000)] = 500,
) -> JSONResponse:
    response = get_station_observations(
        station_id=station_id,
        metric=metric,
        observed_from=observed_from,
        observed_to=observed_to,
        interval=interval,
        limit=limit,
    )
    station, history_summary, source = _station_context_for_observations(station_id)
    return JSONResponse(
        content=jsonable_encoder(
            {
                "generated_at": datetime.now(UTC),
                "attribution": source.attribution,
                "processed_notice": source.processed_notice,
                "station_id": station_id,
                "station_name": station.name
                if station is not None
                else history_summary.get("station_name"),
                "series_kind": response.series_kind,
                "series_origin": response.series_origin,
                "origin_counts": response.origin_counts,
                "interval": response.interval,
                "observations": response.observations,
            }
        ),
        headers={
            "Content-Disposition": f'attachment; filename="{station_id}-observations.json"'
        },
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
        "geometry_attributions": _geometry_attributions_for_features(features),
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


@router.get("/export/warnings.geojson")
def export_warnings_geojson(
    warning_type: Annotated[
        Literal["meteo", "hydro"] | None,
        Query(alias="type"),
    ] = None,
    active_at: datetime | None = None,
    level: int | None = None,
    phenomenon: str | None = None,
    teryt: str | None = None,
    basin: str | None = None,
    province: str | None = None,
    county: str | None = None,
    bbox: Annotated[str | None, Query(description="minLon,minLat,maxLon,maxLat")] = None,
) -> JSONResponse:
    cache = _source_cache()
    geometry_store = get_geometry_store()
    bbox_values = _parse_bbox(bbox)
    cached_warnings = _warnings_from_cache(cache)
    warnings = [
        warning
        for warning in cached_warnings
        if _warning_matches(
            warning,
            warning_type=warning_type,
            active_at=active_at,
            level=level,
            phenomenon=phenomenon,
            teryt=teryt,
            basin=basin,
            province=province,
            county=county,
            geometry_store=geometry_store,
        )
    ]
    features: list[dict[str, Any]] = []
    non_spatial_records: list[dict[str, Any]] = []
    missing_geometry: list[dict[str, Any]] = []
    for warning in warnings:
        geometry = resolve_warning_geometries(warning, geometry_store)
        warning_features = geometry["geojson"]["features"]
        if bbox_values is not None:
            warning_features = [
                feature
                for feature in warning_features
                if _feature_intersects_bbox(feature, bbox_values)
            ]
        features.extend(warning_features)
        if warning_features or geometry["unresolved_areas"] or bbox_values is None:
            non_spatial_records.append(_warning_map_record(warning, geometry))
        if geometry["unresolved_areas"]:
            missing_geometry.extend(
                _missing_warning_geometry(warning, geometry["unresolved_areas"])
            )

    geojson = {
        "type": "FeatureCollection",
        "features": features,
        "generated_at": datetime.now(UTC),
        "attribution": ATTRIBUTION,
        "geometry_attributions": _geometry_attributions_for_features(features),
        "processed_notice": PROCESSED_NOTICE,
        "cache": [
            state.model_dump(mode="json")
            for state in _cache_states(cache, WARNING_SOURCE_KEYS)
        ],
        "filters": {
            "type": warning_type,
            "active_at": active_at,
            "level": level,
            "phenomenon": phenomenon,
            "teryt": teryt,
            "basin": basin,
            "province": province,
            "county": county,
            "bbox": bbox,
        },
        "non_spatial_records": non_spatial_records,
        "missing_geometry": missing_geometry,
        "empty_state": (
            _collection_empty_state(
                cached_warnings,
                features or non_spatial_records or missing_geometry,
                WARNING_SOURCE_KEYS,
                filter_message="No warnings matched the requested export filters.",
            ).model_dump(mode="json")
            if not (features or non_spatial_records or missing_geometry)
            else None
        ),
    }
    return JSONResponse(
        content=jsonable_encoder(geojson),
        media_type="application/geo+json",
        headers={"Content-Disposition": 'attachment; filename="meteolens-warnings.geojson"'},
    )


@router.get("/export/map-state.json")
def export_map_state_json(
    layers: Annotated[str | None, Query(description="Comma-separated layer keys.")] = None,
    bbox: Annotated[str | None, Query(description="minLon,minLat,maxLon,maxLat")] = None,
    lng: float | None = None,
    lat: float | None = None,
    zoom: float | None = None,
    mode: Literal["simple", "expert"] | None = None,
    theme: Literal["system", "light", "dark"] | None = None,
    selection_kind: Literal["station", "warning"] | None = None,
    selection_id: str | None = None,
    warning_level: int | None = None,
    phenomenon: str | None = None,
    province: str | None = None,
    county: str | None = None,
    basin: str | None = None,
    timeline_layer: str | None = None,
    timeline_frame_index: int | None = None,
) -> JSONResponse:
    map_layers = get_map_layers(layers=layers, bbox=bbox)
    active_layers = _parse_layers(layers)
    state = {
        "generated_at": datetime.now(UTC),
        "attribution": ATTRIBUTION,
        "processed_notice": PROCESSED_NOTICE,
        "version": "1",
        "view": {
            "lng": lng,
            "lat": lat,
            "zoom": zoom,
            "bbox": bbox,
        },
        "active_layers": [str(layer["key"]) for layer in active_layers],
        "mode": mode,
        "theme": theme,
        "selection": {
            "kind": selection_kind,
            "id": selection_id,
        }
        if selection_kind and selection_id
        else None,
        "filters": {
            "warning_level": warning_level,
            "phenomenon": phenomenon,
            "province": province,
            "county": county,
            "basin": basin,
        },
        "timeline": {
            "active_layer_key": timeline_layer,
            "frame_index": timeline_frame_index,
        },
        "api_requests": {
            "map_layers": (
                "/api/v1/map/layers"
                + _query_string({"layers": layers, "bbox": bbox})
            ),
            "warnings_geojson": (
                "/api/v1/export/warnings.geojson"
                + _query_string(
                    {
                        "level": warning_level,
                        "phenomenon": phenomenon,
                        "province": province,
                        "county": county,
                        "basin": basin,
                    }
                )
            ),
        },
        "layer_summaries": [
            {
                "key": layer.key,
                "feature_count": len(layer.geojson["features"]),
                "record_count": len(layer.records),
                "missing_geometry_count": len(layer.missing_geometry),
                "source_keys": layer.source_keys,
            }
            for layer in map_layers.layers
        ],
        "cache": [state.model_dump(mode="json") for state in map_layers.cache],
        "empty_state": map_layers.empty_state.model_dump(mode="json")
        if map_layers.empty_state
        else None,
    }
    return JSONResponse(
        content=jsonable_encoder(state),
        headers={"Content-Disposition": 'attachment; filename="meteolens-map-state.json"'},
    )


def _source_cache() -> SourceCache:
    return SourceCache(get_settings().cache_dir)


def _query_string(params: dict[str, Any]) -> str:
    clean_params = {
        key: value
        for key, value in params.items()
        if value is not None and value != ""
    }
    return "?" + urlencode(clean_params) if clean_params else ""


def _geometry_attributions_for_features(features: list[dict[str, Any]]) -> list[str]:
    store = get_geometry_store()
    attributions: list[str] = []
    for feature in features:
        properties = feature.get("properties")
        if not isinstance(properties, dict):
            continue
        dataset_key = properties.get("dataset_key")
        if isinstance(dataset_key, str):
            dataset = store.get_dataset(dataset_key)
            if dataset is not None and dataset.attribution:
                attributions.append(dataset.attribution)
        coordinate_source = properties.get("coordinate_source")
        if isinstance(coordinate_source, str) and coordinate_source:
            attributions.append(coordinate_source)
    return list(dict.fromkeys(attributions))


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
    _apply_reviewed_station_coordinates(
        [record for record in records if isinstance(record, Station)]
    )
    return records


def _stations_from_cache(cache: SourceCache) -> list[Station]:
    return [
        record
        for record in _records_from_cache(cache, STATION_SOURCE_KEYS)
        if isinstance(record, Station)
    ]


def _apply_reviewed_station_coordinates(stations: list[Station]) -> None:
    """Fill synop station coordinates from the reviewed synop_stations dataset.

    IMGW's synop API publishes no coordinates, so synop stations only become
    map markers when a reviewed coordinate dataset is cached. Stations without
    a reviewed match keep lat/lon missing.
    """
    store = get_geometry_store()
    dataset = store.get_dataset("synop_stations")
    if dataset is None or not dataset.loaded:
        return
    for station in stations:
        if station.station_type != "synop" or station.lat is not None:
            continue
        feature = store.find_by_code(dataset_key="synop_stations", code=station.source_id)
        if (
            feature is None
            or feature.geometry_type != "Point"
            or not isinstance(feature.coordinates, list)
            or len(feature.coordinates) < 2
        ):
            continue
        station.lon = float(feature.coordinates[0])
        station.lat = float(feature.coordinates[1])
        station.coordinate_source = dataset.attribution or dataset.title
        station.missing_fields = [
            name for name in station.missing_fields if name not in ("lat", "lon")
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


def _station_context_for_observations(
    station_id: str,
) -> tuple[Station | None, dict[str, Any], SourceMetadata]:
    try:
        station = _get_station_or_404(station_id)
        return station, {}, station.source
    except HTTPException as exc:
        history_summary = history_service.station_history_summary(station_id)
        if history_summary is None:
            raise exc
        source_key = str(history_summary.get("source_key") or "synop")
        return (
            None,
            history_summary,
            SourceMetadata(
                source_key=source_key,
                url=(
                    f"{str(get_settings().imgw_base_url).rstrip('/')}"
                    "/data/dane_pomiarowo_obserwacyjne/dane_meteorologiczne/dobowe/synop/"
                ),
                retrieved_at=datetime.now(UTC),
            ),
        )


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


def _feature_intersects_bbox(
    feature: dict[str, Any],
    bbox: tuple[float, float, float, float],
) -> bool:
    geometry = feature.get("geometry")
    if not isinstance(geometry, dict):
        return False
    points = list(_iter_coordinate_pairs(geometry.get("coordinates")))
    if not points:
        return False
    feature_min_lon = min(lon for lon, _lat in points)
    feature_min_lat = min(lat for _lon, lat in points)
    feature_max_lon = max(lon for lon, _lat in points)
    feature_max_lat = max(lat for _lon, lat in points)
    min_lon, min_lat, max_lon, max_lat = bbox
    return (
        feature_min_lon <= max_lon
        and feature_max_lon >= min_lon
        and feature_min_lat <= max_lat
        and feature_max_lat >= min_lat
    )


def _iter_coordinate_pairs(value: Any):
    if not isinstance(value, list | tuple):
        return
    if len(value) >= 2 and isinstance(value[0], int | float) and isinstance(
        value[1],
        int | float,
    ):
        yield float(value[0]), float(value[1])
        return
    for item in value:
        yield from _iter_coordinate_pairs(item)


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


def _warning_map_record(warning: Warning, geometry: dict[str, Any]) -> dict[str, Any]:
    return {
        **_warning_payload_from_geometry(warning, geometry),
        "area_codes": [area.code for area in warning.areas],
    }


def _warning_payload(warning: Warning, geometry_store=None) -> dict[str, Any]:
    if geometry_store is None:
        geometry_store = get_geometry_store()
    geometry = resolve_warning_geometries(warning, geometry_store)
    return _warning_payload_from_geometry(warning, geometry)


def _warning_payload_from_geometry(warning: Warning, geometry: dict[str, Any]) -> dict[str, Any]:
    payload = warning.model_dump(mode="json")
    payload["area_codes"] = [area.code for area in warning.areas]
    payload["geometry_status"] = geometry["geometry_status"]
    payload["resolved_areas"] = geometry["resolved_areas"]
    payload["unresolved_areas"] = geometry["unresolved_areas"]
    payload["raw_available"] = True
    return payload


def _missing_geometry(station: Station) -> dict[str, Any]:
    return {
        "id": station.id,
        "source_key": station.source_key,
        "reason": "missing_lat_lon",
        "missing_fields": [
            field for field in ("lat", "lon") if getattr(station, field) is None
        ],
    }


def _missing_warning_geometry(
    warning: Warning,
    unresolved_areas: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    areas = unresolved_areas or [
        {"area_type": area.area_type, "code": area.code, "reason": "missing_area_geometry_dataset"}
        for area in warning.areas
    ]
    return [
        {
            "id": warning.id,
            "source_key": warning.source_key,
            "reason": area.get("reason", "missing_area_geometry_dataset"),
            "area_type": area.get("area_type"),
            "area_codes": [area.get("code")],
        }
        for area in areas
    ]


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
        coordinate_source=station.coordinate_source,
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


def _history_observation_matches(
    observation: dict[str, Any],
    *,
    metric: str | None,
    observed_from: datetime | None,
    observed_to: datetime | None,
) -> bool:
    if metric is not None and observation.get("metric") != metric:
        return False
    observed_at_raw = observation.get("observed_at")
    observed_at = (
        datetime.fromisoformat(str(observed_at_raw).replace("Z", "+00:00"))
        if observed_at_raw
        else None
    )
    if observed_from is not None:
        comparison = _compare_datetimes(observed_at, observed_from)
        if comparison is None or comparison < 0:
            return False
    if observed_to is not None:
        comparison = _compare_datetimes(observed_at, observed_to)
        if comparison is None or comparison > 0:
            return False
    return True


def _warning_matches(
    warning: Warning,
    *,
    warning_type: Literal["meteo", "hydro"] | None = None,
    active_at: datetime | None = None,
    level: int | None = None,
    phenomenon: str | None = None,
    teryt: str | None = None,
    basin: str | None = None,
    province: str | None = None,
    county: str | None = None,
    geometry_store=None,
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
    if province is not None or county is not None:
        if geometry_store is None:
            geometry_store = get_geometry_store()
        return warning_matches_spatial_filters(
            warning,
            geometry_store,
            province=province,
            county=county,
            basin=None,
        )
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
