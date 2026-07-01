import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useAppStore } from "../store/appStore";
import { HeaderBar } from "./HeaderBar";

function renderHeader() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <HeaderBar />
    </QueryClientProvider>,
  );
}

function reset() {
  useAppStore.setState({
    mode: "simple",
    theme: "system",
    controlPanelOpen: true,
    shortcutHelpOpen: false,
    userLocation: null,
  });
}

describe("HeaderBar", () => {
  beforeEach(() => {
    reset();
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new Error("no backend"))),
    );
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    reset();
  });

  it("toggles simple/expert mode", () => {
    renderHeader();
    fireEvent.click(screen.getByLabelText("Przełącz tryb prosty/ekspercki"));
    expect(useAppStore.getState().mode).toBe("expert");
  });

  it("cycles the theme", () => {
    renderHeader();
    fireEvent.click(screen.getByLabelText("Motyw: systemowy"));
    expect(useAppStore.getState().theme).toBe("light");
  });

  it("toggles the control panel", () => {
    renderHeader();
    fireEvent.click(screen.getByLabelText("Pokaż/ukryj panel warstw"));
    expect(useAppStore.getState().controlPanelOpen).toBe(false);
  });

  it("opens the shortcut help panel", () => {
    renderHeader();
    fireEvent.click(screen.getByLabelText("Skróty klawiszowe"));
    expect(useAppStore.getState().shortcutHelpOpen).toBe(true);
  });

  it("stores the user location on a successful geolocation lookup", () => {
    const getCurrentPosition = vi.fn((success: PositionCallback) => {
      success({
        coords: { latitude: 52.1, longitude: 21.0 },
      } as GeolocationPosition);
    });
    vi.stubGlobal("navigator", {
      ...navigator,
      geolocation: { getCurrentPosition },
    });

    renderHeader();
    fireEvent.click(screen.getByLabelText("Pokaż dane dla mojej lokalizacji"));

    expect(useAppStore.getState().userLocation).toEqual({ lat: 52.1, lon: 21.0 });
  });

  it("alerts when geolocation lookup fails", () => {
    const getCurrentPosition = vi.fn(
      (_success: PositionCallback, error: PositionErrorCallback) => {
        error({} as GeolocationPositionError);
      },
    );
    vi.stubGlobal("navigator", {
      ...navigator,
      geolocation: { getCurrentPosition },
    });
    const alertSpy = vi.spyOn(window, "alert").mockImplementation(() => {});

    renderHeader();
    fireEvent.click(screen.getByLabelText("Pokaż dane dla mojej lokalizacji"));

    expect(alertSpy).toHaveBeenCalledWith("Nie udało się ustalić lokalizacji.");
    expect(useAppStore.getState().userLocation).toBeNull();
    alertSpy.mockRestore();
  });

  it("alerts when geolocation is unsupported", () => {
    // `geolocation` key must be absent entirely — `in` treats an explicit
    // `undefined` value as still present, which would defeat this check.
    const navigatorWithoutGeolocation = { ...navigator };
    delete (navigatorWithoutGeolocation as { geolocation?: Geolocation }).geolocation;
    vi.stubGlobal("navigator", navigatorWithoutGeolocation);
    const alertSpy = vi.spyOn(window, "alert").mockImplementation(() => {});

    renderHeader();
    fireEvent.click(screen.getByLabelText("Pokaż dane dla mojej lokalizacji"));

    expect(alertSpy).toHaveBeenCalledWith("Przeglądarka nie udostępnia lokalizacji.");
    alertSpy.mockRestore();
  });
});
