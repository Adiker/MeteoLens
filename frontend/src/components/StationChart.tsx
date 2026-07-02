import * as echarts from "echarts";
import { useEffect, useMemo, useRef } from "react";

import type { Observation } from "../api/client";
import { metricLabel } from "../lib/format";
import { useAppStore } from "../store/appStore";

function cssVarColor(name: string, fallback: string): string {
  if (typeof window === "undefined") {
    return fallback;
  }
  const raw = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return raw ? `hsl(${raw})` : fallback;
}

/**
 * Shows a time-series line chart when historical points exist; otherwise a bar
 * chart of the latest numeric metrics from the current snapshot.
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

  const numeric = observations.filter((obs) => obs.value !== null && !obs.missing);
  const timeSeriesMetric = useMemo(() => {
    if (seriesKind !== "history") {
      return null;
    }
    const counts = new Map<string, number>();
    for (const obs of numeric) {
      if (!obs.observed_at) {
        continue;
      }
      counts.set(obs.metric, (counts.get(obs.metric) ?? 0) + 1);
    }
    const ranked = [...counts.entries()].sort((a, b) => b[1] - a[1]);
    return ranked.find(([, count]) => count > 1)?.[0] ?? ranked[0]?.[0] ?? null;
  }, [numeric, seriesKind]);

  const timeSeriesPoints = useMemo(
    () =>
      timeSeriesMetric
        ? numeric
            .filter((obs) => obs.metric === timeSeriesMetric && obs.observed_at)
            .sort((a, b) => String(a.observed_at).localeCompare(String(b.observed_at)))
        : [],
    [numeric, timeSeriesMetric],
  );

  const barPoints = useMemo(() => {
    if (timeSeriesPoints.length > 1) {
      return [];
    }
    return numeric;
  }, [numeric, timeSeriesPoints.length]);

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
      chart.setOption({
        grid: { left: 8, right: 16, top: 16, bottom: 24, containLabel: true },
        tooltip: { trigger: "axis" },
        xAxis: {
          type: "category",
          data: timeSeriesPoints.map((obs) => obs.observed_at ?? ""),
          axisLabel: { color: muted, hideOverlap: true },
        },
        yAxis: {
          type: "value",
          axisLabel: { color: muted },
          splitLine: { lineStyle: { color: border } },
        },
        series: [
          {
            type: "line",
            data: timeSeriesPoints.map((obs) => obs.value),
            smooth: true,
            itemStyle: { color: primary },
          },
        ],
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
          data: barPoints.map((obs) => metricLabel(obs.metric)),
          axisLabel: { color: foreground },
          axisLine: { lineStyle: { color: border } },
        },
        series: [
          {
            type: "bar",
            data: barPoints.map((obs) => obs.value),
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
  }, [barPoints, theme, timeSeriesMetric, timeSeriesPoints]);

  if (numeric.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">
        Brak wartości liczbowych do wykresu (wszystkie metryki są puste).
      </p>
    );
  }

  if (seriesKind === "history" && timeSeriesPoints.length <= 1) {
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
