import { beforeEach, describe, expect, it } from "vitest";

import { activeLayerKeys, POLAND_VIEW, useAppStore } from "./appStore";

function reset() {
  useAppStore.setState({
    selection: null,
    mode: "simple",
    theme: "system",
    filters: { warningLevel: null, phenomenon: "", province: "", county: "", basin: "" },
    mapView: POLAND_VIEW,
  });
  useAppStore.getState().setActiveLayers([
    "synop_stations",
    "hydro_stations",
    "meteo_stations",
    "warnings_meteo",
    "warnings_hydro",
  ]);
}

describe("appStore", () => {
  beforeEach(reset);

  it("toggles a layer on and off", () => {
    const { toggleLayer } = useAppStore.getState();
    toggleLayer("synop_stations");
    expect(useAppStore.getState().activeLayers.synop_stations).toBe(false);
    toggleLayer("synop_stations");
    expect(useAppStore.getState().activeLayers.synop_stations).toBe(true);
  });

  it("cycles theme system -> light -> dark -> system", () => {
    const { cycleTheme } = useAppStore.getState();
    cycleTheme();
    expect(useAppStore.getState().theme).toBe("light");
    cycleTheme();
    expect(useAppStore.getState().theme).toBe("dark");
    cycleTheme();
    expect(useAppStore.getState().theme).toBe("system");
  });

  it("derives active layer keys in registry order", () => {
    useAppStore.getState().setActiveLayers(["warnings_hydro", "synop_stations"]);
    expect(activeLayerKeys(useAppStore.getState().activeLayers)).toEqual([
      "synop_stations",
      "warnings_hydro",
    ]);
  });

  it("clears selection", () => {
    const store = useAppStore.getState();
    store.select({ kind: "warning", id: "meteo:1" });
    expect(useAppStore.getState().selection).not.toBeNull();
    store.clearSelection();
    expect(useAppStore.getState().selection).toBeNull();
  });

  it("sets a single layer's active state directly", () => {
    useAppStore.getState().setLayerActive("hydro_stations", false);
    expect(useAppStore.getState().activeLayers.hydro_stations).toBe(false);
    useAppStore.getState().setLayerActive("hydro_stations", true);
    expect(useAppStore.getState().activeLayers.hydro_stations).toBe(true);
  });

  it("toggles simple/expert mode", () => {
    expect(useAppStore.getState().mode).toBe("simple");
    useAppStore.getState().toggleMode();
    expect(useAppStore.getState().mode).toBe("expert");
    useAppStore.getState().toggleMode();
    expect(useAppStore.getState().mode).toBe("simple");
  });

  it("sets and resets filters", () => {
    useAppStore.getState().setFilter("warningLevel", 2);
    useAppStore.getState().setFilter("phenomenon", "Burze");
    expect(useAppStore.getState().filters).toEqual({
      warningLevel: 2,
      phenomenon: "Burze",
      province: "",
      county: "",
      basin: "",
    });
    useAppStore.getState().resetFilters();
    expect(useAppStore.getState().filters).toEqual({
      warningLevel: null,
      phenomenon: "",
      province: "",
      county: "",
      basin: "",
    });
  });

  it("sets the map view and user location", () => {
    useAppStore.getState().setMapView({ lng: 20, lat: 50, zoom: 8 });
    expect(useAppStore.getState().mapView).toEqual({ lng: 20, lat: 50, zoom: 8 });
    useAppStore.getState().setUserLocation({ lat: 50, lon: 20 });
    expect(useAppStore.getState().userLocation).toEqual({ lat: 50, lon: 20 });
    useAppStore.getState().setUserLocation(null);
    expect(useAppStore.getState().userLocation).toBeNull();
  });

  it("controls the control-panel and shortcut-help open state", () => {
    useAppStore.getState().setControlPanelOpen(false);
    expect(useAppStore.getState().controlPanelOpen).toBe(false);
    useAppStore.getState().toggleControlPanel();
    expect(useAppStore.getState().controlPanelOpen).toBe(true);

    useAppStore.getState().setShortcutHelpOpen(true);
    expect(useAppStore.getState().shortcutHelpOpen).toBe(true);
  });
});
