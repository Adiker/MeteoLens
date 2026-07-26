import * as echarts from "echarts";
import { useEffect, useMemo, useRef } from "react";

import type { Observation } from "../api/client";
import { metricLabel } from "../lib/format";
import { useAppStore } from "../store/appStore";

type SeriesOrigin = "live_refresh" | "archive_import" | "mixed";

const ORIGIN_LABEL: Record<SeriesOrigin, string> = {
  live_refresh: "Live IMGW",
  archive_import: "Archiwum IMGW",
  mixed: "Seria zagregowana",
};

function cssVarColor(name: string, fallback: string): string {
  if (typeof window === "undefined") {
    return fallback;
  }
  const raw = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return raw ? `hsl(${raw})` : fallback;
}

function observationOrigin(observation: Observation): SeriesOrigin {
  return observation.origin ?? "live_refresh";
}

function missingReasonLabel(reason: Observation["missing_reason"]): string {
  if (reason === "source_sentinel") {
    return "brak oznaczony sentinelem IMGW";
  }
  if (reason === "source_null") {
    return "brak NULL w źródle";
  }
  return "brak danych";
}

/**
 * Shows separate live/archive history series. Missing archive points remain
 * nulls, so ECharts renders honest gaps instead of joining across absent data.
 */
export function StationChart({
  observations,
  seriesKind = "snapshot",
}: {
  observations: Observation[];
  seriesKind?: "history" | "snapshot";
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const theme = useAppStore((state) => state.theme);
  const numeric = useMemo(
    () => observations.filter((obs) => obs.value !== null && !obs.missing),
    [observations],
  );

  const timeSeriesMetric = useMemo(() => {
    if (seriesKind !== "history") {
      return null;
    }
    const counts = new Map<string, number>();
    for (const observation of observations) {
      if (observation.observed_at) {
        counts.set(observation.metric, (counts.get(observation.metric) ?? 0) + 1);
      }
    }
    return [...counts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? null;
  }, [observations, seriesKind]);

  const timeSeriesPoints = useMemo(
    () =>
      timeSeriesMetric
        ? observations
            .filter(
              (observation) =>
                observation.metric === timeSeriesMetric && observation.observed_at,
            )
            .sort((a, b) =>
              String(a.observed_at).localeCompare(String(b.observed_at)),
            )
        : [],
    [observations, timeSeriesMetric],
  );

  const pointsByOrigin = useMemo(() => {
    const grouped = new Map<SeriesOrigin, Observation[]>();
    for (const observation of timeSeriesPoints) {
      const origin = observationOrigin(observation);
      grouped.set(origin, [...(grouped.get(origin) ?? []), observation]);
    }
    return grouped;
  }, [timeSeriesPoints]);

  const barPoints = useMemo(
    () => (timeSeriesPoints.length > 1 ? [] : numeric),
    [numeric, timeSeriesPoints.length],
  );

  useEffect(() => {
    const element = containerRef.current;
    const points = timeSeriesPoints.length > 1 ? timeSeriesPoints : barPoints;
    if (!element || points.length === 0) {
      return;
    }

    let chart: echarts.ECharts;
    try {
      chart = echarts.init(element);
    } catch {
      return;
    }

    const foreground = cssVarColor("--foreground", "#1f2937");
    const muted = cssVarColor("--muted-foreground", "#6b7280");
    const border = cssVarColor("--border", "#d1d5db");
    const primary = cssVarColor("--primary", "#0e7490");

    if (timeSeriesPoints.length > 1 && timeSeriesMetric) {
      const originColors: Record<SeriesOrigin, string> = {
        live_refresh: primary,
        archive_import: "#a16207",
        mixed: "#7c3aed",
      };
      const series = [...pointsByOrigin.entries()].map(([origin, originPoints]) => ({
        name: ORIGIN_LABEL[origin],
        type: "line" as const,
        connectNulls: false,
        showSymbol: true,
        symbolSize: 5,
        lineStyle: {
          type: origin === "archive_import" ? ("dashed" as const) : ("solid" as const),
        },
        itemStyle: { color: originColors[origin] },
        data: originPoints.map((observation) => ({
          value: [observation.observed_at, observation.value],
          metadata: {
            missing: observation.missing,
            missingReason: missingReasonLabel(observation.missing_reason),
            temporalResolution: observation.temporal_resolution,
            qualityStatus: observation.quality_status,
          },
        })),
      }));
      chart.setOption({
        grid: { left: 8, right: 16, top: 34, bottom: 24, containLabel: true },
        legend: {
          show: series.length > 1,
          data: series.map((item) => item.name),
          textStyle: { color: muted },
        },
        tooltip: {
          trigger: "axis",
          formatter: (rawParams: unknown) => {
            const params = Array.isArray(rawParams) ? rawParams : [rawParams];
            return params
              .map((rawParam) => {
                const param = rawParam as {
                  seriesName?: string;
                  data?: {
                    value?: [string, number | null];
                    metadata?: {
                      missingReason?: string;
                      temporalResolution?: string | null;
                      qualityStatus?: string | null;
                    };
                  };
                };
                const value = param.data?.value?.[1];
                const details = [
                  param.seriesName ?? "",
                  value === null || value === undefined
                    ? param.data?.metadata?.missingReason
                    : String(value),
                  param.data?.metadata?.temporalResolution
                    ? `rozdzielczość ${param.data.metadata.temporalResolution}`
                    : null,
                  param.data?.metadata?.qualityStatus
                    ? `jakość ${param.data.metadata.qualityStatus}`
                    : null,
                ].filter(Boolean);
                return details.join(" · ");
              })
              .join("<br/>");
          },
        },
        xAxis: {
          type: "time",
          axisLabel: { color: muted, hideOverlap: true },
        },
        yAxis: {
          type: "value",
          name: metricLabel(timeSeriesMetric),
          nameTextStyle: { color: muted },
          axisLabel: { color: muted },
          splitLine: { lineStyle: { color: border } },
        },
        series,
      });
    } else {
      chart.setOption({
        grid: { left: 8, right: 16, top: 16, bottom: 8, containLabel: true },
        tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
        xAxis: {
          type: "value",
          axisLabel: { color: muted },
          splitLine: { lineStyle: { color: border } },
        },
        yAxis: {
          type: "category",
          data: barPoints.map((observation) => metricLabel(observation.metric)),
          axisLabel: { color: foreground },
          axisLine: { lineStyle: { color: border } },
        },
        series: [
          {
            type: "bar",
            data: barPoints.map((observation) => observation.value),
            itemStyle: { color: primary, borderRadius: [0, 3, 3, 0] },
            barMaxWidth: 18,
          },
        ],
      });
    }

    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(element);
    return () => {
      observer.disconnect();
      chart.dispose();
    };
  }, [barPoints, pointsByOrigin, theme, timeSeriesMetric, timeSeriesPoints]);

  if (numeric.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">
        Brak wartości liczbowych do wykresu (wszystkie metryki są puste).
      </p>
    );
  }

  if (seriesKind === "history" && numeric.length <= 1) {
    return (
      <div className="space-y-2">
        <p className="text-xs text-muted-foreground">
          Historia jest zapisywana, ale ta stacja ma jeszcze tylko jeden punkt czasowy.
          Kolejne odświeżenia IMGW zbudują serię wielopunktową.
        </p>
        <div ref={containerRef} className="h-56 w-full" aria-label="Wykres pomiarów stacji" />
      </div>
    );
  }

  return <div ref={containerRef} className="h-56 w-full" aria-label="Wykres pomiarów stacji" />;
}
