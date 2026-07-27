import { useEffect, useRef } from "react";

import { decodePermalink, encodePermalink } from "../lib/permalink";
import { readStoredTheme } from "../lib/theme";
import { activeLayerKeys, useAppStore } from "../store/appStore";

/**
 * Two-way sync between app state and the URL query string.
 * On mount it hydrates the store from the permalink (and stored theme);
 * afterwards it writes serialisable state back to the URL via replaceState.
 */
export function usePermalink(): void {
  const hydrated = useRef(false);

  useEffect(() => {
    const store = useAppStore.getState();
    const decoded = decodePermalink(window.location.search);

    if (decoded.mapView) {
      store.setMapView(decoded.mapView);
    }
    if (decoded.activeLayers) {
      store.setActiveLayers(decoded.activeLayers);
    }
    if (decoded.selection) {
      store.select(decoded.selection);
    }
    if (decoded.mode) {
      store.setMode(decoded.mode);
    }
    if (decoded.filters) {
      store.setFilter("warningLevel", decoded.filters.warningLevel);
      store.setFilter("phenomenon", decoded.filters.phenomenon);
      store.setFilter("province", decoded.filters.province);
      store.setFilter("county", decoded.filters.county);
      store.setFilter("basin", decoded.filters.basin);
      store.setFilter("maxDataDelayMinutes", decoded.filters.maxDataDelayMinutes);
      store.setFilter("onlyStaleCache", decoded.filters.onlyStaleCache);
    }
    if (decoded.warningPanelView) {
      store.setWarningPanelView(decoded.warningPanelView);
    }
    if (decoded.warningHistoryFilters) {
      const history = decoded.warningHistoryFilters;
      store.setWarningHistoryFilter("warningType", history.warningType);
      store.setWarningHistoryFilter("office", history.office);
      store.setWarningHistoryFilter("area", history.area);
      store.setWarningHistoryFilter("changeKind", history.changeKind);
      store.setWarningHistoryFilter("from", history.from);
      store.setWarningHistoryFilter("to", history.to);
    }
    // Theme: permalink wins, otherwise fall back to the last stored preference.
    const storedTheme = decoded.theme ?? readStoredTheme();
    if (storedTheme) {
      store.setTheme(storedTheme);
    }

    hydrated.current = true;
  }, []);

  useEffect(() => {
    const unsubscribe = useAppStore.subscribe((state) => {
      if (!hydrated.current) {
        return;
      }
      const qs = encodePermalink({
        mapView: state.mapView,
        activeLayers: activeLayerKeys(state.activeLayers),
        selection: state.selection,
        mode: state.mode,
        theme: state.theme,
        filters: state.filters,
        warningPanelView: state.warningPanelView,
        warningHistoryFilters: state.warningHistoryFilters,
      });
      const next = `${window.location.pathname}?${qs}`;
      if (next !== `${window.location.pathname}${window.location.search}`) {
        window.history.replaceState(null, "", next);
      }
    });
    return unsubscribe;
  }, []);
}
