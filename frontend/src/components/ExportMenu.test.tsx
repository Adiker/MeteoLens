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
    expect(screen.getByRole("menuitem", { name: /Stan mapy — JSON/ })).toBeEnabled();
    expect(screen.getByRole("menuitem", { name: /Ostrzeżenia — GeoJSON/ })).toBeEnabled();
  });

  it("disables the map GeoJSON export when no layers are active", () => {
    useAppStore.getState().setActiveLayers([]);
    render(<ExportMenu />);

    fireEvent.click(screen.getByLabelText("Eksport danych"));

    expect(screen.getByRole("menuitem", { name: /Widoczna mapa — GeoJSON/ })).toBeDisabled();
    expect(screen.getByRole("menuitem", { name: /Stan mapy — JSON/ })).toBeDisabled();
    expect(screen.getByRole("menuitem", { name: /Ostrzeżenia — GeoJSON/ })).toBeDisabled();
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

  it("builds export links from the current filters and view", () => {
    useAppStore.getState().setFilter("warningLevel", 2);
    useAppStore.getState().setFilter("province", "12");
    useAppStore.getState().setMapView({ lng: 19.1, lat: 52.2, zoom: 6 });
    render(<ExportMenu />);

    fireEvent.click(screen.getByLabelText("Eksport danych"));

    const stateLink = screen.getByRole("menuitem", { name: /Stan mapy — JSON/ });
    const warningLink = screen.getByRole("menuitem", { name: /Ostrzeżenia — GeoJSON/ });
    expect(stateLink).toHaveAttribute("href", expect.stringContaining("lng=19.1"));
    expect(stateLink).toHaveAttribute("href", expect.stringContaining("warning_level=2"));
    expect(warningLink).toHaveAttribute("href", expect.stringContaining("level=2"));
    expect(warningLink).toHaveAttribute("href", expect.stringContaining("province=12"));
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
