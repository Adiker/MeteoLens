import type { WarningChangeKind } from "../api/client";

/** Human-readable labels for normalized metric keys. Falls back to the raw key. */
const METRIC_LABELS: Record<string, string> = {
  temperature: "Temperatura",
  air_temperature: "Temperatura powietrza",
  ground_temperature: "Temperatura przy gruncie",
  temperature_ground: "Temperatura przy gruncie",
  water_temperature: "Temperatura wody",
  wind_speed: "Prędkość wiatru",
  wind_average_speed: "Średnia prędkość wiatru",
  wind_max_speed: "Maksymalna prędkość wiatru",
  wind_direction: "Kierunek wiatru",
  wind_gust: "Porywy wiatru",
  wind_gust_10min: "Poryw wiatru (10 min)",
  relative_humidity: "Wilgotność względna",
  humidity: "Wilgotność",
  pressure: "Ciśnienie",
  precipitation_sum: "Suma opadu",
  precipitation: "Opad",
  precipitation_10min: "Opad (10 min)",
  water_level: "Stan wody",
  flow: "Przepływ",
  snow_depth: "Pokrywa śnieżna",
};

export function metricLabel(metric: string): string {
  return METRIC_LABELS[metric] ?? metric.replace(/_/g, " ");
}

const PL = "pl-PL";

// IMGW data is published in Polish local time; pin the display timezone (with a
// label) so viewers outside Poland see the source validity window, not a shift.
const SOURCE_TIMEZONE = "Europe/Warsaw";

const DATE_ONLY = /^(\d{4})-(\d{2})-(\d{2})$/;

export function isDateOnly(value: string): boolean {
  const match = DATE_ONLY.exec(value);
  if (!match) {
    return false;
  }
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const candidate = new Date(Date.UTC(year, month - 1, day));
  return (
    candidate.getUTCFullYear() === year &&
    candidate.getUTCMonth() === month - 1 &&
    candidate.getUTCDate() === day
  );
}

function sourceDateBoundary(value: string, dayOffset: number): number | null {
  if (!isDateOnly(value)) {
    return null;
  }
  const [year, month, day] = value.split("-").map(Number);
  const desiredLocalAsUtc = Date.UTC(year, month - 1, day + dayOffset);
  let instant = desiredLocalAsUtc;
  const formatter = new Intl.DateTimeFormat("en-CA", {
    timeZone: SOURCE_TIMEZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  });
  for (let iteration = 0; iteration < 2; iteration += 1) {
    const parts = Object.fromEntries(
      formatter
        .formatToParts(new Date(instant))
        .filter((part) => part.type !== "literal")
        .map((part) => [part.type, Number(part.value)]),
    );
    const representedLocalAsUtc = Date.UTC(
      parts.year,
      parts.month - 1,
      parts.day,
      parts.hour,
      parts.minute,
      parts.second,
    );
    instant += desiredLocalAsUtc - representedLocalAsUtc;
  }
  return instant;
}

export function sourceDateStart(value: string): string | undefined {
  const instant = sourceDateBoundary(value, 0);
  return instant === null ? undefined : new Date(instant).toISOString();
}

export function sourceDateEnd(value: string): string | undefined {
  const nextMidnight = sourceDateBoundary(value, 1);
  return nextMidnight === null ? undefined : new Date(nextMidnight - 1).toISOString();
}

export function formatTimestamp(iso: string | null | undefined): string {
  if (!iso) {
    return "—";
  }
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  return new Intl.DateTimeFormat(PL, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: SOURCE_TIMEZONE,
    timeZoneName: "short",
  }).format(date);
}

/** Format a data delay in seconds as a compact human string. */
export function formatDelay(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) {
    return "—";
  }
  if (seconds < 60) {
    return `${seconds} s`;
  }
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) {
    return `${minutes} min`;
  }
  const hours = Math.floor(minutes / 60);
  const restMinutes = minutes % 60;
  if (hours < 24) {
    return restMinutes ? `${hours} h ${restMinutes} min` : `${hours} h`;
  }
  const days = Math.floor(hours / 24);
  const restHours = hours % 24;
  return restHours ? `${days} d ${restHours} h` : `${days} d`;
}

export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }
  return new Intl.NumberFormat(PL, { maximumFractionDigits: 2 }).format(value);
}

/** Format a measurement value with its unit; missing values stay explicit. */
export function formatValue(value: number | null | undefined, unit: string | null | undefined): string {
  if (value === null || value === undefined) {
    return "brak danych";
  }
  return unit ? `${formatNumber(value)} ${unit}` : formatNumber(value);
}

const WARNING_LEVEL_LABEL: Record<number, string> = {
  [-1]: "−1 — susza hydrologiczna",
  1: "1 — żółty",
  2: "2 — pomarańczowy",
  3: "3 — czerwony",
};

export function warningLevelLabel(level: number | null | undefined): string {
  if (level === null || level === undefined) {
    return "—";
  }
  return WARNING_LEVEL_LABEL[level] ?? String(level);
}

const WARNING_CHANGE_LABELS: Record<WarningChangeKind, string> = {
  first_observed: "Pierwsza obserwacja",
  created: "Wydano",
  appeared_in_source: "Pojawiło się w źródle",
  updated: "Zaktualizowano",
  extended: "Rozszerzono",
  escalated: "Podniesiono stopień",
  downgraded: "Obniżono stopień",
  expired: "Wygasło",
  removed_from_source: "Zniknęło ze źródła",
  reappeared: "Pojawiło się ponownie",
  cancelled: "Odwołano",
  correction: "Korekta źródłowa",
  duplicate_conflict: "Konflikt duplikatów",
};

export function warningChangeKindLabel(kind: WarningChangeKind): string {
  return WARNING_CHANGE_LABELS[kind];
}

export const WARNING_LEVEL_COLOR: Record<number, string> = {
  [-1]: "#8b5cf6",
  1: "#eab308",
  2: "#f97316",
  3: "#dc2626",
};

const CACHE_STATUS_LABEL: Record<string, string> = {
  fresh: "aktualny",
  stale: "nieaktualny",
  empty: "brak danych",
  error: "błąd źródła",
  invalid: "uszkodzony cache",
};

export function cacheStatusLabel(status: string): string {
  return CACHE_STATUS_LABEL[status] ?? status;
}
