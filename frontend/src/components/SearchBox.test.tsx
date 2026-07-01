import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { StationsResponse } from "../api/client";
import * as mapBus from "../lib/mapBus";
import { useAppStore } from "../store/appStore";
import { SearchBox } from "./SearchBox";

function renderWithClient() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <SearchBox />
    </QueryClientProvider>,
  );
}

const searchResponse: StationsResponse = {
  generated_at: "2026-06-30T07:30:00Z",
  cache: [],
  empty_state: null,
  stations: [
    {
      id: "hydro:151140030",
      source_id: "151140030",
      source_key: "hydro",
      station_type: "hydro",
      name: "Przewoźniki",
      lat: 51.5253,
      lon: 14.8217,
      latest_observed_at: null,
      data_delay_seconds: null,
      missing_fields: [],
      source: {
        provider: "IMGW-PIB",
        source_key: "hydro",
        url: "https://danepubliczne.imgw.pl/api/data/hydro",
        retrieved_at: "2026-06-30T07:30:00Z",
        attribution: "Źródło danych: IMGW-PIB.",
        processed_notice: "Dane IMGW-PIB zostały przetworzone przez MeteoLens.",
      },
      raw_available: true,
    },
  ],
};

describe("SearchBox", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    useAppStore.setState({ selection: null });
  });

  it("shows matching stations after typing at least two characters", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve(searchResponse),
        } as Response),
      ),
    );
    renderWithClient();

    fireEvent.change(screen.getByLabelText("Szukaj stacji"), { target: { value: "Prze" } });
    fireEvent.focus(screen.getByLabelText("Szukaj stacji"));

    expect(await screen.findByText("Przewoźniki")).toBeInTheDocument();
  });

  it("selects a station and flies the map to its coordinates", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve(searchResponse),
        } as Response),
      ),
    );
    const flySpy = vi.spyOn(mapBus, "flyTo").mockImplementation(() => {});
    renderWithClient();

    fireEvent.change(screen.getByLabelText("Szukaj stacji"), { target: { value: "Prze" } });
    const option = await screen.findByText("Przewoźniki");
    fireEvent.mouseDown(option);

    expect(useAppStore.getState().selection).toEqual({ kind: "station", id: "hydro:151140030" });
    expect(flySpy).toHaveBeenCalledWith({ lng: 14.8217, lat: 51.5253, zoom: 9 });
    flySpy.mockRestore();
  });

  it("shows an unavailable message when the search request fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new Error("network down"))),
    );
    renderWithClient();

    fireEvent.change(screen.getByLabelText("Szukaj stacji"), { target: { value: "Prze" } });

    expect(
      await screen.findByText("Wyszukiwanie niedostępne — sprawdź backend."),
    ).toBeInTheDocument();
  });

  it("does not query for a single-character term", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    renderWithClient();

    fireEvent.change(screen.getByLabelText("Szukaj stacji"), { target: { value: "P" } });
    // Let the 250ms debounce elapse; the query must stay disabled below 2 chars.
    await new Promise((resolve) => setTimeout(resolve, 350));

    expect(fetchMock).not.toHaveBeenCalled();
  });
});
