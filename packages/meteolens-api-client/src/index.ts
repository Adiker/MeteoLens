import { OPENAPI_METADATA, type ApiOperationId, type ApiSchemaName } from "./generated";

export { OPENAPI_METADATA, type ApiOperationId, type ApiSchemaName };

export type StationType = "synop" | "hydro" | "meteo";
export type WarningType = "meteo" | "hydro";
export type Interval = "raw" | "10m" | "1h" | "1d";

export interface MeteoLensClientOptions {
  baseUrl?: string;
  fetch?: typeof fetch;
}

export interface SourceMetadata {
  provider: string;
  source_key: string;
  url: string;
  retrieved_at: string;
  attribution: string;
  processed_notice: string;
}

export interface EmptyState {
  code: string;
  message: string;
  source_keys: string[];
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

export interface ApiEnvelope {
  generated_at: string;
  cache: CacheSourceState[];
  empty_state: EmptyState | null;
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
  latest_observed_at: string | null;
  data_delay_seconds: number | null;
  missing_fields: string[];
  source: SourceMetadata;
  raw_available: boolean;
}

export interface StationsResponse extends ApiEnvelope {
  stations: StationListItem[];
}

export interface Observation {
  metric: string;
  value: number | null;
  unit: string | null;
  observed_at: string | null;
  retrieved_at?: string | null;
  data_delay_seconds?: number | null;
  raw_field: string;
  missing: boolean;
  origin?: "live_refresh" | "archive_import" | "mixed";
  import_run_id?: string | null;
  import_source_url?: string | null;
}

export interface ObservationResponse {
  generated_at: string;
  station_id: string;
  source: SourceMetadata;
  observations: Observation[];
  series_kind: "history" | "snapshot";
  series_origin: "live_refresh" | "archive_import" | "mixed";
  origin_counts: Record<string, number>;
  interval: Interval;
  empty_state: EmptyState | null;
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

export interface WarningRecord {
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
  area_codes: string[];
  geometry_status?: string;
  source: SourceMetadata;
}

export interface LocationSummaryResponse extends ApiEnvelope {
  location: { lat: number; lon: number };
  radius_km: number;
  nearest_stations: Array<StationListItem & { distance_km: number }>;
  warnings: WarningRecord[];
  notes: string[];
}

export interface ApiErrorPayload {
  code?: string;
  message?: string;
  [key: string]: unknown;
}

export class MeteoLensApiError extends Error {
  status: number;
  code?: string;

  constructor(status: number, message: string, code?: string) {
    super(message);
    this.name = "MeteoLensApiError";
    this.status = status;
    this.code = code;
  }
}

export class MeteoLensClient {
  readonly baseUrl: string;
  private readonly fetchImpl: typeof fetch;

  constructor(options: MeteoLensClientOptions = {}) {
    this.baseUrl = (options.baseUrl ?? "").replace(/\/$/, "");
    this.fetchImpl = options.fetch ?? fetch;
  }

  listStations(params: { type?: StationType; q?: string; limit?: number } = {}) {
    return this.getJson<StationsResponse>(`/api/v1/stations${query(params)}`);
  }

  getStationObservations(
    stationId: string,
    params: {
      metric?: string;
      from?: string;
      to?: string;
      interval?: Interval;
      limit?: number;
    } = {},
  ) {
    return this.getJson<ObservationResponse>(
      `/api/v1/stations/${encodeURIComponent(stationId)}/observations${query(params)}`,
    );
  }

  getFreshnessStatus() {
    return this.getJson<FreshnessResponse>("/api/v1/status/freshness");
  }

  getActiveWarningsForLocation(params: { lat: number; lon: number; radius_km?: number }) {
    return this.getJson<LocationSummaryResponse>(
      `/api/v1/location/summary${query(params)}`,
    );
  }

  stationObservationsCsvUrl(
    stationId: string,
    params: { metric?: string; from?: string; to?: string; interval?: Interval; limit?: number } = {},
  ) {
    return this.url(
      `/api/v1/export/station/${encodeURIComponent(stationId)}/observations.csv${query(params)}`,
    );
  }

  stationObservationsJsonUrl(
    stationId: string,
    params: { metric?: string; from?: string; to?: string; interval?: Interval; limit?: number } = {},
  ) {
    return this.url(
      `/api/v1/export/station/${encodeURIComponent(stationId)}/observations.json${query(params)}`,
    );
  }

  warningGeoJsonUrl(params: {
    type?: WarningType;
    active_at?: string;
    level?: number;
    phenomenon?: string;
    teryt?: string;
    basin?: string;
    province?: string;
    county?: string;
    bbox?: string;
  } = {}) {
    return this.url(`/api/v1/export/warnings.geojson${query(params)}`);
  }

  private url(path: string) {
    return `${this.baseUrl}${path}`;
  }

  private async getJson<T>(path: string): Promise<T> {
    const response = await this.fetchImpl(this.url(path));
    if (!response.ok) {
      throw await toApiError(response);
    }
    return (await response.json()) as T;
  }
}

export function createMeteoLensClient(options: MeteoLensClientOptions = {}) {
  return new MeteoLensClient(options);
}

function query(params: Record<string, string | number | undefined | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  }
  const value = search.toString();
  return value ? `?${value}` : "";
}

async function toApiError(response: Response): Promise<MeteoLensApiError> {
  let code: string | undefined;
  let message = `MeteoLens API request failed (${response.status}).`;
  try {
    const body = (await response.json()) as {
      detail?: { error?: ApiErrorPayload };
      error?: ApiErrorPayload;
    };
    const payload = body.detail?.error ?? body.error;
    code = payload?.code;
    message = payload?.message ?? message;
  } catch {
    // The API usually returns JSON errors, but keep a useful fallback.
  }
  return new MeteoLensApiError(response.status, message, code);
}
