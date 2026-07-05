import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useAppStore } from "../store/appStore";
import { TimelineBar } from "./TimelineBar";

const timelinePayload = {
  generated_at: "2026-07-01T10:00:00Z",
  layers: [
    {
      key: "product:COMPO_SRI.comp.sri",
      product_id: "COMPO_SRI.comp.sri",
      title: "COMPO_SRI.comp.sri",
      kind: "product_frames",
      category: "radar_composite",
      rendering_status: "parser_not_implemented",
      frame_count: 2,
      missing_frames: 0,
      frames_renderable: false,
      source_time: "2026-06-30T08:00:00Z",
      first_frame_time: "2026-06-28T03:30:00+00:00",
      last_frame_time: "2026-06-28T04:30:00+00:00",
      stale: false,
      attribution: "Źródło danych: IMGW-PIB.",
      processed_notice: "Dane przetworzone.",
      notes: ["Frame timestamps are parsed from public manifest filenames only."],
    },
  ],
  empty_state: null,
};

function framesPayload(offset = 0, limit = 500, frameCount = 2) {
  const frames = Array.from(
    { length: Math.min(limit, Math.max(frameCount - offset, 0)) },
    (_item, itemIndex) => {
      const index = offset + itemIndex;
      return {
        index,
        file: `202606280${index.toString().padStart(3, "0")}0000dBR.sri`,
        url: `https://example.test/frame-${index}`,
        frame_time: `2026-06-28T${String(3 + (index % 12)).padStart(2, "0")}:30:00+00:00`,
        frame_kind: "observation",
        rendering_status: "parser_not_implemented",
        missing: false,
      };
    },
  );
  return {
  generated_at: "2026-07-01T10:00:00Z",
  product_id: "COMPO_SRI.comp.sri",
  description: "COMPO_SRI.comp.sri",
  category: "radar_composite",
  availability: "stable_retrievable",
  rendering_status: "parser_not_implemented",
  format_notes: "Proprietary SRI composite binary.",
  research_date: "2026-07-01",
  source: {
    provider: "IMGW-PIB",
    source_key: "product",
    url: "https://danepubliczne.imgw.pl/api/data/product/id/COMPO_SRI.comp.sri",
    retrieved_at: "2026-06-30T08:00:00Z",
    attribution: "Źródło danych: IMGW-PIB.",
    processed_notice: "Dane przetworzone.",
  },
  retrieved_at: "2026-06-30T08:00:00Z",
  frames,
  frame_count: frameCount,
  limit,
  offset,
  missing_frames: 0,
  stale: false,
  attribution: "Źródło danych: IMGW-PIB.",
  processed_notice: "Dane przetworzone.",
  empty_state: null,
  };
}

const renderableDescriptor = {
  variables: [
    {
      key: "t2m",
      title: "Temperatura powietrza 2 m (COSMO)",
      unit: "°C",
      legend: [
        { value: -30, color: "#3c0078" },
        { value: 40, color: "#c8141e" },
      ],
    },
  ],
  default_variable: "t2m",
  bounds: [10.963, 46.597, 28.376, 57.695],
  image_coordinates: [
    [10.963, 57.695],
    [28.376, 57.695],
    [28.376, 46.597],
    [10.963, 46.597],
  ],
  render_url_template: "/api/v1/products/COSMO_HVD_00_00/render/{file}?variable={variable}",
  max_lead_hours: 24,
  lead_step_hours: 3,
  grid_note: "COSMO rotated grid",
  attribution: "Źródło danych: IMGW-PIB.",
  processed_notice: "Dane przetworzone.",
};

const renderableTimelinePayload = {
  generated_at: "2026-07-05T10:00:00Z",
  layers: [
    {
      key: "product:COSMO_HVD_00_00",
      product_id: "COSMO_HVD_00_00",
      title: "Prognoza meteo GRIB model COSMO 2k8 00/00",
      kind: "product_frames",
      category: "grib_model",
      rendering_status: "renderable",
      frame_count: 2,
      missing_frames: 0,
      frames_renderable: true,
      renderable: renderableDescriptor,
      source_time: "2026-07-05T08:00:00Z",
      first_frame_time: "2026-07-04T00:00:00+00:00",
      last_frame_time: "2026-07-04T03:00:00+00:00",
      stale: false,
      attribution: "Źródło danych: IMGW-PIB.",
      processed_notice: "Dane przetworzone.",
      notes: [],
    },
  ],
  empty_state: null,
};

const cosmoFramesPayload = {
  generated_at: "2026-07-05T10:00:00Z",
  product_id: "COSMO_HVD_00_00",
  description: "Prognoza meteo GRIB model COSMO 2k8 00/00",
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
      render_ready: false,
    },
    {
      index: 1,
      file: "202607040000_202607040100_lfff00010000",
      url: "https://x/1",
      frame_time: "2026-07-04T01:00:00+00:00",
      run_time: "2026-07-04T00:00:00+00:00",
      frame_kind: "forecast_lead",
      rendering_status: "renderable",
      missing: false,
      renderable: false,
      renderable_reason: "lead_not_on_render_step",
    },
  ],
  frame_count: 2,
  limit: 500,
  offset: 0,
  missing_frames: 0,
  stale: false,
  renderable: renderableDescriptor,
  attribution: "Źródło danych: IMGW-PIB.",
  processed_notice: "Dane przetworzone.",
  empty_state: null,
};

let currentTimelinePayload = timelinePayload;
let requestedUrls: string[] = [];

function renderTimelineBar() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <TimelineBar />
    </QueryClientProvider>,
  );
}

describe("TimelineBar", () => {
  beforeEach(() => {
    currentTimelinePayload = timelinePayload;
    requestedUrls = [];
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo) => {
        const url = String(input);
        requestedUrls.push(url);
        if (url.includes("/api/v1/map/timeline")) {
          return Promise.resolve(new Response(JSON.stringify(currentTimelinePayload)));
        }
        if (url.includes("/api/v1/products/COMPO_SRI.comp.sri/frames")) {
          const parsed = new URL(url, "http://localhost");
          const offset = Number(parsed.searchParams.get("offset") ?? "0");
          const limit = Number(parsed.searchParams.get("limit") ?? "500");
          const frameCount = currentTimelinePayload.layers[0].frame_count;
          return Promise.resolve(
            new Response(JSON.stringify(framesPayload(offset, limit, frameCount))),
          );
        }
        if (url.includes("/api/v1/products/COSMO_HVD_00_00/frames")) {
          return Promise.resolve(new Response(JSON.stringify(cosmoFramesPayload)));
        }
        return Promise.reject(new Error(`unexpected fetch ${url}`));
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    useAppStore.setState({
      timeline: {
        activeLayerKey: null,
        frameIndex: 0,
        playing: false,
        speed: 1,
        focused: false,
        overlayEnabled: false,
        overlayError: null,
      },
    });
  });

  it("shows product timeline controls when backend exposes layers", async () => {
    renderTimelineBar();
    expect(await screen.findByTestId("timeline-bar")).toBeInTheDocument();
    expect(
      await screen.findByText("Metadane ramek — renderowanie mapy niedostępne"),
    ).toBeInTheDocument();
    expect(await screen.findByText("1 / 2")).toBeInTheDocument();
  });

  it("steps frames with next button", async () => {
    const user = userEvent.setup();
    renderTimelineBar();
    await screen.findByTestId("timeline-bar");
    await screen.findByText("1 / 2");
    await user.click(await screen.findByLabelText("Następna ramka"));
    expect(await screen.findByText("2 / 2")).toBeInTheDocument();
  });

  it("offers the map overlay toggle and legend for a renderable layer", async () => {
    const user = userEvent.setup();
    currentTimelinePayload = renderableTimelinePayload;
    renderTimelineBar();

    await screen.findByTestId("timeline-bar");
    expect(await screen.findByText(/warstwa renderowalna/)).toBeInTheDocument();
    expect(
      await screen.findByText("Temperatura powietrza 2 m (COSMO) [°C]"),
    ).toBeInTheDocument();
    expect(await screen.findByText(/Ramka renderowana na żądanie/)).toBeInTheDocument();

    const toggle = await screen.findByLabelText("Pokaż warstwę na mapie");
    expect(useAppStore.getState().timeline.overlayEnabled).toBe(false);
    await user.click(toggle);
    expect(useAppStore.getState().timeline.overlayEnabled).toBe(true);
    expect(await screen.findByLabelText("Ukryj warstwę z mapy")).toBeInTheDocument();
  });

  it("labels frames outside the render window as metadata-only", async () => {
    const user = userEvent.setup();
    currentTimelinePayload = renderableTimelinePayload;
    renderTimelineBar();

    await screen.findByText("1 / 2");
    await user.click(await screen.findByLabelText("Następna ramka"));
    expect(
      await screen.findByText(/poza krokiem renderowania \(tylko metadane\)/),
    ).toBeInTheDocument();
  });

  it("keeps the metadata-only label for non-renderable layers", async () => {
    renderTimelineBar();
    await screen.findByTestId("timeline-bar");
    expect(
      await screen.findByText("Metadane ramek — renderowanie mapy niedostępne"),
    ).toBeInTheDocument();
    expect(screen.queryByLabelText("Pokaż warstwę na mapie")).not.toBeInTheDocument();
  });

  it("fetches the page containing the selected global frame index", async () => {
    currentTimelinePayload = {
      ...timelinePayload,
      layers: [{ ...timelinePayload.layers[0], frame_count: 600 }],
    };
    useAppStore.setState({
      timeline: {
        activeLayerKey: "product:COMPO_SRI.comp.sri",
        frameIndex: 501,
        playing: false,
        speed: 1,
        focused: false,
        overlayEnabled: false,
        overlayError: null,
      },
    });

    renderTimelineBar();

    expect(await screen.findByText("502 / 600")).toBeInTheDocument();
    expect(
      requestedUrls.some((url) =>
        url.includes("/api/v1/products/COMPO_SRI.comp.sri/frames?limit=500&offset=500"),
      ),
    ).toBe(true);
  });
});
