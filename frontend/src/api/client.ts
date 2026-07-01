import type { LayerKey, StationType, WarningType } from "../lib/layers";

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

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
}

export interface StationListItem {
  id: string;
  source_id: string;
  source_key: string;
  station_type: StationType;
  name: string;
  lat: number | null;
  lon: number | null;
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

export interface LocationSummaryResponse extends ApiEnvelope {
  location: { lat: number; lon: number };
  radius_km: number;
  nearest_stations: Array<StationListItem & { distance_km: number }>;
  warnings: WarningRecord[];
  notes: string[];
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

export function fetchStations(params: { type?: StationType; q?: string; limit?: number } = {}) {
  return getJson<StationsResponse>(`/api/v1/stations${query(params)}`);
}

export function fetchStation(id: string) {
  return getJson<StationResponse>(`/api/v1/stations/${encodeURIComponent(id)}`);
}

export function fetchObservations(id: string, params: { metric?: string } = {}) {
  return getJson<ObservationResponse>(
    `/api/v1/stations/${encodeURIComponent(id)}/observations${query(params)}`,
  );
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
