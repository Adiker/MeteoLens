import { describe, expect, it } from "vitest";

import { cacheStatusLabel, formatDelay, formatValue, metricLabel, warningLevelLabel } from "./format";

describe("format helpers", () => {
  it("formats data delays compactly", () => {
    expect(formatDelay(null)).toBe("—");
    expect(formatDelay(30)).toBe("30 s");
    expect(formatDelay(90)).toBe("2 min");
    expect(formatDelay(3600)).toBe("1 h");
    expect(formatDelay(3900)).toBe("1 h 5 min");
  });

  it("keeps missing values explicit instead of using zero", () => {
    expect(formatValue(null, "°C")).toBe("brak danych");
    expect(formatValue(undefined, "°C")).toBe("brak danych");
    expect(formatValue(0, "mm")).toBe("0 mm");
  });

  it("labels known metrics and falls back for unknown ones", () => {
    expect(metricLabel("temperature")).toBe("Temperatura");
    expect(metricLabel("custom_metric")).toBe("custom metric");
  });

  it("labels warning levels and cache statuses", () => {
    expect(warningLevelLabel(3)).toContain("czerwony");
    expect(warningLevelLabel(null)).toBe("—");
    expect(cacheStatusLabel("fresh")).toBe("aktualny");
    expect(cacheStatusLabel("unknown")).toBe("unknown");
  });
});
