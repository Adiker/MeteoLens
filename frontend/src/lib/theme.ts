import type { ThemePreference } from "../store/appStore";

export const THEME_STORAGE_KEY = "meteolens.theme";

/** Last persisted theme preference, or null if none/unavailable. */
export function readStoredTheme(): ThemePreference | null {
  try {
    const value = window.localStorage.getItem(THEME_STORAGE_KEY);
    if (value === "light" || value === "dark" || value === "system") {
      return value;
    }
  } catch {
    // localStorage may be unavailable (private mode); ignore.
  }
  return null;
}

export function persistTheme(theme: ThemePreference): void {
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    // ignore persistence failures
  }
}

export function resolveDark(theme: ThemePreference): boolean {
  if (theme === "system") {
    return typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: dark)").matches;
  }
  return theme === "dark";
}

/** Initial theme for the store: saved preference wins, else system. */
export function initialTheme(): ThemePreference {
  return readStoredTheme() ?? "system";
}
