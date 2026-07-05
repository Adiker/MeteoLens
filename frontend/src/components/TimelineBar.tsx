import { ChevronLeft, ChevronRight, Layers, Loader2, Pause, Play } from "lucide-react";
import { useEffect, useMemo } from "react";

import { formatTimestamp } from "../lib/format";
import { cn } from "../lib/utils";
import { useAppStore, type TimelineSpeed } from "../store/appStore";
import { useTimelineFrames } from "../hooks/useTimelineFrames";

const SPEED_OPTIONS: TimelineSpeed[] = [0.5, 1, 2, 4];

const RENDERING_STATUS_LABEL: Record<string, string> = {
  renderable: "warstwa renderowalna",
  parser_not_implemented: "tylko metadane",
  download_blocked: "pliki niedostępne publicznie u źródła",
  metadata_only: "tylko metadane",
  rendering_not_implemented: "render niezaimplementowany",
  unsupported_format: "format nieobsługiwany",
  unavailable: "produkt niedostępny",
};

const FRAME_REASON_LABEL: Record<string, string> = {
  constant_field_file: "plik pól stałych (bez renderu)",
  not_a_forecast_frame: "ramka bez prognozy (bez renderu)",
  lead_beyond_render_window: "poza oknem renderowania (tylko metadane)",
  lead_not_on_render_step: "poza krokiem renderowania (tylko metadane)",
};

export function TimelineBar() {
  const timeline = useAppStore((state) => state.timeline);
  const setTimelineLayer = useAppStore((state) => state.setTimelineLayer);
  const setTimelineFrameIndex = useAppStore((state) => state.setTimelineFrameIndex);
  const toggleTimelinePlaying = useAppStore((state) => state.toggleTimelinePlaying);
  const setTimelineSpeed = useAppStore((state) => state.setTimelineSpeed);
  const setTimelineFocused = useAppStore((state) => state.setTimelineFocused);
  const toggleTimelineOverlay = useAppStore((state) => state.toggleTimelineOverlay);

  const {
    layers,
    activeLayer,
    frameCount,
    clampedIndex,
    currentFrame,
    timelineLoading,
    framesLoading,
    framesStale,
    missingFrames,
    retrievedAt,
  } = useTimelineFrames();

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

  const renderableVariable = activeLayer?.renderable?.variables[0] ?? null;

  const statusLabel = useMemo(() => {
    if (timelineLoading) {
      return "Ładowanie osi czasu…";
    }
    if (layers.length === 0) {
      return null;
    }
    if (framesLoading) {
      return "Ładowanie ramek produktu…";
    }
    if (activeLayer && !activeLayer.frames_renderable) {
      return "Metadane ramek — renderowanie mapy niedostępne";
    }
    return null;
  }, [activeLayer, framesLoading, layers.length, timelineLoading]);

  if (layers.length === 0 && !timelineLoading) {
    return null;
  }

  const frameRenderLabel = (() => {
    if (!activeLayer?.frames_renderable || !currentFrame) {
      return null;
    }
    if (currentFrame.renderable) {
      return currentFrame.render_ready
        ? "Ramka wyrenderowana (cache)"
        : "Ramka renderowana na żądanie";
    }
    return (
      FRAME_REASON_LABEL[currentFrame.renderable_reason ?? ""] ??
      "Ramka nierenderowalna (tylko metadane)"
    );
  })();

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
                  {layer.frames_renderable ? " (render)" : ""}
                </option>
              ))}
            </select>
          ) : (
            <span className="text-xs text-foreground">{activeLayer?.title}</span>
          )}
          {activeLayer?.frames_renderable && (
            <button
              type="button"
              className={cn(
                "inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs",
                timeline.overlayEnabled
                  ? "bg-primary text-primary-foreground"
                  : "bg-background hover:bg-muted",
              )}
              aria-pressed={timeline.overlayEnabled}
              aria-label={
                timeline.overlayEnabled ? "Ukryj warstwę z mapy" : "Pokaż warstwę na mapie"
              }
              onClick={toggleTimelineOverlay}
            >
              <Layers aria-hidden className="size-3.5" />
              {timeline.overlayEnabled ? "Warstwa włączona" : "Pokaż na mapie"}
            </button>
          )}
          {statusLabel && (
            <span className="text-xs text-muted-foreground">{statusLabel}</span>
          )}
          {timeline.overlayError && (
            <span className="text-xs text-red-600" role="alert">
              {timeline.overlayError}
            </span>
          )}
          {(timelineLoading || framesLoading) && (
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
                    : currentFrame?.frame_kind === "constant"
                      ? "Pola stałe modelu"
                      : "Brak czasu ramki"}
                {currentFrame?.run_time && (
                  <span className="ml-1 text-muted-foreground">
                    (start: {formatTimestamp(currentFrame.run_time)})
                  </span>
                )}
              </dd>
            </div>
            <div>
              <dt className="uppercase">Czas źródła</dt>
              <dd className="text-foreground">
                {retrievedAt ? formatTimestamp(retrievedAt) : "—"}
              </dd>
            </div>
            <div>
              <dt className="uppercase">Ramki</dt>
              <dd className="text-foreground">
                {frameCount > 0 ? `${clampedIndex + 1} / ${frameCount}` : "Brak ramek"}
                {missingFrames ? (
                  <span className="ml-1 text-amber-600">({missingFrames} bez czasu)</span>
                ) : null}
              </dd>
            </div>
            <div>
              <dt className="uppercase">Status</dt>
              <dd className="text-foreground">
                {framesStale ? "Przestarzałe" : "Aktualne"}
                {" · "}
                {RENDERING_STATUS_LABEL[activeLayer.rendering_status] ??
                  activeLayer.rendering_status}
                {frameRenderLabel ? ` · ${frameRenderLabel}` : ""}
              </dd>
            </div>
          </dl>
        )}

        {activeLayer?.renderable && renderableVariable && (
          <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
            <span className="text-foreground">
              {renderableVariable.title} [{renderableVariable.unit}]
            </span>
            <span aria-hidden className="flex items-center overflow-hidden rounded-sm">
              {renderableVariable.legend.map((stop) => (
                <span
                  key={stop.value}
                  className="inline-block h-2.5 w-6"
                  style={{ backgroundColor: stop.color }}
                  title={`${stop.value} ${renderableVariable.unit}`}
                />
              ))}
            </span>
            <span>
              {renderableVariable.legend[0]?.value}–
              {renderableVariable.legend[renderableVariable.legend.length - 1]?.value}{" "}
              {renderableVariable.unit}
            </span>
          </div>
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
