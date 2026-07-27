import { useInfiniteQuery, useQuery } from "@tanstack/react-query";

import type { LayerKey, StationType, WarningType } from "../lib/layers";
import {
  fetchFreshnessStatus,
  fetchGeometryDatasets,
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
  fetchWarningEvents,
  fetchWarningHistory,
  fetchWarningStationComparison,
  fetchWarnings,
  type WarningEventParams,
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

export function useGeometryDatasetsQuery() {
  return useQuery({
    queryKey: ["geometry-datasets"],
    queryFn: fetchGeometryDatasets,
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

export function useObservationsQuery(id: string | null, metric?: string) {
  return useQuery({
    queryKey: ["observations", id, metric ?? null],
    queryFn: () => fetchObservations(id as string, { metric, limit: 5000 }),
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

export function useWarningEventsQuery(params: WarningEventParams) {
  return useInfiniteQuery({
    queryKey: ["warning-events", params],
    queryFn: ({ pageParam }) =>
      fetchWarningEvents({
        ...params,
        cursor: pageParam || undefined,
        limit: 50,
      }),
    initialPageParam: "",
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    staleTime: STALE_TIME,
  });
}

export function useWarningHistoryQuery(historyId: string | null) {
  return useQuery({
    queryKey: ["warning-history", historyId],
    queryFn: () => fetchWarningHistory(historyId as string),
    enabled: Boolean(historyId),
    staleTime: STALE_TIME,
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

export function useProductFramesQuery(productId: string | null, limit = 500, offset = 0) {
  return useQuery({
    queryKey: ["product-frames", productId, limit, offset],
    queryFn: () => fetchProductFrames(productId as string, { limit, offset }),
    enabled: Boolean(productId),
    staleTime: STALE_TIME,
  });
}

export function useFreshnessQuery() {
  return useQuery({
    queryKey: ["freshness"],
    queryFn: fetchFreshnessStatus,
    staleTime: STALE_TIME,
  });
}

export function useWarningComparisonQuery(stationId: string | null) {
  return useQuery({
    queryKey: ["warning-comparison", stationId],
    queryFn: () => fetchWarningStationComparison(stationId as string),
    enabled: Boolean(stationId),
    staleTime: STALE_TIME,
  });
}
