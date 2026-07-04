import type { GeometryDatasetStatus } from "../api/client";

export function loadedGeometryAttributions(
  datasets: GeometryDatasetStatus[] | undefined,
): string[] {
  const attributions = (datasets ?? [])
    .filter((dataset) => dataset.loaded && dataset.attribution)
    .map((dataset) => dataset.attribution as string);
  return [...new Set(attributions)];
}
