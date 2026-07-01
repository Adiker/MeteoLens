import { describe, expect, it } from "vitest";

import { evaluateAlertRule, staleSourceKeys } from "./alertRules";
import type { AlertRule } from "./userData";

describe("alertRules", () => {
  it("triggers warning_nearby when warnings exist", () => {
    const rule: AlertRule = {
      id: "a1",
      name: "Nearby",
      enabled: true,
      type: "warning_nearby",
    };
    const result = evaluateAlertRule(rule, {
      userLocation: { lat: 52, lon: 21 },
      nearbyWarningCount: 2,
      maxNearbyWarningLevel: 2,
      stationMetricValue: null,
      staleSourceKeys: [],
    });
    expect(result.triggered).toBe(true);
  });

  it("disables warning_nearby without user location", () => {
    const rule: AlertRule = {
      id: "a2",
      name: "Nearby",
      enabled: true,
      type: "warning_nearby",
    };
    const result = evaluateAlertRule(rule, {
      userLocation: null,
      nearbyWarningCount: 0,
      maxNearbyWarningLevel: null,
      stationMetricValue: null,
      staleSourceKeys: [],
    });
    expect(result.triggered).toBe(false);
    expect(result.disabledReason).toBeTruthy();
  });

  it("collects stale source keys", () => {
    const keys = staleSourceKeys([
      {
        key: "synop",
        title: "Synop",
        url: "https://example.test/synop",
        parser_status: "implemented",
        cache_status: "stale",
        cache: {
          status: "stale",
          parser_warnings: [],
        },
      },
    ]);
    expect(keys).toEqual(["synop"]);
  });
});
