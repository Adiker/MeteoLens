import { create } from "zustand";

import { DEFAULT_ACTIVE_LAYERS, type LayerKey } from "../lib/layers";
import { initialTheme } from "../lib/theme";
import {
  readAlertRules,
  readDashboardWidgets,
  readSavedLocations,
  readSavedViews,
  writeAlertRules,
  writeDashboardWidgets,
  writeSavedLocations,
  writeSavedViews,
  type AlertRule,
  type DashboardWidgets,
  type SavedLocation,
  type SavedMapView,
} from "../lib/userData";

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
  /** TERYT voivodeship prefix filter where geometry exists. */
  province: string;
  /** TERYT county code filter where geometry exists. */
  county: string;
  /** Hydrological basin code filter where geometry exists. */
  basin: string;
  /** Expert: hide stations with delay above this many minutes. */
  maxDataDelayMinutes: number | null;
  /** Expert: surface only layers backed by stale/error cache. */
  onlyStaleCache: boolean;
}

export type TimelineSpeed = 0.5 | 1 | 2 | 4;

export interface TimelineState {
  activeLayerKey: string | null;
  frameIndex: number;
  playing: boolean;
  speed: TimelineSpeed;
  focused: boolean;
  /** User opt-in for drawing the rendered product overlay on the map. */
  overlayEnabled: boolean;
  /** Last overlay image load failure, surfaced in the timeline bar. */
  overlayError: string | null;
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
  timeline: TimelineState;
  powerPanelOpen: boolean;
  savedLocations: SavedLocation[];
  savedViews: SavedMapView[];
  alertRules: AlertRule[];
  dashboardWidgets: DashboardWidgets;

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
  setTimelineLayer: (layerKey: string | null) => void;
  setTimelineFrameIndex: (index: number) => void;
  setTimelinePlaying: (playing: boolean) => void;
  toggleTimelinePlaying: () => void;
  setTimelineSpeed: (speed: TimelineSpeed) => void;
  stepTimelineFrame: (delta: number) => void;
  setTimelineFocused: (focused: boolean) => void;
  toggleTimelineOverlay: () => void;
  setTimelineOverlayError: (error: string | null) => void;
  setPowerPanelOpen: (open: boolean) => void;
  togglePowerPanel: () => void;
  addSavedLocation: (location: SavedLocation) => void;
  removeSavedLocation: (id: string) => void;
  addSavedView: (view: SavedMapView) => void;
  removeSavedView: (id: string) => void;
  applySavedView: (view: SavedMapView) => void;
  addAlertRule: (rule: AlertRule) => void;
  updateAlertRule: (rule: AlertRule) => void;
  removeAlertRule: (id: string) => void;
  setDashboardWidgets: (widgets: DashboardWidgets) => void;
}

function buildActiveLayers(keys: LayerKey[]): Record<LayerKey, boolean> {
  const active = {} as Record<LayerKey, boolean>;
  for (const key of DEFAULT_ACTIVE_LAYERS) {
    active[key] = keys.includes(key);
  }
  return active;
}

const DEFAULT_FILTERS: Filters = {
  warningLevel: null,
  phenomenon: "",
  province: "",
  county: "",
  basin: "",
  maxDataDelayMinutes: null,
  onlyStaleCache: false,
};

const THEME_CYCLE: ThemePreference[] = ["system", "light", "dark"];

const DEFAULT_TIMELINE: TimelineState = {
  activeLayerKey: null,
  frameIndex: 0,
  playing: false,
  speed: 1,
  focused: false,
  // Off by default: the first render of a frame downloads a large GRIB file
  // on the backend, so drawing the overlay is an explicit user choice.
  overlayEnabled: false,
  overlayError: null,
};

export const useAppStore = create<AppState>((set) => ({
  activeLayers: buildActiveLayers(DEFAULT_ACTIVE_LAYERS),
  selection: null,
  mode: "simple",
  // Hydrate from persisted preference so the theme hook never overwrites it.
  theme: initialTheme(),
  filters: DEFAULT_FILTERS,
  mapView: POLAND_VIEW,
  userLocation: null,
  controlPanelOpen: true,
  shortcutHelpOpen: false,
  timeline: DEFAULT_TIMELINE,
  powerPanelOpen: false,
  savedLocations: readSavedLocations(),
  savedViews: readSavedViews(),
  alertRules: readAlertRules(),
  dashboardWidgets: readDashboardWidgets(),

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
  setTimelineLayer: (layerKey) =>
    set((state) => ({
      timeline: {
        ...state.timeline,
        activeLayerKey: layerKey,
        frameIndex: 0,
        playing: false,
        overlayError: null,
      },
    })),
  setTimelineFrameIndex: (index) =>
    set((state) => ({ timeline: { ...state.timeline, frameIndex: Math.max(0, index) } })),
  setTimelinePlaying: (playing) =>
    set((state) => ({ timeline: { ...state.timeline, playing } })),
  toggleTimelinePlaying: () =>
    set((state) => ({ timeline: { ...state.timeline, playing: !state.timeline.playing } })),
  setTimelineSpeed: (speed) => set((state) => ({ timeline: { ...state.timeline, speed } })),
  stepTimelineFrame: (delta) =>
    set((state) => ({
      timeline: {
        ...state.timeline,
        frameIndex: Math.max(0, state.timeline.frameIndex + delta),
      },
    })),
  setTimelineFocused: (focused) =>
    set((state) => ({ timeline: { ...state.timeline, focused } })),
  toggleTimelineOverlay: () =>
    set((state) => ({
      timeline: {
        ...state.timeline,
        overlayEnabled: !state.timeline.overlayEnabled,
        overlayError: null,
      },
    })),
  setTimelineOverlayError: (error) =>
    set((state) => ({ timeline: { ...state.timeline, overlayError: error } })),
  setPowerPanelOpen: (open) => set({ powerPanelOpen: open }),
  togglePowerPanel: () => set((state) => ({ powerPanelOpen: !state.powerPanelOpen })),
  addSavedLocation: (location) =>
    set((state) => {
      const savedLocations = [...state.savedLocations, location];
      writeSavedLocations(savedLocations);
      return { savedLocations };
    }),
  removeSavedLocation: (id) =>
    set((state) => {
      const savedLocations = state.savedLocations.filter((item) => item.id !== id);
      writeSavedLocations(savedLocations);
      return { savedLocations };
    }),
  addSavedView: (view) =>
    set((state) => {
      const savedViews = [...state.savedViews, view];
      writeSavedViews(savedViews);
      return { savedViews };
    }),
  removeSavedView: (id) =>
    set((state) => {
      const savedViews = state.savedViews.filter((item) => item.id !== id);
      writeSavedViews(savedViews);
      return { savedViews };
    }),
  applySavedView: (view) =>
    set({
      mapView: view.mapView,
      activeLayers: buildActiveLayers(view.activeLayers),
      filters: view.filters,
      mode: view.mode,
      theme: view.theme,
    }),
  addAlertRule: (rule) =>
    set((state) => {
      const alertRules = [...state.alertRules, rule];
      writeAlertRules(alertRules);
      return { alertRules };
    }),
  updateAlertRule: (rule) =>
    set((state) => {
      const alertRules = state.alertRules.map((item) => (item.id === rule.id ? rule : item));
      writeAlertRules(alertRules);
      return { alertRules };
    }),
  removeAlertRule: (id) =>
    set((state) => {
      const alertRules = state.alertRules.filter((item) => item.id !== id);
      writeAlertRules(alertRules);
      return { alertRules };
    }),
  setDashboardWidgets: (widgets) => {
    writeDashboardWidgets(widgets);
    set({ dashboardWidgets: widgets });
  },
}));

export function activeLayerKeys(active: Record<LayerKey, boolean>): LayerKey[] {
  return DEFAULT_ACTIVE_LAYERS.filter((key) => active[key]);
}
