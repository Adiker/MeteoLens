import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("maplibre-gl", () => ({
  default: {
    Map: class {
      addControl = vi.fn();
      remove = vi.fn();
    },
    NavigationControl: class {}
  }
}));

describe("App", () => {
  it("renders the MeteoLens shell", async () => {
    const { App } = await import("./App");

    render(<App />);

    expect(screen.getByRole("heading", { name: "MeteoLens" })).toBeInTheDocument();
    expect(screen.getByLabelText("Mapa MeteoLens")).toBeInTheDocument();
    expect(screen.getByText("Źródło danych: IMGW-PIB.")).toBeInTheDocument();
  });
});
