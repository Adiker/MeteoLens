import "maplibre-gl/dist/maplibre-gl.css";

import maplibregl from "maplibre-gl";
import { useEffect, useRef } from "react";

const POLAND_CENTER: [number, number] = [19.1451, 51.9194];

export function MapShell() {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!mapContainerRef.current) {
      return undefined;
    }

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      center: POLAND_CENTER,
      zoom: 5.4,
      minZoom: 4,
      maxZoom: 14,
      attributionControl: false,
      style: {
        version: 8,
        sources: {
          osm: {
            type: "raster",
            tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            attribution: "© OpenStreetMap contributors"
          }
        },
        layers: [
          {
            id: "osm",
            type: "raster",
            source: "osm"
          }
        ]
      }
    });

    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "bottom-left");

    return () => {
      map.remove();
    };
  }, []);

  return (
    <div className="h-full w-full bg-muted">
      <div ref={mapContainerRef} className="h-full w-full" aria-label="Mapa MeteoLens" />
    </div>
  );
}

