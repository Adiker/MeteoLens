import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, fetchStation } from "./client";

function mockResponse(status: number, body: unknown) {
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

describe("client error parsing", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("reads code/message from FastAPI detail.error", async () => {
    mockResponse(503, { detail: { error: { code: "cache_empty", message: "Brak cache" } } });
    await expect(fetchStation("synop:1")).rejects.toMatchObject({
      name: "ApiError",
      status: 503,
      code: "cache_empty",
      message: "Brak cache",
    });
  });

  it("falls back to top-level error and a default message", async () => {
    mockResponse(404, { error: { code: "not_found" } });
    const error = await fetchStation("synop:1").catch((err) => err);
    expect(error).toBeInstanceOf(ApiError);
    expect(error.code).toBe("not_found");
    expect(error.message).toContain("404");
  });
});
