/** Human-readable labels for normalized metric keys. Falls back to the raw key. */
const METRIC_LABELS: Record<string, string> = {
  temperature: "Temperatura",
  temperature_ground: "Temperatura przy gruncie",
  water_temperature: "Temperatura wody",
  wind_speed: "Prędkość wiatru",
  wind_direction: "Kierunek wiatru",
  wind_gust: "Porywy wiatru",
  relative_humidity: "Wilgotność względna",
  humidity: "Wilgotność",
  pressure: "Ciśnienie",
  precipitation_sum: "Suma opadu",
  precipitation: "Opad",
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

export const WARNING_LEVEL_COLOR: Record<number, string> = {
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
