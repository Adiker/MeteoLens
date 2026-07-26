import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Observation } from "../api/client";

// jsdom has no real canvas backing, which makes zrender's painter throw deep
// inside echarts; the component only needs the init/setOption/resize/dispose
// surface, so stub it instead of exercising a real chart engine here.
const chartMocks = vi.hoisted(() => ({
  setOption: vi.fn(),
}));

vi.mock("echarts", () => ({
  init: () => ({
    setOption: chartMocks.setOption,
    resize: () => {},
    dispose: () => {},
  }),
}));

const { StationChart } = await import("./StationChart");

function observation(overrides: Partial<Observation> = {}): Observation {
  return {
    metric: "temperature",
    value: 12.3,
    unit: "°C",
    observed_at: "2026-06-30T07:00:00+02:00",
    raw_field: "temperatura",
    missing: false,
    ...overrides,
  };
}

describe("StationChart", () => {
  beforeEach(() => {
    chartMocks.setOption.mockClear();
  });

  it("shows a fallback message when there are no numeric values", () => {
    render(<StationChart observations={[observation({ value: null, missing: true })]} />);

    expect(
      screen.getByText("Brak wartości liczbowych do wykresu (wszystkie metryki są puste)."),
    ).toBeInTheDocument();
  });

  it("renders no fallback text when there are numeric values", () => {
    render(<StationChart observations={[observation()]} />);

    expect(screen.getByLabelText("Wykres pomiarów stacji")).toBeInTheDocument();
    expect(screen.queryByText(/Brak wartości liczbowych/)).not.toBeInTheDocument();
  });

  it("excludes missing/null observations from the chart data", () => {
    render(
      <StationChart
        observations={[observation(), observation({ metric: "pressure", value: null, missing: true })]}
      />,
    );

    expect(screen.getByLabelText("Wykres pomiarów stacji")).toBeInTheDocument();
  });

  it("renders live and archive as separate series and keeps source nulls as gaps", () => {
    render(
      <StationChart
        seriesKind="history"
        observations={[
          observation({
            metric: "water_level",
            value: 120,
            unit: "cm",
            origin: "live_refresh",
          }),
          observation({
            metric: "water_level",
            value: 118,
            unit: "cm",
            observed_at: "2026-06-29T00:00:00Z",
            origin: "archive_import",
            temporal_resolution: "1d",
          }),
          observation({
            metric: "water_level",
            value: null,
            unit: "cm",
            observed_at: "2026-06-28T00:00:00Z",
            origin: "archive_import",
            missing: true,
            missing_reason: "source_null",
            temporal_resolution: "1d",
          }),
        ]}
      />,
    );

    const option = chartMocks.setOption.mock.calls[0][0] as {
      series: Array<{
        name: string;
        connectNulls: boolean;
        data: Array<{ value: [string, number | null] }>;
      }>;
    };
    expect(option.series.map((series) => series.name)).toEqual([
      "Archiwum IMGW",
      "Live IMGW",
    ]);
    expect(option.series.every((series) => series.connectNulls === false)).toBe(true);
    expect(option.series[0].data.some((point) => point.value[1] === null)).toBe(true);
  });
});
