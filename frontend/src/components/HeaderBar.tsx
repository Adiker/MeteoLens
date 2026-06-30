import { Crosshair, Keyboard, Monitor, Moon, PanelLeft, SunMedium, Telescope } from "lucide-react";
import { useState } from "react";

import { flyTo } from "../lib/mapBus";
import { cn } from "../lib/utils";
import { useAppStore, type ThemePreference } from "../store/appStore";
import { ExportMenu } from "./ExportMenu";
import { SearchBox } from "./SearchBox";
import { iconButtonClass } from "./primitives";

const THEME_ICON: Record<ThemePreference, typeof Monitor> = {
  system: Monitor,
  light: SunMedium,
  dark: Moon,
};
const THEME_LABEL: Record<ThemePreference, string> = {
  system: "Motyw: systemowy",
  light: "Motyw: jasny",
  dark: "Motyw: ciemny",
};

export function HeaderBar() {
  const theme = useAppStore((state) => state.theme);
  const cycleTheme = useAppStore((state) => state.cycleTheme);
  const mode = useAppStore((state) => state.mode);
  const toggleMode = useAppStore((state) => state.toggleMode);
  const toggleControlPanel = useAppStore((state) => state.toggleControlPanel);
  const setShortcutHelpOpen = useAppStore((state) => state.setShortcutHelpOpen);
  const setUserLocation = useAppStore((state) => state.setUserLocation);
  const [locating, setLocating] = useState(false);
  const ThemeIcon = THEME_ICON[theme];

  const onLocate = () => {
    if (!("geolocation" in navigator)) {
      window.alert("Przeglądarka nie udostępnia lokalizacji.");
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const { latitude, longitude } = position.coords;
        setUserLocation({ lat: latitude, lon: longitude });
        flyTo({ lng: longitude, lat: latitude, zoom: 9 });
        setLocating(false);
      },
      () => {
        setLocating(false);
        window.alert("Nie udało się ustalić lokalizacji.");
      },
      { enableHighAccuracy: false, timeout: 10_000 },
    );
  };

  return (
    <header className="flex min-h-14 items-center gap-3 border-b border-border bg-card px-3 sm:px-4">
      <button
        type="button"
        className={cn(iconButtonClass, "lg:hidden")}
        aria-label="Pokaż/ukryj panel warstw"
        onClick={toggleControlPanel}
      >
        <PanelLeft aria-hidden className="size-4" />
      </button>

      <div className="hidden sm:block">
        <h1 className="text-base font-semibold leading-none">MeteoLens</h1>
        <p className="text-xs text-muted-foreground">Panel pogodowo-hydrologiczny IMGW-PIB</p>
      </div>

      <div className="flex min-w-0 flex-1 justify-center">
        <SearchBox />
      </div>

      <div className="flex items-center gap-2">
        <button
          type="button"
          className={iconButtonClass}
          aria-label="Pokaż dane dla mojej lokalizacji"
          aria-busy={locating}
          onClick={onLocate}
        >
          <Crosshair aria-hidden className={cn("size-4", locating && "animate-pulse")} />
        </button>
        <ExportMenu />
        <button
          type="button"
          className={cn(iconButtonClass, mode === "expert" && "border-primary text-primary")}
          aria-label="Przełącz tryb prosty/ekspercki"
          aria-pressed={mode === "expert"}
          title={mode === "expert" ? "Tryb ekspercki" : "Tryb prosty"}
          onClick={toggleMode}
        >
          <Telescope aria-hidden className="size-4" />
        </button>
        <button
          type="button"
          className={iconButtonClass}
          aria-label={THEME_LABEL[theme]}
          title={THEME_LABEL[theme]}
          onClick={cycleTheme}
        >
          <ThemeIcon aria-hidden className="size-4" />
        </button>
        <button
          type="button"
          className={cn(iconButtonClass, "hidden sm:inline-flex")}
          aria-label="Skróty klawiszowe"
          onClick={() => setShortcutHelpOpen(true)}
        >
          <Keyboard aria-hidden className="size-4" />
        </button>
      </div>
    </header>
  );
}
