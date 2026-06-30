import { useQuery } from "@tanstack/react-query";

import { fetchHealth, fetchSources } from "./client";

export function useHealthQuery() {
  return useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    retry: 1
  });
}

export function useSourcesQuery() {
  return useQuery({
    queryKey: ["sources"],
    queryFn: fetchSources,
    retry: 1
  });
}

