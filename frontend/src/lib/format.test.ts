import { describe, expect, it } from "vitest";

import {
  cacheStatusLabel,
  formatDelay,
  formatTimestamp,
  formatValue,
  isDateOnly,
  metricLabel,
  sourceDateEnd,
  sourceDateStart,
  warningLevelLabel,
  WARNING_LEVEL_COLOR,
} from "./format";

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
    expect(metricLabel("air_temperature")).toBe("Temperatura powietrza");
    expect(metricLabel("ground_temperature")).toBe("Temperatura przy gruncie");
    expect(metricLabel("wind_average_speed")).toBe("Średnia prędkość wiatru");
    expect(metricLabel("wind_max_speed")).toBe("Maksymalna prędkość wiatru");
    expect(metricLabel("wind_gust_10min")).toBe("Poryw wiatru (10 min)");
    expect(metricLabel("precipitation_10min")).toBe("Opad (10 min)");
    expect(metricLabel("custom_metric")).toBe("custom metric");
  });

  it("renders timestamps in Polish source time regardless of runner timezone", () => {
    // 10:00 UTC is 12:00 in Warsaw (summer, +2); the label keeps the zone explicit.
    const formatted = formatTimestamp("2026-06-30T10:00:00Z");
    expect(formatted).toContain("12:00");
    expect(formatted).toMatch(/GMT\+2|CEST/);
    expect(formatTimestamp(null)).toBe("—");
  });

  it("converts date filters to complete Europe/Warsaw calendar days", () => {
    expect(sourceDateStart("2026-07-01")).toBe("2026-06-30T22:00:00.000Z");
    expect(sourceDateEnd("2026-07-01")).toBe("2026-07-01T21:59:59.999Z");
    expect(sourceDateStart("2026-01-01")).toBe("2025-12-31T23:00:00.000Z");
    expect(sourceDateEnd("2026-03-29")).toBe("2026-03-29T21:59:59.999Z");
    expect(sourceDateStart("not-a-date")).toBeUndefined();
    expect(isDateOnly("2026-02-29")).toBe(false);
    expect(isDateOnly("2028-02-29")).toBe(true);
  });

  it("labels warning levels and cache statuses", () => {
    expect(warningLevelLabel(3)).toContain("czerwony");
    expect(WARNING_LEVEL_COLOR[-1]).toBeDefined();
    expect(warningLevelLabel(null)).toBe("—");
    expect(cacheStatusLabel("fresh")).toBe("aktualny");
    expect(cacheStatusLabel("unknown")).toBe("unknown");
  });
});
