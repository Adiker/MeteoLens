import { useEffect } from "react";

import { persistTheme, resolveDark } from "../lib/theme";
import { useAppStore } from "../store/appStore";

/** Reflects the store theme preference onto <html> and persists it. */
export function useTheme(): void {
  const theme = useAppStore((state) => state.theme);

  useEffect(() => {
    const apply = () => {
      document.documentElement.classList.toggle("dark", resolveDark(theme));
    };
    apply();
    persistTheme(theme);

    if (theme !== "system") {
      return;
    }
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, [theme]);
}
