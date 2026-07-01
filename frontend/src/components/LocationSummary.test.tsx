import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { LocationSummaryResponse } from "../api/client";
import { useAppStore } from "../store/appStore";
import { LocationSummary } from "./LocationSummary";

function renderWithClient() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <LocationSummary />
    </QueryClientProvider>,
  );
}

function mockFetch(status: number, body: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve({
        ok: status >= 200 && status < 300,
        status,
        json: () => Promise.resolve(body),
      } as Response),
    ),
  );
}

const summary: LocationSummaryResponse = {
  generated_at: "2026-06-30T07:30:00Z",
  cache: [],
  empty_state: null,
  location: { lat: 51.52, lon: 14.82 },
  radius_km: 20,
  notes: ["Warnings are not spatially matched yet."],
  nearest_stations: [
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
      distance_km: 1.2,
    },
  ],
  warnings: [
    {
      kind: "warning",
      id: "warningsmeteo:Sk1",
      source_id: "Sk1",
      source_key: "warningsmeteo",
      warning_type: "meteo",
      event: "Burze",
      level: 2,
      probability: 70,
      valid_from: "2026-06-30T14:00:00+02:00",
      valid_to: "2026-06-30T20:00:00+02:00",
      published_at: "2026-06-30T06:32:00+02:00",
      office: null,
      content: null,
      comment: null,
      areas: [],
      area_codes: [],
      missing_fields: [],
      source: {
        provider: "IMGW-PIB",
        source_key: "warningsmeteo",
        url: "https://danepubliczne.imgw.pl/api/data/warningsmeteo",
        retrieved_at: "2026-06-30T07:30:00Z",
        attribution: "Źródło danych: IMGW-PIB.",
        processed_notice: "Dane IMGW-PIB zostały przetworzone przez MeteoLens.",
      },
      raw: {},
      raw_available: true,
    },
  ],
};

describe("LocationSummary", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    useAppStore.setState({ userLocation: null, selection: null });
  });

  it("renders nothing without a user location", () => {
    useAppStore.setState({ userLocation: null });
    const { container } = renderWithClient();
    expect(container).toBeEmptyDOMElement();
  });

  it("lists nearest stations and active warnings", async () => {
    mockFetch(200, summary);
    useAppStore.setState({ userLocation: { lat: 51.52, lon: 14.82 } });

    renderWithClient();

    expect(await screen.findByText("Przewoźniki")).toBeInTheDocument();
    expect(screen.getByText("1.2 km")).toBeInTheDocument();
    expect(screen.getByText("Burze")).toBeInTheDocument();
    expect(screen.getByText("Warnings are not spatially matched yet.")).toBeInTheDocument();
  });

  it("selects a station when clicked", async () => {
    mockFetch(200, summary);
    useAppStore.setState({ userLocation: { lat: 51.52, lon: 14.82 } });

    renderWithClient();
    fireEvent.click(await screen.findByText("Przewoźniki"));

    expect(useAppStore.getState().selection).toEqual({ kind: "station", id: "hydro:151140030" });
  });

  it("clears the user location", async () => {
    mockFetch(200, summary);
    useAppStore.setState({ userLocation: { lat: 51.52, lon: 14.82 } });

    renderWithClient();
    await screen.findByText("Przewoźniki");
    fireEvent.click(screen.getByLabelText("Wyczyść lokalizację"));

    expect(useAppStore.getState().userLocation).toBeNull();
  });

  it("shows an error notice when the summary request fails", async () => {
    mockFetch(503, { detail: { error: { code: "cache_empty", message: "Brak cache" } } });
    useAppStore.setState({ userLocation: { lat: 51.52, lon: 14.82 } });

    renderWithClient();

    expect(
      await screen.findByText("Nie udało się pobrać danych lokalizacji."),
    ).toBeInTheDocument();
  });
});
