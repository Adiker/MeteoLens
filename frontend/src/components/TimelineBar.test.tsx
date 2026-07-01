import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

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

const framesPayload = {
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
  frames: [
    {
      index: 0,
      file: "2026062803300000dBR.sri",
      url: "https://example.test/frame-0",
      frame_time: "2026-06-28T03:30:00+00:00",
      frame_kind: "observation",
      rendering_status: "parser_not_implemented",
      missing: false,
    },
    {
      index: 1,
      file: "2026062804300000dBR.sri",
      url: "https://example.test/frame-1",
      frame_time: "2026-06-28T04:30:00+00:00",
      frame_kind: "observation",
      rendering_status: "parser_not_implemented",
      missing: false,
    },
  ],
  frame_count: 2,
  limit: 500,
  offset: 0,
  missing_frames: 0,
  stale: false,
  attribution: "Źródło danych: IMGW-PIB.",
  processed_notice: "Dane przetworzone.",
  empty_state: null,
};

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
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo) => {
        const url = String(input);
        if (url.includes("/api/v1/map/timeline")) {
          return Promise.resolve(new Response(JSON.stringify(timelinePayload)));
        }
        if (url.includes("/api/v1/products/COMPO_SRI.comp.sri/frames")) {
          return Promise.resolve(new Response(JSON.stringify(framesPayload)));
        }
        return Promise.reject(new Error(`unexpected fetch ${url}`));
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
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
});
