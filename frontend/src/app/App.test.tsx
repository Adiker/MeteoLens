import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

class FakeMap {
  addControl = vi.fn();
  addSource = vi.fn();
  addLayer = vi.fn();
  getSource = vi.fn();
  getLayer = vi.fn();
  setFilter = vi.fn();
  flyTo = vi.fn();
  on = vi.fn();
  remove = vi.fn();
  getCanvas = vi.fn(() => ({ style: {} }) as unknown as HTMLCanvasElement);
  getCenter = vi.fn(() => ({ lng: 19, lat: 52 }));
  getZoom = vi.fn(() => 5.4);
}

vi.mock("maplibre-gl", () => ({
  default: {
    Map: FakeMap,
    NavigationControl: class {},
    AttributionControl: class {},
  },
}));

describe("App", () => {
  beforeEach(() => {
    // No backend in unit tests: queries fail gracefully.
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new Error("no backend"))),
    );
    window.history.replaceState(null, "", "/");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders the MeteoLens shell", async () => {
    const { App } = await import("./App");
    render(<App />);

    expect(screen.getByRole("heading", { name: "MeteoLens" })).toBeInTheDocument();
    expect(screen.getByLabelText("Mapa MeteoLens")).toBeInTheDocument();
    expect(screen.getByText("Źródło danych: IMGW-PIB.")).toBeInTheDocument();
    // Layer registry is rendered as toggles.
    expect(screen.getByLabelText("Warstwa Stacje synoptyczne")).toBeInTheDocument();
  });
});
