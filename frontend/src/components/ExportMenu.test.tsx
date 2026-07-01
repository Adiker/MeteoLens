import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as mapBus from "../lib/mapBus";
import { useAppStore } from "../store/appStore";
import { ExportMenu } from "./ExportMenu";

function reset() {
  useAppStore.setState({ selection: null });
  useAppStore.getState().setActiveLayers([
    "synop_stations",
    "hydro_stations",
    "meteo_stations",
    "warnings_meteo",
    "warnings_hydro",
  ]);
}

describe("ExportMenu", () => {
  beforeEach(reset);
  afterEach(reset);

  it("opens the menu and shows the map GeoJSON export when layers are active", () => {
    render(<ExportMenu />);

    fireEvent.click(screen.getByLabelText("Eksport danych"));

    expect(screen.getByRole("menu")).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: /Widoczna mapa — GeoJSON/ })).toBeEnabled();
  });

  it("disables the map GeoJSON export when no layers are active", () => {
    useAppStore.getState().setActiveLayers([]);
    render(<ExportMenu />);

    fireEvent.click(screen.getByLabelText("Eksport danych"));

    expect(screen.getByRole("menuitem", { name: /Widoczna mapa — GeoJSON/ })).toBeDisabled();
  });

  it("shows station export links only when a station is selected", () => {
    render(<ExportMenu />);
    fireEvent.click(screen.getByLabelText("Eksport danych"));
    expect(screen.getByText("Wybierz stację, aby wyeksportować jej dane.")).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText("Eksport danych"));
    useAppStore.setState({ selection: { kind: "station", id: "hydro:1" } });
    fireEvent.click(screen.getByLabelText("Eksport danych"));

    expect(screen.getByRole("menuitem", { name: "Stacja — CSV" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Stacja — JSON" })).toBeInTheDocument();
  });

  it("triggers a PNG capture and closes the menu", () => {
    const spy = vi.spyOn(mapBus, "captureMapPng").mockImplementation(() => {});
    render(<ExportMenu />);
    fireEvent.click(screen.getByLabelText("Eksport danych"));

    fireEvent.click(screen.getByRole("menuitem", { name: /Bieżąca mapa — PNG/ }));

    expect(spy).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    spy.mockRestore();
  });

  it("closes the menu when clicking outside of it", () => {
    render(<ExportMenu />);
    fireEvent.click(screen.getByLabelText("Eksport danych"));
    expect(screen.getByRole("menu")).toBeInTheDocument();

    fireEvent.mouseDown(document.body);

    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });
});
