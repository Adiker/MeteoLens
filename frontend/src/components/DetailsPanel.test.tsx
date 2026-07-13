import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ObservationResponse, StationResponse, WarningResponse } from "../api/client";
import { useAppStore } from "../store/appStore";
import { DetailsPanel } from "./DetailsPanel";

function renderWithClient() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <DetailsPanel />
    </QueryClientProvider>,
  );
}

function mockFetchByPath(handlers: Record<string, { status: number; body: unknown }>) {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      const match = Object.entries(handlers).find(([path]) => url.includes(path));
      if (!match) {
        return Promise.reject(new Error(`Unhandled fetch: ${url}`));
      }
      const [, { status, body }] = match;
      return Promise.resolve({
        ok: status >= 200 && status < 300,
        status,
        json: () => Promise.resolve(body),
      } as Response);
    }),
  );
}

const stationResponse: StationResponse = {
  generated_at: "2026-06-30T07:30:00Z",
  raw_available: true,
  latest_observed_at: "2026-06-30T07:00:00+02:00",
  data_delay_seconds: 1800,
  station: {
    kind: "station",
    id: "hydro:151140030",
    source_id: "151140030",
    source_key: "hydro",
    station_type: "hydro",
    name: "Przewoźniki",
    lat: 51.5253,
    lon: 14.8217,
    coordinate_source: "MeteoLens reviewed station fixture",
    region: "lubuskie",
    watercourse: "Skroda",
    observations: [
      {
        metric: "water_level",
        value: 227,
        unit: "cm",
        observed_at: "2026-06-30T07:00:00+02:00",
        raw_field: "stan_wody",
        missing: false,
      },
      {
        metric: "water_temperature",
        value: null,
        unit: "°C",
        observed_at: null,
        raw_field: "temperatura_wody",
        missing: true,
      },
    ],
    missing_fields: ["temperatura_wody"],
    source: {
      provider: "IMGW-PIB",
      source_key: "hydro",
      url: "https://danepubliczne.imgw.pl/api/data/hydro",
      retrieved_at: "2026-06-30T07:30:00Z",
      attribution: "Źródło danych: IMGW-PIB.",
      processed_notice: "Dane IMGW-PIB zostały przetworzone przez MeteoLens.",
    },
    raw: { id_stacji: "151140030" },
  },
};

const observationsResponse: ObservationResponse = {
  generated_at: "2026-06-30T07:30:00Z",
  station_id: "hydro:151140030",
  source: stationResponse.station.source,
  series_kind: "snapshot",
  series_origin: "live_refresh",
  origin_counts: { live_refresh: 2 },
  interval: "raw",
  empty_state: null,
  observations: stationResponse.station.observations,
};

const warningResponse: WarningResponse = {
  generated_at: "2026-06-30T07:30:00Z",
  geometry_status: "missing_area_geometry_dataset",
  raw_available: true,
  warning: {
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
    office: "Centralne Biuro Prognoz",
    content: "Prognozowane są burze.",
    comment: null,
    areas: [{ area_type: "teryt", code: "1205", label: "1205" }],
    area_codes: ["1205"],
    missing_fields: [],
    source: stationResponse.station.source,
    raw: { id: "Sk1" },
    raw_available: true,
  },
};

describe("DetailsPanel", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    useAppStore.setState({ selection: null, mode: "simple" });
  });

  it("renders nothing when there is no selection", () => {
    useAppStore.setState({ selection: null });
    const { container } = renderWithClient();
    expect(container).toBeEmptyDOMElement();
  });

  it("shows station details, honoring missing values and delay", async () => {
    mockFetchByPath({
      "/stations/hydro%3A151140030/observations": { status: 200, body: observationsResponse },
      "/stations/hydro%3A151140030": { status: 200, body: stationResponse },
    });
    useAppStore.setState({ selection: { kind: "station", id: "hydro:151140030" }, mode: "simple" });

    renderWithClient();

    expect(await screen.findByText("Przewoźniki")).toBeInTheDocument();
    expect(screen.getByText("MeteoLens reviewed station fixture")).toBeInTheDocument();
    expect(screen.getByText("Braki danych:", { exact: false })).toBeInTheDocument();
    // Missing value must render as an explicit "no data" label, never as 0.
    expect(screen.getByText("brak danych")).toBeInTheDocument();
    // The source footer must carry attribution and the processed-data notice.
    expect(screen.getByText("Źródło danych: IMGW-PIB.")).toBeInTheDocument();
    expect(
      screen.getByText("Dane IMGW-PIB zostały przetworzone przez MeteoLens."),
    ).toBeInTheDocument();
  });

  it("shows a localized current snapshot without flattening history into duplicate rows", async () => {
    const meteoStation: StationResponse = {
      ...stationResponse,
      station: {
        ...stationResponse.station,
        id: "meteo:252170210",
        source_id: "252170210",
        source_key: "meteo",
        station_type: "meteo",
        name: "Kórnik",
        observations: [
          {
            metric: "ground_temperature",
            value: 24.5,
            unit: "°C",
            observed_at: "2026-07-13T11:10:00+02:00",
            raw_field: "temperatura_gruntu",
            missing: false,
          },
          {
            metric: "air_temperature",
            value: 21.7,
            unit: "°C",
            observed_at: "2026-07-13T11:10:00+02:00",
            raw_field: "temperatura_powietrza",
            missing: false,
          },
        ],
      },
    };
    const meteoHistory: ObservationResponse = {
      ...observationsResponse,
      station_id: meteoStation.station.id,
      series_kind: "history",
      observations: [
        ...meteoStation.station.observations,
        {
          metric: "ground_temperature",
          value: 30.3,
          unit: "°C",
          observed_at: "2026-07-13T10:10:00+02:00",
          raw_field: "temperatura_gruntu",
          missing: false,
        },
        {
          metric: "air_temperature",
          value: 25.5,
          unit: "°C",
          observed_at: "2026-07-13T10:10:00+02:00",
          raw_field: "temperatura_powietrza",
          missing: false,
        },
      ],
    };

    mockFetchByPath({
      "/stations/meteo%3A252170210/observations": { status: 200, body: meteoHistory },
      "/stations/meteo%3A252170210": { status: 200, body: meteoStation },
    });
    useAppStore.setState({
      selection: { kind: "station", id: "meteo:252170210" },
      mode: "simple",
    });

    renderWithClient();

    expect(await screen.findByText("Kórnik")).toBeInTheDocument();
    expect(await screen.findByText("Seria z odświeżeń live IMGW-PIB")).toBeInTheDocument();
    expect(screen.getAllByText("Temperatura przy gruncie")).toHaveLength(1);
    expect(screen.getAllByText("Temperatura powietrza")).toHaveLength(1);
    expect(screen.getByText("24,5 °C")).toBeInTheDocument();
    expect(screen.getByText("21,7 °C")).toBeInTheDocument();
    expect(screen.queryByText("30,3 °C")).not.toBeInTheDocument();
    expect(screen.queryByText("25,5 °C")).not.toBeInTheDocument();
  });

  it("shows warning details with the missing-geometry notice and attribution", async () => {
    mockFetchByPath({
      "/warnings/warningsmeteo%3ASk1": { status: 200, body: warningResponse },
    });
    useAppStore.setState({ selection: { kind: "warning", id: "warningsmeteo:Sk1" }, mode: "simple" });

    renderWithClient();

    expect(await screen.findByText("Burze")).toBeInTheDocument();
    expect(screen.getByText("Brak geometrii obszaru")).toBeInTheDocument();
    expect(screen.getByText("Źródło danych: IMGW-PIB.")).toBeInTheDocument();
    expect(
      screen.getByText("Dane IMGW-PIB zostały przetworzone przez MeteoLens."),
    ).toBeInTheDocument();
  });

  it("shows resolved warning geometry without the missing-geometry notice", async () => {
    mockFetchByPath({
      "/warnings/warningsmeteo%3ASk1": {
        status: 200,
        body: {
          ...warningResponse,
          geometry_status: "resolved",
          warning: {
            ...warningResponse.warning,
            geometry_status: "resolved",
            resolved_areas: [
              {
                area_type: "teryt",
                code: "1205",
                label: "powiat myślenicki",
                dataset_key: "teryt_counties",
              },
            ],
            unresolved_areas: [],
          },
        },
      },
    });
    useAppStore.setState({ selection: { kind: "warning", id: "warningsmeteo:Sk1" }, mode: "simple" });

    renderWithClient();

    expect(await screen.findByText("Burze")).toBeInTheDocument();
    expect(screen.queryByText("Brak geometrii obszaru")).not.toBeInTheDocument();
    expect(screen.getByText("Geometria obszaru dostępna")).toBeInTheDocument();
  });

  it("shows a cache-empty notice instead of masking the error as no-data", async () => {
    mockFetchByPath({
      "/stations/hydro%3Amissing": {
        status: 503,
        body: { detail: { error: { code: "cache_empty", message: "Brak cache" } } },
      },
    });
    useAppStore.setState({ selection: { kind: "station", id: "hydro:missing" }, mode: "simple" });

    renderWithClient();

    expect(await screen.findByText("Brak danych w cache")).toBeInTheDocument();
  });

  it("closes the panel when the close button is clicked", async () => {
    mockFetchByPath({
      "/stations/hydro%3A151140030/observations": { status: 200, body: observationsResponse },
      "/stations/hydro%3A151140030": { status: 200, body: stationResponse },
    });
    useAppStore.setState({ selection: { kind: "station", id: "hydro:151140030" }, mode: "simple" });

    renderWithClient();
    await screen.findByText("Przewoźniki");

    screen.getByLabelText("Zamknij panel szczegółów").click();

    await waitFor(() => expect(useAppStore.getState().selection).toBeNull());
  });
});
