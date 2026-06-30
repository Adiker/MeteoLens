/**
 * Lightweight window-event bus for imperative map commands, so components can
 * ask the map to move without prop-drilling a MapLibre instance through the tree.
 */
export const FLY_TO_EVENT = "meteolens:flyto";
export const CAPTURE_PNG_EVENT = "meteolens:capture-png";

export interface FlyToDetail {
  lng: number;
  lat: number;
  zoom?: number;
}

export function flyTo(detail: FlyToDetail): void {
  window.dispatchEvent(new CustomEvent<FlyToDetail>(FLY_TO_EVENT, { detail }));
}

export function captureMapPng(): void {
  window.dispatchEvent(new CustomEvent(CAPTURE_PNG_EVENT));
}
