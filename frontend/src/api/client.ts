import type { LayerKey, StationType, WarningType } from "../lib/layers";
import type { Filters, MapView, Selection, ThemePreference, ViewMode } from "../store/appStore";

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL !== undefined
    ? import.meta.env.VITE_API_BASE_URL
    : import.meta.env.DEV
      ? "http://localhost:8000"
      : "";

// ---------------------------------------------------------------------------
// Shared metadata
// ---------------------------------------------------------------------------

export interface SourceMetadata {
  provider: string;
  source_key: string;
  url: string;
  retrieved_at: string;
  attribution: string;
  processed_notice: string;
}

export interface CacheStatus {
  status: string;
  last_success_at?: string | null;
  age_seconds?: number | null;
  record_count?: number | null;
  parser_warnings: string[];
  error?: string | null;
}

export interface CacheSourceState {
  source_key: string;
  status: CacheStatus;
}

export interface EmptyState {
  code: string;
  message: string;
  source_keys: string[];
}

interface ApiEnvelope {
  generated_at: string;
  cache: CacheSourceState[];
  empty_state: EmptyState | null;
}

// ---------------------------------------------------------------------------
// Health & sources
// ---------------------------------------------------------------------------

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  environment: string;
  checked_at: string;
}

export interface SourceDescriptor {
  key: string;
  title: string;
  url: string;
  parser_status: string;
  cache_status: string;
  cache: CacheStatus;
  notes?: string | null;
}

export interface SourcesResponse {
  retrieved_at: string;
  sources: SourceDescriptor[];
}

// ---------------------------------------------------------------------------
// Stations
// ---------------------------------------------------------------------------

export interface Observation {
  metric: string;
  value: number | null;
  unit: string | null;
  observed_at: string | null;
  raw_field: string;
  missing: boolean;
  data_delay_seconds?: number | null;
  origin?: "live_refresh" | "archive_import" | "mixed";
  import_run_id?: string | null;
  import_source_url?: string | null;
}

export interface StationListItem {
  id: string;
  source_id: string;
  source_key: string;
  station_type: StationType;
  name: string;
  lat: number | null;
  lon: number | null;
  coordinate_source?: string | null;
  region?: string | null;
  watercourse?: string | null;
  latest_observed_at: string | null;
  data_delay_seconds: number | null;
  missing_fields: string[];
  source: SourceMetadata;
  raw_available: boolean;
}

export interface StationsResponse extends ApiEnvelope {
  stations: StationListItem[];
}

export interface StationDetail {
  kind: "station";
  id: string;
  source_id: string;
  source_key: string;
  station_type: StationType;
  name: string;
  lat: number | null;
  lon: number | null;
  coordinate_source?: string | null;
  region?: string | null;
  watercourse?: string | null;
  observations: Observation[];
  missing_fields: string[];
  source: SourceMetadata;
  raw: Record<string, unknown>;
}

export interface StationResponse {
  generated_at: string;
  station: StationDetail;
  latest_observed_at: string | null;
  data_delay_seconds: number | null;
  raw_available: boolean;
}

export interface ObservationResponse {
  generated_at: string;
  station_id: string;
  source: SourceMetadata;
  observations: Observation[];
  series_kind: "history" | "snapshot";
  series_origin: "live_refresh" | "archive_import" | "mixed";
  origin_counts: Record<string, number>;
  interval: string;
  empty_state: EmptyState | null;
}

// ---------------------------------------------------------------------------
// Warnings
// ---------------------------------------------------------------------------

export interface WarningArea {
  area_type: "teryt" | "basin" | "province";
  code: string;
  label?: string | null;
  region?: string | null;
}

export interface WarningRecord {
  kind: "warning";
  id: string;
  source_id: string;
  source_key: string;
  warning_type: WarningType;
  event: string;
  level: number | null;
  probability: number | null;
  valid_from: string | null;
  valid_to: string | null;
  published_at: string | null;
  office: string | null;
  content: string | null;
  comment: string | null;
  areas: WarningArea[];
  area_codes: string[];
  geometry_status?: string;
  resolved_areas?: Array<Record<string, unknown>>;
  unresolved_areas?: Array<Record<string, unknown>>;
  match_type?: string;
  matched_area?: Record<string, unknown>;
  missing_fields: string[];
  source: SourceMetadata;
  raw: Record<string, unknown>;
  raw_available: boolean;
}

export interface WarningsResponse extends ApiEnvelope {
  warnings: WarningRecord[];
}

export interface WarningResponse {
  generated_at: string;
  warning: WarningRecord;
  geometry_status: string;
  raw_available: boolean;
}

// ---------------------------------------------------------------------------
// Map layers & location
// ---------------------------------------------------------------------------

export interface StationFeature {
  type: "Feature";
  id: string;
  geometry: { type: "Point"; coordinates: [number, number] };
  properties: StationListItem & { observations: Observation[] };
}

export interface MapLayer {
  key: LayerKey;
  title: string;
  source_keys: string[];
  sources: SourceMetadata[];
  geojson: { type: "FeatureCollection"; features: StationFeature[] };
  records: Array<Record<string, unknown>>;
  missing_geometry: Array<Record<string, unknown>>;
}

export interface MapLayersResponse extends ApiEnvelope {
  layers: MapLayer[];
}

export interface GeometryDatasetStatus {
  key: string;
  title: string;
  source: string;
  license_note: string;
  provider?: string | null;
  canonical_url?: string | null;
  license_url?: string | null;
  attribution?: string | null;
  public_use?: boolean | null;
  commercial_use?: boolean | null;
  redistribution_note?: string | null;
  update_cadence?: string | null;
  known_limitations?: string | null;
  dataset_version?: string | null;
  review_status?: string | null;
  reviewed_at?: string | null;
  loaded: boolean;
  feature_count: number;
  error?: string | null;
}

export interface GeometryDatasetsResponse {
  generated_at: string;
  datasets: GeometryDatasetStatus[];
  manifest_present: boolean;
}

export interface LocationSummaryResponse extends ApiEnvelope {
  location: { lat: number; lon: number };
  radius_km: number;
  nearest_stations: Array<StationListItem & { distance_km: number }>;
  warnings: WarningRecord[];
  notes: string[];
}

// ---------------------------------------------------------------------------
// Products & timeline
// ---------------------------------------------------------------------------

export interface ProductRecord {
  id: string;
  description: string;
  manifest_url: string;
  category: string;
  availability: string;
  rendering_status: string;
  high_value: boolean;
  format_notes: string;
  research_date: string;
  notes?: string | null;
  missing_fields: string[];
  source: SourceMetadata;
}

export interface ProductsResponse {
  generated_at: string;
  retrieved_at: string | null;
  research_date: string;
  attribution: string;
  processed_notice: string;
  products: ProductRecord[];
  empty_state: EmptyState | null;
}

export interface ProductFrame {
  index: number;
  file: string;
  url: string;
  frame_time: string | null;
  run_time?: string | null;
  frame_kind: string;
  rendering_status: string;
  missing: boolean;
  renderable?: boolean;
  renderable_reason?: string | null;
  render_url?: string;
  render_ready?: boolean;
}

export interface RenderableVariable {
  key: string;
  title: string;
  unit: string;
  legend: Array<{ value: number; color: string }>;
}

export interface RenderableDescriptor {
  variables: RenderableVariable[];
  default_variable: string;
  bounds: [number, number, number, number];
  /** MapLibre image-source corners: TL, TR, BR, BL as [lon, lat]. */
  image_coordinates: [[number, number], [number, number], [number, number], [number, number]];
  render_url_template: string;
  max_lead_hours: number;
  lead_step_hours: number;
  grid_note: string;
  attribution: string;
  processed_notice: string;
}

export interface ProductFramesResponse {
  generated_at: string;
  product_id: string;
  description: string;
  category: string;
  availability: string;
  rendering_status: string;
  format_notes: string;
  research_date: string;
  source: SourceMetadata;
  retrieved_at: string | null;
  frames: ProductFrame[];
  frame_count: number;
  limit: number;
  offset: number;
  missing_frames: number;
  stale: boolean;
  renderable: RenderableDescriptor | null;
  attribution: string;
  processed_notice: string;
  empty_state: EmptyState | null;
  error?: string | null;
}

export interface TimelineLayer {
  key: string;
  product_id: string;
  title: string;
  kind: string;
  category: string;
  rendering_status: string;
  frame_count: number;
  missing_frames: number;
  frames_renderable: boolean;
  renderable: RenderableDescriptor | null;
  source_time: string | null;
  first_frame_time: string | null;
  last_frame_time: string | null;
  stale: boolean;
  attribution: string;
  processed_notice: string;
  notes: string[];
}

export interface MapTimelineResponse {
  generated_at: string;
  layers: TimelineLayer[];
  empty_state: EmptyState | null;
}

// ---------------------------------------------------------------------------
// Fetch helpers
// ---------------------------------------------------------------------------

interface ApiErrorPayload {
  code?: string;
  message?: string;
  [key: string]: unknown;
}

export interface ApiErrorBody {
  // FastAPI raises HTTPException(detail={"error": ...}) -> nested under `detail`.
  detail?: { error?: ApiErrorPayload };
  error?: ApiErrorPayload;
}

export class ApiError extends Error {
  status: number;
  code?: string;

  constructor(status: number, message: string, code?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    let code: string | undefined;
    let message = `Żądanie API nie powiodło się (${response.status}).`;
    try {
      const body = (await response.json()) as ApiErrorBody;
      const payload = body.detail?.error ?? body.error;
      code = payload?.code;
      if (payload?.message) {
        message = payload.message;
      }
    } catch {
      // keep default message
    }
    throw new ApiError(response.status, message, code);
  }
  return (await response.json()) as T;
}

function query(params: Record<string, string | number | undefined | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

export function fetchHealth() {
  return getJson<HealthResponse>("/health");
}

export function fetchSources() {
  return getJson<SourcesResponse>("/api/v1/sources");
}

export function fetchMapLayers(layers: LayerKey[]) {
  return getJson<MapLayersResponse>(`/api/v1/map/layers${query({ layers: layers.join(",") })}`);
}

export function fetchGeometryDatasets() {
  return getJson<GeometryDatasetsResponse>("/api/v1/geometry/datasets");
}

export function fetchStations(params: { type?: StationType; q?: string; limit?: number } = {}) {
  return getJson<StationsResponse>(`/api/v1/stations${query(params)}`);
}

export function fetchStation(id: string) {
  return getJson<StationResponse>(`/api/v1/stations/${encodeURIComponent(id)}`);
}

export function fetchObservations(
  id: string,
  params: {
    metric?: string;
    from?: string;
    to?: string;
    interval?: "raw" | "10m" | "1h" | "1d";
    limit?: number;
  } = {},
) {
  return getJson<ObservationResponse>(
    `/api/v1/stations/${encodeURIComponent(id)}/observations${query(params)}`,
  );
}

export interface RankingsResponse {
  generated_at: string;
  metric: string;
  direction: "highest" | "lowest";
  rankings: Array<Observation & { station_id: string; station_name: string; station_type: string }>;
  attribution: string;
  processed_notice: string;
  empty_state: EmptyState | null;
}

export function fetchRankings(params: {
  metric: string;
  direction?: "highest" | "lowest";
  type?: StationType;
  limit?: number;
}) {
  return getJson<RankingsResponse>(`/api/v1/rankings${query(params)}`);
}

export function fetchWarnings(
  params: {
    type?: WarningType;
    level?: number;
    phenomenon?: string;
    province?: string;
    county?: string;
    basin?: string;
    active_at?: string;
  } = {},
) {
  return getJson<WarningsResponse>(`/api/v1/warnings${query(params)}`);
}

export function fetchWarning(id: string) {
  return getJson<WarningResponse>(`/api/v1/warnings/${encodeURIComponent(id)}`);
}

export function fetchLocationSummary(params: { lat: number; lon: number; radius_km?: number }) {
  return getJson<LocationSummaryResponse>(`/api/v1/location/summary${query(params)}`);
}

export function fetchProducts() {
  return getJson<ProductsResponse>("/api/v1/products");
}

export function fetchProductFrames(
  productId: string,
  params: { limit?: number; offset?: number } = {},
) {
  return getJson<ProductFramesResponse>(
    `/api/v1/products/${encodeURIComponent(productId)}/frames${query(params)}`,
  );
}

export function fetchMapTimeline() {
  return getJson<MapTimelineResponse>("/api/v1/map/timeline");
}

/** Absolute URL of a rendered product frame PNG (MapLibre image source). */
export function productRenderUrl(renderUrl: string): string {
  return `${API_BASE_URL}${renderUrl}`;
}

export interface SourceFreshnessItem {
  source_key: string;
  title: string;
  cache_status: string;
  last_success_at: string | null;
  age_seconds: number | null;
  record_count: number | null;
  parser_warnings: string[];
  error: string | null;
  ttl_seconds: number;
  stale: boolean;
  parser_status: string;
  notes?: string | null;
}

export interface FreshnessResponse {
  generated_at: string;
  overall_status: string;
  sources: SourceFreshnessItem[];
  notes: string[];
  attribution: string;
  processed_notice: string;
  alerting_disclaimer: string;
}

export interface WarningStationComparisonResponse {
  generated_at: string;
  station_id: string;
  station: Record<string, unknown>;
  observations: Observation[];
  warnings: WarningRecord[];
  notes: string[];
  alerting_disclaimer: string;
  attribution: string;
  processed_notice: string;
  empty_state: EmptyState | null;
}

export function fetchFreshnessStatus() {
  return getJson<FreshnessResponse>("/api/v1/status/freshness");
}

export function fetchWarningStationComparison(stationId: string) {
  return getJson<WarningStationComparisonResponse>(
    `/api/v1/compare/warning-station/${encodeURIComponent(stationId)}`,
  );
}

// Export URLs are direct download links (anchor href), not fetched JSON.
export function stationCsvUrl(id: string): string {
  return `${API_BASE_URL}/api/v1/export/station/${encodeURIComponent(id)}.csv`;
}

export function stationJsonUrl(id: string): string {
  return `${API_BASE_URL}/api/v1/export/station/${encodeURIComponent(id)}.json`;
}

export function mapGeoJsonUrl(layers: LayerKey[]): string {
  return `${API_BASE_URL}/api/v1/export/map.geojson${query({ layers: layers.join(",") })}`;
}

export function warningsGeoJsonUrl(params: {
  type?: WarningType;
  active_at?: string;
  level?: number | null;
  phenomenon?: string;
  province?: string;
  county?: string;
  basin?: string;
}): string {
  return `${API_BASE_URL}/api/v1/export/warnings.geojson${query(params)}`;
}

export function mapStateJsonUrl(params: {
  layers: LayerKey[];
  mapView: MapView;
  mode: ViewMode;
  theme: ThemePreference;
  selection: Selection | null;
  filters: Filters;
  timelineLayer?: string | null;
  timelineFrameIndex?: number | null;
}): string {
  return `${API_BASE_URL}/api/v1/export/map-state.json${query({
    layers: params.layers.join(","),
    lng: params.mapView.lng,
    lat: params.mapView.lat,
    zoom: params.mapView.zoom,
    mode: params.mode,
    theme: params.theme,
    selection_kind: params.selection?.kind,
    selection_id: params.selection?.id,
    warning_level: params.filters.warningLevel,
    phenomenon: params.filters.phenomenon,
    province: params.filters.province,
    county: params.filters.county,
    basin: params.filters.basin,
    timeline_layer: params.timelineLayer,
    timeline_frame_index: params.timelineFrameIndex,
  })}`;
}
