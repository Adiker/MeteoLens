import { useEffect } from "react";

import { useAppStore, type ThemePreference } from "../store/appStore";

const STORAGE_KEY = "meteolens.theme";

export function readStoredTheme(): ThemePreference | null {
  try {
    const value = window.localStorage.getItem(STORAGE_KEY);
    if (value === "light" || value === "dark" || value === "system") {
      return value;
    }
  } catch {
    // localStorage may be unavailable (private mode); ignore.
  }
  return null;
}

function resolveDark(theme: ThemePreference): boolean {
  if (theme === "system") {
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  }
  return theme === "dark";
}

/** Reflects the store theme preference onto <html> and persists it. */
export function useTheme(): void {
  const theme = useAppStore((state) => state.theme);

  useEffect(() => {
    const apply = () => {
      document.documentElement.classList.toggle("dark", resolveDark(theme));
    };
    apply();

    try {
      window.localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      // ignore persistence failures
    }

    if (theme !== "system") {
      return;
    }
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, [theme]);
}
