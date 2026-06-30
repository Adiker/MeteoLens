const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

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
  notes?: string | null;
}

export interface SourcesResponse {
  retrieved_at: string;
  sources: SourceDescriptor[];
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function fetchHealth() {
  return getJson<HealthResponse>("/health");
}

export function fetchSources() {
  return getJson<SourcesResponse>("/api/v1/sources");
}

