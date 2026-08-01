import { DEFAULT_ACTIVE_LAYERS, type LayerKey } from "./layers";
import { WARNING_CHANGE_KINDS, type WarningChangeKind } from "../api/client";
import { isDateOnly } from "./format";
import type {
  Filters,
  MapView,
  Selection,
  ThemePreference,
  ViewMode,
  WarningHistoryFilters,
  WarningPanelView,
} from "../store/appStore";

/** Compact codes keep permalinks short and stable. */
const LAYER_CODE: Record<LayerKey, string> = {
  synop_stations: "syn",
  hydro_stations: "hyd",
  meteo_stations: "met",
  warnings_meteo: "wm",
  warnings_hydro: "wh",
};
const CODE_LAYER = Object.fromEntries(
  Object.entries(LAYER_CODE).map(([key, code]) => [code, key]),
) as Record<string, LayerKey>;

const THEME_CODE: Record<ThemePreference, string> = { system: "sys", light: "l", dark: "d" };
const CODE_THEME: Record<string, ThemePreference> = { sys: "system", l: "light", d: "dark" };

export interface PermalinkState {
  mapView: MapView;
  activeLayers: LayerKey[];
  selection: Selection | null;
  mode: ViewMode;
  theme: ThemePreference;
  filters: Filters;
  warningPanelView?: WarningPanelView;
  warningHistoryFilters?: WarningHistoryFilters;
}

/** Serialize app state into a URL query string (no sensitive local state). */
export function encodePermalink(state: PermalinkState): string {
  const params = new URLSearchParams();
  params.set("c", `${state.mapView.lat.toFixed(4)},${state.mapView.lng.toFixed(4)}`);
  params.set("z", state.mapView.zoom.toFixed(1));
  params.set("l", state.activeLayers.map((key) => LAYER_CODE[key]).join(","));
  params.set("m", state.mode === "expert" ? "e" : "s");
  if (state.theme !== "system") {
    params.set("t", THEME_CODE[state.theme]);
  }
  if (state.selection) {
    const prefix =
      state.selection.kind === "warning-history"
        ? "h"
        : state.selection.kind === "warning"
          ? "w"
          : "s";
    params.set("sel", `${prefix}:${state.selection.id}`);
  }
  if (state.filters.warningLevel !== null) {
    params.set("wl", String(state.filters.warningLevel));
  }
  if (state.filters.phenomenon.trim()) {
    params.set("ph", state.filters.phenomenon.trim());
  }
  if (state.filters.province.trim()) {
    params.set("pv", state.filters.province.trim());
  }
  if (state.filters.county.trim()) {
    params.set("cy", state.filters.county.trim());
  }
  if (state.filters.basin.trim()) {
    params.set("bs", state.filters.basin.trim());
  }
  if (state.filters.maxDataDelayMinutes !== null) {
    params.set("md", String(state.filters.maxDataDelayMinutes));
  }
  if (state.filters.onlyStaleCache) {
    params.set("osc", "1");
  }
  if (state.warningPanelView === "history") {
    params.set("wv", "h");
  }
  const history = state.warningHistoryFilters;
  if (history?.warningType) params.set("wt", history.warningType);
  if (history?.office.trim()) params.set("wo", history.office.trim());
  if (history?.area.trim()) params.set("wa", history.area.trim());
  if (history?.changeKind) params.set("wk", history.changeKind);
  if (history?.from) params.set("wf", history.from);
  if (history?.to) params.set("wto", history.to);
  return params.toString();
}

/** Parse a URL query string back into a partial app state. Invalid parts are ignored. */
export function decodePermalink(search: string): Partial<PermalinkState> {
  const params = new URLSearchParams(search);
  const result: Partial<PermalinkState> = {};

  const center = params.get("c");
  const zoom = params.get("z");
  if (center) {
    const [lat, lng] = center.split(",").map(Number);
    if (Number.isFinite(lat) && Number.isFinite(lng)) {
      const z = Number(zoom);
      result.mapView = { lat, lng, zoom: Number.isFinite(z) ? z : 5.4 };
    }
  }

  const layers = params.get("l");
  if (layers !== null) {
    const keys = layers
      .split(",")
      .map((code) => CODE_LAYER[code])
      .filter((key): key is LayerKey => Boolean(key));
    result.activeLayers = DEFAULT_ACTIVE_LAYERS.filter((key) => keys.includes(key));
  }

  const mode = params.get("m");
  if (mode === "e" || mode === "s") {
    result.mode = mode === "e" ? "expert" : "simple";
  }

  const theme = params.get("t");
  if (theme && CODE_THEME[theme]) {
    result.theme = CODE_THEME[theme];
  }

  const sel = params.get("sel");
  if (sel) {
    const [prefix, ...rest] = sel.split(":");
    const id = rest.join(":");
    if (id && (prefix === "w" || prefix === "s" || prefix === "h")) {
      result.selection = {
        kind: prefix === "h" ? "warning-history" : prefix === "w" ? "warning" : "station",
        id,
      };
    }
  }

  const warningLevel = params.get("wl");
  const phenomenon = params.get("ph");
  const province = params.get("pv") ?? params.get("pr");
  const county = params.get("cy") ?? params.get("co");
  const basin = params.get("bs") ?? params.get("ba");
  const maxDelay = params.get("md");
  const onlyStale = params.get("osc");
  if (
    warningLevel !== null ||
    phenomenon !== null ||
    province !== null ||
    county !== null ||
    basin !== null ||
    maxDelay !== null ||
    onlyStale !== null
  ) {
    const level = Number(warningLevel);
    const delay = Number(maxDelay);
    result.filters = {
      warningLevel: warningLevel !== null && Number.isFinite(level) ? level : null,
      phenomenon: phenomenon ?? "",
      province: province ?? "",
      county: county ?? "",
      basin: basin ?? "",
      maxDataDelayMinutes: maxDelay !== null && Number.isFinite(delay) ? delay : null,
      onlyStaleCache: onlyStale === "1",
    };
  }

  if (params.get("wv") === "h") {
    result.warningPanelView = "history";
  }
  const warningType = params.get("wt");
  const changeKind = params.get("wk");
  const from = params.get("wf");
  const to = params.get("wto");
  const historyFilterValues = {
    warningType: warningType === "meteo" || warningType === "hydro" ? warningType : "",
    office: params.get("wo") ?? "",
    area: params.get("wa") ?? "",
    changeKind: WARNING_CHANGE_KINDS.includes(changeKind as WarningChangeKind)
      ? (changeKind as WarningChangeKind)
      : "",
    from: from && isDateOnly(from) ? from : "",
    to: to && isDateOnly(to) ? to : "",
  } satisfies WarningHistoryFilters;
  if (Object.values(historyFilterValues).some(Boolean)) {
    result.warningHistoryFilters = historyFilterValues;
  }

  return result;
}
