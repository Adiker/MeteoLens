import { afterEach, describe, expect, it } from "vitest";

import { initialTheme, readStoredTheme, THEME_STORAGE_KEY } from "./theme";

describe("theme storage", () => {
  afterEach(() => window.localStorage.clear());

  it("reads a saved preference", () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, "dark");
    expect(readStoredTheme()).toBe("dark");
    expect(initialTheme()).toBe("dark");
  });

  it("falls back to system when unset or invalid", () => {
    expect(readStoredTheme()).toBeNull();
    expect(initialTheme()).toBe("system");
    window.localStorage.setItem(THEME_STORAGE_KEY, "neon");
    expect(readStoredTheme()).toBeNull();
    expect(initialTheme()).toBe("system");
  });
});
