import { ChevronLeft, ChevronRight, Loader2, Pause, Play } from "lucide-react";
import { useEffect, useMemo } from "react";

import { useMapTimelineQuery, useProductFramesQuery } from "../api/queries";
import { formatTimestamp } from "../lib/format";
import { cn } from "../lib/utils";
import { useAppStore, type TimelineSpeed } from "../store/appStore";

const SPEED_OPTIONS: TimelineSpeed[] = [0.5, 1, 2, 4];

export function TimelineBar() {
  const timeline = useAppStore((state) => state.timeline);
  const setTimelineLayer = useAppStore((state) => state.setTimelineLayer);
  const setTimelineFrameIndex = useAppStore((state) => state.setTimelineFrameIndex);
  const toggleTimelinePlaying = useAppStore((state) => state.toggleTimelinePlaying);
  const setTimelineSpeed = useAppStore((state) => state.setTimelineSpeed);
  const setTimelineFocused = useAppStore((state) => state.setTimelineFocused);

  const timelineQuery = useMapTimelineQuery();
  const layers = useMemo(() => timelineQuery.data?.layers ?? [], [timelineQuery.data?.layers]);
  const activeLayer =
    layers.find((layer) => layer.key === timeline.activeLayerKey) ?? layers[0] ?? null;

  useEffect(() => {
    if (layers.length === 0) {
      if (timeline.activeLayerKey) {
        setTimelineLayer(null);
      }
      return;
    }
    if (!timeline.activeLayerKey || !layers.some((layer) => layer.key === timeline.activeLayerKey)) {
      setTimelineLayer(layers[0].key);
    }
  }, [layers, setTimelineLayer, timeline.activeLayerKey]);

  const framesQuery = useProductFramesQuery(activeLayer?.product_id ?? null);
  const frames = framesQuery.data?.frames ?? [];
  const frameCount = framesQuery.data?.frame_count ?? 0;
  const clampedIndex = Math.min(timeline.frameIndex, Math.max(frameCount - 1, 0));
  const currentFrame = frames[clampedIndex] ?? null;

  useEffect(() => {
    if (clampedIndex !== timeline.frameIndex) {
      setTimelineFrameIndex(clampedIndex);
    }
  }, [clampedIndex, setTimelineFrameIndex, timeline.frameIndex]);

  useEffect(() => {
    if (!timeline.playing || frameCount <= 1) {
      return;
    }
    const intervalMs = 1000 / timeline.speed;
    const timer = window.setInterval(() => {
      const store = useAppStore.getState();
      const next = store.timeline.frameIndex + 1;
      if (next >= frameCount) {
        store.setTimelinePlaying(false);
        store.setTimelineFrameIndex(Math.max(frameCount - 1, 0));
        return;
      }
      store.setTimelineFrameIndex(next);
    }, intervalMs);
    return () => window.clearInterval(timer);
  }, [frameCount, timeline.playing, timeline.speed]);

  const statusLabel = useMemo(() => {
    if (timelineQuery.isLoading) {
      return "Ładowanie osi czasu…";
    }
    if (layers.length === 0) {
      return null;
    }
    if (framesQuery.isLoading) {
      return "Ładowanie ramek produktu…";
    }
    if (activeLayer && !activeLayer.frames_renderable) {
      return "Metadane ramek — renderowanie mapy niedostępne";
    }
    return null;
  }, [activeLayer, framesQuery.isLoading, layers.length, timelineQuery.isLoading]);

  if (layers.length === 0 && !timelineQuery.isLoading) {
    return null;
  }

  return (
    <section
      className="border-t border-border bg-card/95 px-3 py-2 text-card-foreground backdrop-blur"
      aria-label="Oś czasu produktów"
      data-testid="timeline-bar"
      tabIndex={0}
      onFocus={() => setTimelineFocused(true)}
      onBlur={() => setTimelineFocused(false)}
    >
      <div className="mx-auto flex max-w-6xl flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Oś czasu
          </p>
          {layers.length > 1 ? (
            <select
              className="rounded-md border border-border bg-background px-2 py-1 text-xs"
              value={activeLayer?.key ?? ""}
              onChange={(event) => setTimelineLayer(event.target.value || null)}
              aria-label="Warstwa osi czasu"
            >
              {layers.map((layer) => (
                <option key={layer.key} value={layer.key}>
                  {layer.title}
                </option>
              ))}
            </select>
          ) : (
            <span className="text-xs text-foreground">{activeLayer?.title}</span>
          )}
          {statusLabel && (
            <span className="text-xs text-muted-foreground">{statusLabel}</span>
          )}
          {(timelineQuery.isLoading || framesQuery.isLoading) && (
            <Loader2 aria-hidden className="size-3.5 animate-spin text-muted-foreground" />
          )}
        </div>

        {activeLayer && (
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              className="inline-flex size-8 items-center justify-center rounded-md border border-border bg-background hover:bg-muted"
              aria-label={timeline.playing ? "Pauza" : "Odtwórz"}
              onClick={toggleTimelinePlaying}
              disabled={frameCount <= 1}
            >
              {timeline.playing ? (
                <Pause aria-hidden className="size-4" />
              ) : (
                <Play aria-hidden className="size-4" />
              )}
            </button>
            <button
              type="button"
              className="inline-flex size-8 items-center justify-center rounded-md border border-border bg-background hover:bg-muted"
              aria-label="Poprzednia ramka"
              onClick={() => setTimelineFrameIndex(clampedIndex - 1)}
              disabled={clampedIndex <= 0}
            >
              <ChevronLeft aria-hidden className="size-4" />
            </button>
            <button
              type="button"
              className="inline-flex size-8 items-center justify-center rounded-md border border-border bg-background hover:bg-muted"
              aria-label="Następna ramka"
              onClick={() => setTimelineFrameIndex(clampedIndex + 1)}
              disabled={frameCount === 0 || clampedIndex >= frameCount - 1}
            >
              <ChevronRight aria-hidden className="size-4" />
            </button>

            <input
              type="range"
              min={0}
              max={Math.max(frameCount - 1, 0)}
              value={clampedIndex}
              onChange={(event) => setTimelineFrameIndex(Number(event.target.value))}
              className="min-w-32 flex-1"
              aria-label="Pozycja ramki"
              disabled={frameCount <= 1}
            />

            <label className="flex items-center gap-1 text-xs text-muted-foreground">
              Prędkość
              <select
                className="rounded-md border border-border bg-background px-2 py-1 text-xs text-foreground"
                value={timeline.speed}
                onChange={(event) => setTimelineSpeed(Number(event.target.value) as TimelineSpeed)}
              >
                {SPEED_OPTIONS.map((speed) => (
                  <option key={speed} value={speed}>
                    {speed}x
                  </option>
                ))}
              </select>
            </label>
          </div>
        )}

        {activeLayer && (
          <dl className="grid gap-1 text-[11px] text-muted-foreground sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <dt className="uppercase">Czas ramki</dt>
              <dd className={cn("text-foreground", currentFrame?.missing && "text-amber-600")}>
                {currentFrame?.frame_time
                  ? formatTimestamp(currentFrame.frame_time)
                  : currentFrame?.frame_kind === "metadata"
                    ? "Metadane (readme)"
                    : "Brak czasu ramki"}
              </dd>
            </div>
            <div>
              <dt className="uppercase">Czas źródła</dt>
              <dd className="text-foreground">
                {framesQuery.data?.retrieved_at
                  ? formatTimestamp(framesQuery.data.retrieved_at)
                  : activeLayer.source_time
                    ? formatTimestamp(activeLayer.source_time)
                    : "—"}
              </dd>
            </div>
            <div>
              <dt className="uppercase">Ramki</dt>
              <dd className="text-foreground">
                {frameCount > 0 ? `${clampedIndex + 1} / ${frameCount}` : "Brak ramek"}
                {framesQuery.data?.missing_frames ? (
                  <span className="ml-1 text-amber-600">
                    ({framesQuery.data.missing_frames} bez czasu)
                  </span>
                ) : null}
              </dd>
            </div>
            <div>
              <dt className="uppercase">Status</dt>
              <dd className="text-foreground">
                {activeLayer.stale || framesQuery.data?.stale ? "Przestarzałe" : "Aktualne"}
                {" · "}
                {activeLayer.rendering_status === "parser_not_implemented"
                  ? "tylko metadane"
                  : activeLayer.rendering_status}
              </dd>
            </div>
          </dl>
        )}

        {activeLayer && (
          <p className="text-[11px] text-muted-foreground">
            {activeLayer.processed_notice} {activeLayer.attribution}
          </p>
        )}
      </div>
    </section>
  );
}
