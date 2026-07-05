import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CAPTURE_PNG_EVENT } from "../lib/mapBus";
import { useAppStore } from "../store/appStore";

const mapMocks = vi.hoisted(() => ({
  instances: [] as Array<{
    fire: (event: string) => void;
    sourceData: Map<string, unknown[]>;
    updateImageCalls: Array<{ id: string; options: unknown }>;
  }>,
}));

vi.mock("maplibre-gl", () => {
  class FakeMap {
    handlers: Record<string, Array<(...args: unknown[]) => void>> = {};
    sourceData = new Map<string, unknown[]>();
    updateImageCalls: Array<{ id: string; options: unknown }> = [];
    constructor() {
      mapMocks.instances.push(this as unknown as (typeof mapMocks.instances)[number]);
    }
    fire = (event: string) => {
      for (const handler of this.handlers[event] ?? []) {
        handler();
      }
    };
    on = vi.fn((event: string, layerOrCb: unknown, maybeCb?: unknown) => {
      const callback = typeof layerOrCb === "function" ? layerOrCb : maybeCb;
      if (typeof callback === "function") {
        (this.handlers[event] ??= []).push(callback as (...args: unknown[]) => void);
      }
    });
    addControl = vi.fn();
    addSource = vi.fn();
    addLayer = vi.fn();
    getSource = vi.fn((id: string) => ({
      setData: (data: { features?: unknown[] }) => {
        this.sourceData.set(id, data.features ?? []);
      },
      updateImage: (options: unknown) => {
        this.updateImageCalls.push({ id, options });
      },
    }));
    getLayer = vi.fn(() => ({}));
    setLayoutProperty = vi.fn();
    setFilter = vi.fn();
    flyTo = vi.fn();
    remove = vi.fn();
    getCanvas = vi.fn(
      () => ({ width: 800, height: 600, style: {} }) as unknown as HTMLCanvasElement,
    );
    getCenter = vi.fn(() => ({ lng: 19, lat: 52 }));
    getZoom = vi.fn(() => 5.4);
  }
  return {
    default: {
      Map: FakeMap,
      NavigationControl: class {},
      AttributionControl: class {},
    },
  };
});

async function renderMapShell() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
  });
  const { MapShell } = await import("./MapShell");
  return render(
    <QueryClientProvider client={client}>
      <MapShell />
    </QueryClientProvider>,
  );
}

const initialStoreState = useAppStore.getState();

describe("MapShell", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new Error("no backend"))),
    );
    useAppStore.setState(initialStoreState, true);
    mapMocks.instances.length = 0;
  });

  it("embeds the data attribution caption in the exported PNG canvas", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/v1/geometry/datasets")) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () =>
            Promise.resolve({
              generated_at: "2026-07-04T00:00:00Z",
              manifest_present: true,
              datasets: [
                {
                  key: "teryt_counties",
                  title: "Powiaty",
                  source: "PRG",
                  license_note: "Reviewed",
                  attribution: "Granice administracyjne: Państwowy Rejestr Granic (PRG), © GUGiK.",
                  loaded: true,
                  feature_count: 380,
                  error: null,
                },
              ],
            }),
        } as Response);
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ sources: [], layers: [] }),
      } as Response);
    });
    vi.stubGlobal("fetch", fetchMock);
    // Legal requirement: PNG exports must carry visible attribution (see
    // LEGAL_ATTRIBUTION.md "Where Attribution Must Appear"). jsdom has no real
    // canvas backing, so stub the 2D context to capture what MapShell draws.
    const fillText = vi.fn();
    const fakeCtx = {
      drawImage: vi.fn(),
      fillRect: vi.fn(),
      fillText,
      font: "",
      fillStyle: "",
      textBaseline: "",
    };
    const fakeCanvas = {
      width: 0,
      height: 0,
      getContext: () => fakeCtx,
      toDataURL: () => "data:image/png;base64,",
    };
    // A real <a> element with a data: href triggers jsdom's unimplemented
    // navigation path on click(); stub it out too since we only care about
    // the drawn caption here, not the download mechanics.
    const fakeAnchor = { href: "", download: "", click: vi.fn() };
    const realCreateElement = document.createElement.bind(document);
    vi.spyOn(document, "createElement").mockImplementation((tag: string) => {
      if (tag === "canvas") {
        return fakeCanvas as unknown as HTMLCanvasElement;
      }
      if (tag === "a") {
        return fakeAnchor as unknown as HTMLAnchorElement;
      }
      return realCreateElement(tag);
    });

    await renderMapShell();
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/api/v1/geometry/datasets")),
    );
    await waitFor(() => {
      fillText.mockClear();
      window.dispatchEvent(new Event(CAPTURE_PNG_EVENT));
      expect(fillText).toHaveBeenCalledTimes(2);
    });

    const text = fillText.mock.calls.map((call) => String(call[0])).join(" ");
    expect(text).toContain("Źródło danych: IMGW-PIB.");
    expect(text).toContain("Dane przetworzone przez MeteoLens");
    expect(text).toContain("Państwowy Rejestr Granic");
  });

  it("pushes warning polygons into the warnings map source when geometry exists", async () => {
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
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        const payload = url.includes("/api/v1/map/layers")
          ? {
              generated_at: "2026-07-04T00:00:00Z",
              cache: [],
              empty_state: null,
              layers: [
                {
                  key: "warnings_meteo",
                  title: "Ostrzeżenia meteorologiczne",
                  source_keys: ["warningsmeteo"],
                  sources: [],
                  geojson: { type: "FeatureCollection", features: [polygonFeature] },
                  records: [],
                  missing_geometry: [],
                },
              ],
            }
          : { sources: [] };
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve(payload),
        } as Response);
      }),
    );
    useAppStore.getState().setActiveLayers(["warnings_meteo"]);

    await renderMapShell();
    const fakeMap = mapMocks.instances[mapMocks.instances.length - 1];
    expect(fakeMap).toBeDefined();
    fakeMap!.fire("load");

    await waitFor(() => {
      const features = (fakeMap!.sourceData.get("warnings") ?? []) as Array<{ id?: string }>;
      expect(features.map((feature) => feature.id)).toEqual(["warningsmeteo:w1:1205"]);
    });
  });

  it("keeps the warnings map source empty in the list-only fallback state", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        const payload = url.includes("/api/v1/map/layers")
          ? {
              generated_at: "2026-07-04T00:00:00Z",
              cache: [],
              empty_state: null,
              layers: [
                {
                  key: "warnings_meteo",
                  title: "Ostrzeżenia meteorologiczne",
                  source_keys: ["warningsmeteo"],
                  sources: [],
                  geojson: { type: "FeatureCollection", features: [] },
                  records: [{ id: "warningsmeteo:w1" }],
                  missing_geometry: [
                    {
                      id: "warningsmeteo:w1",
                      source_key: "warningsmeteo",
                      reason: "geometry_not_found",
                      area_type: "teryt",
                      area_codes: ["1205"],
                    },
                  ],
                },
              ],
            }
          : { sources: [] };
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve(payload),
        } as Response);
      }),
    );
    useAppStore.getState().setActiveLayers(["warnings_meteo"]);

    await renderMapShell();
    const fakeMap = mapMocks.instances[mapMocks.instances.length - 1];
    fakeMap!.fire("load");

    // The warnings source stays empty and the fill layer is hidden; the warning
    // itself is only presented in the ControlPanel list (see ControlPanel tests).
    await waitFor(() => {
      const setLayoutProperty = (
        fakeMap as unknown as { setLayoutProperty: ReturnType<typeof vi.fn> }
      ).setLayoutProperty;
      expect(setLayoutProperty).toHaveBeenCalledWith("warnings-fill", "visibility", "none");
      expect(fakeMap!.sourceData.get("warnings") ?? []).toEqual([]);
    });
  });

  it("draws the rendered product frame as a map image overlay when enabled", async () => {
    const renderableTimeline = {
      generated_at: "2026-07-05T10:00:00Z",
      empty_state: null,
      layers: [
        {
          key: "product:COSMO_HVD_00_00",
          product_id: "COSMO_HVD_00_00",
          title: "COSMO 00/00",
          kind: "product_frames",
          category: "grib_model",
          rendering_status: "renderable",
          frame_count: 1,
          missing_frames: 0,
          frames_renderable: true,
          renderable: {
            variables: [{ key: "t2m", title: "Temperatura 2 m", unit: "°C", legend: [] }],
            default_variable: "t2m",
            bounds: [10.963, 46.597, 28.376, 57.695],
            image_coordinates: [
              [10.963, 57.695],
              [28.376, 57.695],
              [28.376, 46.597],
              [10.963, 46.597],
            ],
            render_url_template:
              "/api/v1/products/COSMO_HVD_00_00/render/{file}?variable={variable}",
            max_lead_hours: 24,
            lead_step_hours: 3,
            grid_note: "",
            attribution: "Źródło danych: IMGW-PIB.",
            processed_notice: "Dane przetworzone.",
          },
          source_time: "2026-07-05T08:00:00Z",
          first_frame_time: "2026-07-04T00:00:00+00:00",
          last_frame_time: "2026-07-04T00:00:00+00:00",
          stale: false,
          attribution: "Źródło danych: IMGW-PIB.",
          processed_notice: "Dane przetworzone.",
          notes: [],
        },
      ],
    };
    const framesPayload = {
      generated_at: "2026-07-05T10:00:00Z",
      product_id: "COSMO_HVD_00_00",
      description: "COSMO 00/00",
      category: "grib_model",
      availability: "stable_retrievable",
      rendering_status: "renderable",
      format_notes: "GRIB1",
      research_date: "2026-07-05",
      source: {
        provider: "IMGW-PIB",
        source_key: "product",
        url: "https://danepubliczne.imgw.pl/api/data/product/id/COSMO_HVD_00_00",
        retrieved_at: "2026-07-05T08:00:00Z",
        attribution: "Źródło danych: IMGW-PIB.",
        processed_notice: "Dane przetworzone.",
      },
      retrieved_at: "2026-07-05T08:00:00Z",
      frames: [
        {
          index: 0,
          file: "202607040000_202607040000_lfff00000000",
          url: "https://x/0",
          frame_time: "2026-07-04T00:00:00+00:00",
          run_time: "2026-07-04T00:00:00+00:00",
          frame_kind: "forecast_lead",
          rendering_status: "renderable",
          missing: false,
          renderable: true,
          renderable_reason: null,
          render_url:
            "/api/v1/products/COSMO_HVD_00_00/render/202607040000_202607040000_lfff00000000?variable=t2m",
          render_ready: true,
        },
      ],
      frame_count: 1,
      limit: 500,
      offset: 0,
      missing_frames: 0,
      stale: false,
      renderable: renderableTimeline.layers[0].renderable,
      attribution: "Źródło danych: IMGW-PIB.",
      processed_notice: "Dane przetworzone.",
      empty_state: null,
    };
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        const payload = url.includes("/api/v1/map/timeline")
          ? renderableTimeline
          : url.includes("/api/v1/products/COSMO_HVD_00_00/frames")
            ? framesPayload
            : { sources: [], layers: [] };
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve(payload),
        } as Response);
      }),
    );
    useAppStore.setState({
      timeline: {
        activeLayerKey: "product:COSMO_HVD_00_00",
        frameIndex: 0,
        playing: false,
        speed: 1,
        focused: false,
        overlayEnabled: true,
        overlayError: null,
      },
    });

    await renderMapShell();
    const fakeMap = mapMocks.instances[mapMocks.instances.length - 1];
    fakeMap!.fire("load");

    await waitFor(() => {
      const calls = fakeMap!.updateImageCalls.filter((call) => call.id === "product-render");
      expect(calls.length).toBeGreaterThan(0);
      const options = calls[calls.length - 1].options as {
        url: string;
        coordinates: number[][];
      };
      expect(options.url).toContain(
        "/api/v1/products/COSMO_HVD_00_00/render/202607040000_202607040000_lfff00000000",
      );
      expect(options.coordinates[0]).toEqual([10.963, 57.695]);
    });
  });

  it("filters station features above the expert delay threshold", async () => {
    const { filterStationFeaturesByDelay } = await import("./stationFilters");
    const fresh = {
      id: "fresh",
      properties: { data_delay_seconds: 30 * 60 },
    };
    const delayed = {
      id: "delayed",
      properties: { data_delay_seconds: 120 * 60 },
    };
    const unknown = {
      id: "unknown",
      properties: { data_delay_seconds: null },
    };

    const features = [fresh, delayed, unknown] as Parameters<typeof filterStationFeaturesByDelay>[0];

    expect(filterStationFeaturesByDelay(features, 60).map((feature) => feature.id)).toEqual([
      "fresh",
      "unknown",
    ]);
  });

  it("filters station features to stale-cache sources when the expert toggle is on", async () => {
    const { filterStationFeaturesByStaleCache } = await import("./stationFilters");
    const synop = { id: "synop-1", properties: { source_key: "synop" } };
    const hydro = { id: "hydro-1", properties: { source_key: "hydro" } };
    const features = [synop, hydro] as Parameters<typeof filterStationFeaturesByStaleCache>[0];

    expect(filterStationFeaturesByStaleCache(features, false, ["synop"])).toEqual(features);
    expect(
      filterStationFeaturesByStaleCache(features, true, ["synop"]).map((feature) => feature.id),
    ).toEqual(["synop-1"]);
  });
});
