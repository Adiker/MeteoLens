import { describe, expect, it } from "vitest";

import { decodePermalink, encodePermalink, type PermalinkState } from "./permalink";

const baseState: PermalinkState = {
  mapView: { lat: 52.2297, lng: 21.0122, zoom: 9 },
  activeLayers: ["synop_stations", "warnings_meteo"],
  selection: { kind: "station", id: "synop:12375" },
  mode: "expert",
  theme: "dark",
  filters: {
    warningLevel: 2,
    phenomenon: "burze",
    province: "12",
    county: "1205",
    basin: "B1",
    maxDataDelayMinutes: 45,
    onlyStaleCache: true,
  },
};

describe("permalink", () => {
  it("round-trips full state", () => {
    const decoded = decodePermalink(encodePermalink(baseState));
    expect(decoded.mapView).toEqual({ lat: 52.2297, lng: 21.0122, zoom: 9 });
    expect(decoded.activeLayers).toEqual(["synop_stations", "warnings_meteo"]);
    expect(decoded.selection).toEqual({ kind: "station", id: "synop:12375" });
    expect(decoded.mode).toBe("expert");
    expect(decoded.theme).toBe("dark");
    expect(decoded.filters).toEqual(baseState.filters);
  });

  it("omits theme from the URL when it is system default", () => {
    const qs = encodePermalink({ ...baseState, theme: "system" });
    expect(qs).not.toContain("t=");
    expect(decodePermalink(qs).theme).toBeUndefined();
  });

  it("ignores unknown layer codes and malformed center", () => {
    const decoded = decodePermalink("l=syn,zzz&c=notanumber");
    expect(decoded.activeLayers).toEqual(["synop_stations"]);
    expect(decoded.mapView).toBeUndefined();
  });

  it("decodes a warning selection", () => {
    expect(decodePermalink("sel=w:meteo:123").selection).toEqual({
      kind: "warning",
      id: "meteo:123",
    });
  });

  it("accepts legacy spatial filter aliases", () => {
    expect(decodePermalink("pr=12&co=1205&ba=B1").filters).toMatchObject({
      province: "12",
      county: "1205",
      basin: "B1",
    });
  });
});
