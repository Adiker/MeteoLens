import type { StationFeature } from "../api/client";

export function filterStationFeaturesByDelay(
  features: StationFeature[],
  maxDataDelayMinutes: number | null,
): StationFeature[] {
  if (maxDataDelayMinutes === null) {
    return features;
  }
  const maxDelaySeconds = maxDataDelayMinutes * 60;
  return features.filter((feature) => {
    const delaySeconds = feature.properties.data_delay_seconds;
    return delaySeconds === null || delaySeconds === undefined || delaySeconds <= maxDelaySeconds;
  });
}

/** Keep only stations whose source cache is not fresh, so experts can spot stale data. */
export function filterStationFeaturesByStaleCache(
  features: StationFeature[],
  onlyStaleCache: boolean,
  staleSourceKeys: string[],
): StationFeature[] {
  if (!onlyStaleCache) {
    return features;
  }
  const stale = new Set(staleSourceKeys);
  return features.filter((feature) => stale.has(feature.properties.source_key));
}
