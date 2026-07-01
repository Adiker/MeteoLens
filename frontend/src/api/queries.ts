import { useQuery } from "@tanstack/react-query";

import type { LayerKey, StationType, WarningType } from "../lib/layers";
import {
  fetchHealth,
  fetchLocationSummary,
  fetchMapLayers,
  fetchMapTimeline,
  fetchObservations,
  fetchProductFrames,
  fetchSources,
  fetchStation,
  fetchStations,
  fetchWarning,
  fetchWarnings,
} from "./client";

const STALE_TIME = 60_000;

export function useHealthQuery() {
  return useQuery({ queryKey: ["health"], queryFn: fetchHealth, retry: 1 });
}

export function useSourcesQuery() {
  return useQuery({
    queryKey: ["sources"],
    queryFn: fetchSources,
    retry: 1,
    staleTime: STALE_TIME,
  });
}

export function useMapLayersQuery(layers: LayerKey[]) {
  return useQuery({
    queryKey: ["map-layers", layers],
    queryFn: () => fetchMapLayers(layers),
    enabled: layers.length > 0,
    staleTime: STALE_TIME,
  });
}

export function useStationSearchQuery(q: string, type?: StationType) {
  const term = q.trim();
  return useQuery({
    queryKey: ["station-search", term, type ?? null],
    queryFn: () => fetchStations({ q: term, type, limit: 8 }),
    enabled: term.length >= 2,
    staleTime: STALE_TIME,
  });
}

export function useStationQuery(id: string | null) {
  return useQuery({
    queryKey: ["station", id],
    queryFn: () => fetchStation(id as string),
    enabled: Boolean(id),
  });
}

export function useObservationsQuery(id: string | null) {
  return useQuery({
    queryKey: ["observations", id],
    queryFn: () => fetchObservations(id as string),
    enabled: Boolean(id),
  });
}

export function useWarningsQuery(
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
  return useQuery({
    queryKey: ["warnings", params],
    queryFn: () => fetchWarnings(params),
    staleTime: STALE_TIME,
  });
}

/** Current time bucketed to the minute, for a stable `active_at` query key. */
export function activeAtBucket(): string {
  return new Date(Math.floor(Date.now() / 60_000) * 60_000).toISOString();
}

export function useWarningQuery(id: string | null) {
  return useQuery({
    queryKey: ["warning", id],
    queryFn: () => fetchWarning(id as string),
    enabled: Boolean(id),
  });
}

export function useLocationSummaryQuery(location: { lat: number; lon: number } | null) {
  return useQuery({
    queryKey: ["location-summary", location],
    queryFn: () => fetchLocationSummary({ lat: location!.lat, lon: location!.lon }),
    enabled: Boolean(location),
  });
}

export function useMapTimelineQuery() {
  return useQuery({
    queryKey: ["map-timeline"],
    queryFn: fetchMapTimeline,
    staleTime: STALE_TIME,
  });
}

export function useProductFramesQuery(productId: string | null, limit = 500) {
  return useQuery({
    queryKey: ["product-frames", productId, limit],
    queryFn: () => fetchProductFrames(productId as string, { limit }),
    enabled: Boolean(productId),
    staleTime: STALE_TIME,
  });
}
