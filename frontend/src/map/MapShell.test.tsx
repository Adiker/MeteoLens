import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CAPTURE_PNG_EVENT } from "../lib/mapBus";

class FakeMap {
  addControl = vi.fn();
  addSource = vi.fn();
  addLayer = vi.fn();
  getSource = vi.fn();
  getLayer = vi.fn();
  setFilter = vi.fn();
  flyTo = vi.fn();
  on = vi.fn();
  remove = vi.fn();
  getCanvas = vi.fn(() => ({ width: 800, height: 600, style: {} }) as unknown as HTMLCanvasElement);
  getCenter = vi.fn(() => ({ lng: 19, lat: 52 }));
  getZoom = vi.fn(() => 5.4);
}

vi.mock("maplibre-gl", () => ({
  default: {
    Map: FakeMap,
    NavigationControl: class {},
    AttributionControl: class {},
  },
}));

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

describe("MapShell PNG export", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new Error("no backend"))),
    );
  });

  it("embeds the IMGW-PIB attribution caption in the exported PNG canvas", async () => {
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
    window.dispatchEvent(new Event(CAPTURE_PNG_EVENT));

    expect(fillText).toHaveBeenCalledTimes(1);
    const [text] = fillText.mock.calls[0];
    expect(text).toContain("Źródło danych: IMGW-PIB.");
    expect(text).toContain("Dane przetworzone przez MeteoLens");
  });
});
