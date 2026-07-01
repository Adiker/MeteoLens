import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Observation } from "../api/client";

// jsdom has no real canvas backing, which makes zrender's painter throw deep
// inside echarts; the component only needs the init/setOption/resize/dispose
// surface, so stub it instead of exercising a real chart engine here.
vi.mock("echarts", () => ({
  init: () => ({
    setOption: () => {},
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
});
