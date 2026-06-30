import * as echarts from "echarts";
import { useEffect, useRef } from "react";

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
 * Bar chart of the latest numeric metric values for a station. The cached IMGW
 * payload is a single-timestamp snapshot, so this honestly shows current values
 * (missing/null metrics are excluded) rather than implying a time series.
 */
export function StationChart({ observations }: { observations: Observation[] }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  // Re-init when theme changes so axis/label colours follow the palette.
  const theme = useAppStore((state) => state.theme);

  const points = observations.filter((obs) => obs.value !== null && !obs.missing);

  useEffect(() => {
    const element = containerRef.current;
    if (!element || points.length === 0) {
      return;
    }

    let chart: echarts.ECharts;
    try {
      chart = echarts.init(element);
    } catch {
      return; // canvas unavailable (e.g. jsdom) — chart is optional UI.
    }

    const foreground = cssVarColor("--foreground", "#1f2937");
    const muted = cssVarColor("--muted-foreground", "#6b7280");
    const border = cssVarColor("--border", "#d1d5db");
    const primary = cssVarColor("--primary", "#0e7490");

    chart.setOption({
      grid: { left: 8, right: 16, top: 16, bottom: 8, containLabel: true },
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        formatter: (params: unknown) => {
          const [point] = params as Array<{ dataIndex: number }>;
          const obs = points[point.dataIndex];
          const unit = obs.unit ? ` ${obs.unit}` : "";
          return `${metricLabel(obs.metric)}<br/><b>${obs.value}${unit}</b>`;
        },
      },
      xAxis: {
        type: "value",
        axisLabel: { color: muted },
        splitLine: { lineStyle: { color: border } },
      },
      yAxis: {
        type: "category",
        data: points.map((obs) => metricLabel(obs.metric)),
        axisLabel: { color: foreground },
        axisLine: { lineStyle: { color: border } },
      },
      series: [
        {
          type: "bar",
          data: points.map((obs) => obs.value),
          itemStyle: { color: primary, borderRadius: [0, 3, 3, 0] },
          barMaxWidth: 18,
        },
      ],
    });

    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(element);
    return () => {
      observer.disconnect();
      chart.dispose();
    };
  }, [points, theme]);

  if (points.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">
        Brak wartości liczbowych do wykresu (wszystkie metryki są puste).
      </p>
    );
  }

  return <div ref={containerRef} className="h-56 w-full" aria-label="Wykres pomiarów stacji" />;
}
