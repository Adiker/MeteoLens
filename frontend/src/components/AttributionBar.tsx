import { useGeometryDatasetsQuery } from "../api/queries";
import { loadedGeometryAttributions } from "../lib/geometryAttribution";

export function AttributionBar() {
  const geometryQuery = useGeometryDatasetsQuery();
  const geometryAttributions = loadedGeometryAttributions(geometryQuery.data?.datasets);

  return (
    <footer className="flex min-h-9 flex-wrap items-center justify-between gap-x-4 gap-y-1 border-t border-border bg-card px-4 py-2 text-xs text-muted-foreground">
      <span>Źródło danych: IMGW-PIB.</span>
      {geometryAttributions.map((attribution) => (
        <span key={attribution}>{attribution}</span>
      ))}
      <span>Dane IMGW-PIB zostały przetworzone przez MeteoLens.</span>
    </footer>
  );
}
