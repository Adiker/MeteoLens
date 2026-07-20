import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useAppStore } from "../store/appStore";
import { ControlPanel } from "./ControlPanel";

const initialState = useAppStore.getState();

type JsonByPath = Record<string, unknown>;

function stubFetch(byPath: JsonByPath) {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const url = String(input);
    const match = Object.entries(byPath).find(([path]) => url.includes(path));
    if (!match) {
      return Promise.reject(new Error(`no stub for ${url}`));
    }
    return Promise.resolve({
      ok: true,
      status: 200,
      json: () => Promise.resolve(match[1]),
    } as Response);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function warningRecord(overrides: Record<string, unknown> = {}) {
  return {
    id: "warningsmeteo:w1",
    source_id: "w1",
    source_key: "warningsmeteo",
    warning_type: "meteo",
    event: "Burze z gradem",
    level: 2,
    probability: 80,
    valid_from: "2026-07-04T00:00:00Z",
    valid_to: "2026-07-05T00:00:00Z",
    published_at: "2026-07-04T00:00:00Z",
    office: "CBPM",
    content: "Prognozowane są burze.",
    comment: null,
    areas: [{ area_type: "teryt", code: "1205", label: null, region: null }],
    area_codes: ["1205"],
    missing_fields: [],
    geometry_status: "resolved",
    resolved_areas: [],
    unresolved_areas: [],
    raw_available: true,
    source: {
      provider: "IMGW-PIB",
      source_key: "warningsmeteo",
      url: "https://danepubliczne.imgw.pl/api/data/warningsmeteo",
      retrieved_at: "2026-07-04T00:00:00Z",
      attribution: "Źródło danych: IMGW-PIB.",
      processed_notice: "Dane IMGW-PIB zostały przetworzone przez MeteoLens.",
    },
    ...overrides,
  };
}

function mapLayersResponse(features: unknown[], missingGeometry: unknown[]) {
  return {
    generated_at: "2026-07-04T00:00:00Z",
    cache: [],
    empty_state: null,
    layers: [
      {
        key: "warnings_meteo",
        title: "Ostrzeżenia meteorologiczne",
        source_keys: ["warningsmeteo"],
        sources: [],
        geojson: { type: "FeatureCollection", features },
        records: [warningRecord()],
        missing_geometry: missingGeometry,
      },
    ],
  };
}

const polygonFeature = {
  type: "Feature",
  id: "warningsmeteo:w1:1205",
  properties: {
    warning_id: "warningsmeteo:w1",
    warning_type: "meteo",
    event: "Burze z gradem",
    level: 2,
    area_type: "teryt",
    code: "1205",
    label: "powiat myślenicki",
    dataset_key: "teryt_counties",
    geometry_status: "resolved",
  },
  geometry: {
    type: "Polygon",
    coordinates: [
      [
        [19.0, 49.7],
        [20.2, 49.7],
        [20.2, 50.1],
        [19.0, 50.1],
        [19.0, 49.7],
      ],
    ],
  },
};

function renderPanel() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <ControlPanel />
    </QueryClientProvider>,
  );
}

describe("ControlPanel warnings geometry states", () => {
  beforeEach(() => {
    useAppStore.setState(initialState, true);
    useAppStore.getState().setActiveLayers(["warnings_meteo"]);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    useAppStore.setState(initialState, true);
  });

  it("shows polygon counts when warning geometry exists", async () => {
    stubFetch({
      "/api/v1/map/layers": mapLayersResponse([polygonFeature], []),
      "/api/v1/warnings": { warnings: [warningRecord()], empty_state: null },
      "/api/v1/sources": { sources: [] },
    });

    renderPanel();

    expect(await screen.findByText(/1 poligonów · 0 bez geometrii/)).toBeInTheDocument();
  });

  it("shows hydro basin polygon counts on the hydro warning layer", async () => {
    useAppStore.getState().setActiveLayers(["warnings_hydro"]);
    const hydroFeature = {
      ...polygonFeature,
      id: "warningshydro:h1:Z_P_WP_1856",
      properties: {
        ...polygonFeature.properties,
        warning_id: "warningshydro:h1",
        warning_type: "hydro",
        event: "Susza hydrologiczna",
        area_type: "basin",
        code: "Z_P_WP_1856",
        label: "Kanał Mosiński",
        dataset_key: "hydro_basins",
      },
    };
    stubFetch({
      "/api/v1/map/layers": {
        generated_at: "2026-07-04T00:00:00Z",
        cache: [],
        empty_state: null,
        layers: [
          {
            key: "warnings_hydro",
            title: "Ostrzeżenia hydrologiczne",
            source_keys: ["warningshydro"],
            sources: [],
            geojson: { type: "FeatureCollection", features: [hydroFeature] },
            records: [
              warningRecord({
                id: "warningshydro:h1",
                source_key: "warningshydro",
                warning_type: "hydro",
                event: "Susza hydrologiczna",
                areas: [{ area_type: "basin", code: "Z_P_WP_1856", label: null, region: null }],
                area_codes: ["Z_P_WP_1856"],
              }),
            ],
            missing_geometry: [],
          },
        ],
      },
      "/api/v1/warnings": {
        warnings: [
          warningRecord({
            id: "warningshydro:h1",
            source_key: "warningshydro",
            warning_type: "hydro",
            event: "Susza hydrologiczna",
            area_codes: ["Z_P_WP_1856"],
          }),
        ],
        empty_state: null,
      },
      "/api/v1/sources": { sources: [] },
    });

    renderPanel();

    expect(await screen.findByText(/1 poligonów · 0 bez geometrii/)).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /Susza hydrologiczna/ })).toBeInTheDocument();
  });

  it("falls back to the list-only state when geometry is missing", async () => {
    stubFetch({
      "/api/v1/map/layers": mapLayersResponse(
        [],
        [
          {
            id: "warningsmeteo:w1",
            source_key: "warningsmeteo",
            reason: "geometry_not_found",
            area_type: "teryt",
            area_codes: ["1205"],
          },
        ],
      ),
      "/api/v1/warnings": {
        warnings: [warningRecord({ geometry_status: "missing_area_geometry_dataset" })],
        empty_state: null,
      },
      "/api/v1/sources": { sources: [] },
    });

    renderPanel();

    // No polygons on the map, but the warning stays visible in the list.
    expect(await screen.findByText(/0 poligonów · 1 bez geometrii/)).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /Burze z gradem/ })).toBeInTheDocument();
  });

  it("passes province, county, and basin filters to the warnings API", async () => {
    const fetchMock = stubFetch({
      "/api/v1/map/layers": mapLayersResponse([polygonFeature], []),
      "/api/v1/warnings": { warnings: [warningRecord()], empty_state: null },
      "/api/v1/sources": { sources: [] },
    });

    renderPanel();

    fireEvent.change(screen.getByLabelText(/Województwo \(TERYT\)/), {
      target: { value: "12" },
    });
    fireEvent.change(screen.getByLabelText(/Powiat \(TERYT\)/), {
      target: { value: "1205" },
    });
    fireEvent.change(screen.getByLabelText(/Zlewnia/), {
      target: { value: "Z_P_WP_1856" },
    });

    await waitFor(() => {
      const warningCalls = fetchMock.mock.calls
        .map((call) => String(call[0]))
        .filter((url) => url.includes("/api/v1/warnings?"));
      const last = warningCalls[warningCalls.length - 1] ?? "";
      expect(last).toContain("province=12");
      expect(last).toContain("county=1205");
      expect(last).toContain("basin=Z_P_WP_1856");
    });
  });
});
