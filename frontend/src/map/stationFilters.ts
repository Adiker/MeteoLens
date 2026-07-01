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
