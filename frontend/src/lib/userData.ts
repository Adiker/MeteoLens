import type { LayerKey } from "./layers";
import { readJsonStorage, writeJsonStorage } from "./storage";
import type { Filters, MapView, ThemePreference, ViewMode } from "../store/appStore";

export const SAVED_LOCATIONS_KEY = "meteolens.savedLocations";
export const SAVED_VIEWS_KEY = "meteolens.savedViews";
export const ALERT_RULES_KEY = "meteolens.alertRules";
export const DASHBOARD_KEY = "meteolens.dashboard";

export interface SavedLocation {
  id: string;
  name: string;
  lat: number;
  lon: number;
  createdAt: string;
}

export interface SavedMapView {
  id: string;
  name: string;
  mapView: MapView;
  activeLayers: LayerKey[];
  filters: Filters;
  mode: ViewMode;
  theme: ThemePreference;
  createdAt: string;
}

export type AlertRuleType =
  | "warning_nearby"
  | "warning_level"
  | "station_threshold"
  | "stale_source";

export interface AlertRule {
  id: string;
  name: string;
  enabled: boolean;
  type: AlertRuleType;
  radiusKm?: number;
  warningLevel?: number;
  stationId?: string;
  metric?: string;
  operator?: "gt" | "lt";
  threshold?: number;
  sourceKey?: string;
}

export interface DashboardWidgets {
  showFreshness: boolean;
  showAlerts: boolean;
  showSavedViews: boolean;
  showComparison: boolean;
}

export const DEFAULT_DASHBOARD: DashboardWidgets = {
  showFreshness: true,
  showAlerts: true,
  showSavedViews: true,
  showComparison: true,
};

export const ALERTING_DISCLAIMER =
  "MeteoLens nie jest urzędowym systemem ostrzegania. Lokalne reguły służą wyłącznie informacji operacyjnej i nie zastępują komunikatów IMGW-PIB.";

export function readSavedLocations(): SavedLocation[] {
  return readJsonStorage<SavedLocation[]>(SAVED_LOCATIONS_KEY, []);
}

export function writeSavedLocations(locations: SavedLocation[]): void {
  writeJsonStorage(SAVED_LOCATIONS_KEY, locations);
}

export function readSavedViews(): SavedMapView[] {
  return readJsonStorage<SavedMapView[]>(SAVED_VIEWS_KEY, []);
}

export function writeSavedViews(views: SavedMapView[]): void {
  writeJsonStorage(SAVED_VIEWS_KEY, views);
}

export function readAlertRules(): AlertRule[] {
  return readJsonStorage<AlertRule[]>(ALERT_RULES_KEY, []);
}

export function writeAlertRules(rules: AlertRule[]): void {
  writeJsonStorage(ALERT_RULES_KEY, rules);
}

export function readDashboardWidgets(): DashboardWidgets {
  return readJsonStorage(DASHBOARD_KEY, DEFAULT_DASHBOARD);
}

export function writeDashboardWidgets(widgets: DashboardWidgets): void {
  writeJsonStorage(DASHBOARD_KEY, widgets);
}

export function createId(prefix: string): string {
  return `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
}
