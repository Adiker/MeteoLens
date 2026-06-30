import { beforeEach, describe, expect, it } from "vitest";

import { activeLayerKeys, POLAND_VIEW, useAppStore } from "./appStore";

function reset() {
  useAppStore.setState({
    selection: null,
    mode: "simple",
    theme: "system",
    filters: { warningLevel: null, phenomenon: "" },
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
});
