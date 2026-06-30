import { create } from "zustand";

import { DEFAULT_ACTIVE_LAYERS, type LayerKey } from "../lib/layers";

export type ThemePreference = "system" | "light" | "dark";
export type ViewMode = "simple" | "expert";

export interface Selection {
  kind: "station" | "warning";
  id: string;
}

export interface MapView {
  lng: number;
  lat: number;
  zoom: number;
}

export interface Filters {
  /** Warning level filter (1-3) or null for all. */
  warningLevel: number | null;
  /** Free-text phenomenon/event filter. */
  phenomenon: string;
}

export const POLAND_VIEW: MapView = { lng: 19.1451, lat: 51.9194, zoom: 5.4 };

export interface AppState {
  activeLayers: Record<LayerKey, boolean>;
  selection: Selection | null;
  mode: ViewMode;
  theme: ThemePreference;
  filters: Filters;
  mapView: MapView;
  userLocation: { lat: number; lon: number } | null;
  controlPanelOpen: boolean;
  shortcutHelpOpen: boolean;

  toggleLayer: (key: LayerKey) => void;
  setLayerActive: (key: LayerKey, active: boolean) => void;
  setActiveLayers: (keys: LayerKey[]) => void;
  select: (selection: Selection | null) => void;
  clearSelection: () => void;
  setMode: (mode: ViewMode) => void;
  toggleMode: () => void;
  setTheme: (theme: ThemePreference) => void;
  cycleTheme: () => void;
  setFilter: <K extends keyof Filters>(key: K, value: Filters[K]) => void;
  resetFilters: () => void;
  setMapView: (view: MapView) => void;
  setUserLocation: (location: { lat: number; lon: number } | null) => void;
  setControlPanelOpen: (open: boolean) => void;
  toggleControlPanel: () => void;
  setShortcutHelpOpen: (open: boolean) => void;
}

function buildActiveLayers(keys: LayerKey[]): Record<LayerKey, boolean> {
  const active = {} as Record<LayerKey, boolean>;
  for (const key of DEFAULT_ACTIVE_LAYERS) {
    active[key] = keys.includes(key);
  }
  return active;
}

const DEFAULT_FILTERS: Filters = { warningLevel: null, phenomenon: "" };

const THEME_CYCLE: ThemePreference[] = ["system", "light", "dark"];

export const useAppStore = create<AppState>((set) => ({
  activeLayers: buildActiveLayers(DEFAULT_ACTIVE_LAYERS),
  selection: null,
  mode: "simple",
  theme: "system",
  filters: DEFAULT_FILTERS,
  mapView: POLAND_VIEW,
  userLocation: null,
  controlPanelOpen: true,
  shortcutHelpOpen: false,

  toggleLayer: (key) =>
    set((state) => ({ activeLayers: { ...state.activeLayers, [key]: !state.activeLayers[key] } })),
  setLayerActive: (key, active) =>
    set((state) => ({ activeLayers: { ...state.activeLayers, [key]: active } })),
  setActiveLayers: (keys) => set({ activeLayers: buildActiveLayers(keys) }),
  select: (selection) => set({ selection }),
  clearSelection: () => set({ selection: null }),
  setMode: (mode) => set({ mode }),
  toggleMode: () => set((state) => ({ mode: state.mode === "simple" ? "expert" : "simple" })),
  setTheme: (theme) => set({ theme }),
  cycleTheme: () =>
    set((state) => ({
      theme: THEME_CYCLE[(THEME_CYCLE.indexOf(state.theme) + 1) % THEME_CYCLE.length],
    })),
  setFilter: (key, value) => set((state) => ({ filters: { ...state.filters, [key]: value } })),
  resetFilters: () => set({ filters: DEFAULT_FILTERS }),
  setMapView: (view) => set({ mapView: view }),
  setUserLocation: (location) => set({ userLocation: location }),
  setControlPanelOpen: (open) => set({ controlPanelOpen: open }),
  toggleControlPanel: () => set((state) => ({ controlPanelOpen: !state.controlPanelOpen })),
  setShortcutHelpOpen: (open) => set({ shortcutHelpOpen: open }),
}));

export function activeLayerKeys(active: Record<LayerKey, boolean>): LayerKey[] {
  return DEFAULT_ACTIVE_LAYERS.filter((key) => active[key]);
}
