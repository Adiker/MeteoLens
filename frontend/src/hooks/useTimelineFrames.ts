import { useEffect, useMemo } from "react";

import type { ProductFrame, TimelineLayer } from "../api/client";
import { useMapTimelineQuery, useProductFramesQuery } from "../api/queries";
import { useAppStore } from "../store/appStore";

export const FRAME_PAGE_SIZE = 500;

export interface TimelineFrames {
  layers: TimelineLayer[];
  activeLayer: TimelineLayer | null;
  frames: ProductFrame[];
  frameCount: number;
  clampedIndex: number;
  currentFrame: ProductFrame | null;
  timelineLoading: boolean;
  framesLoading: boolean;
  framesStale: boolean;
  missingFrames: number;
  retrievedAt: string | null;
}

/**
 * Shared timeline state: active layer, paged frames, and the current frame.
 * Used by both the timeline bar (controls) and the map shell (overlay), which
 * must agree on the exact same frame selection.
 */
export function useTimelineFrames(): TimelineFrames {
  const timeline = useAppStore((state) => state.timeline);
  const setTimelineLayer = useAppStore((state) => state.setTimelineLayer);
  const setTimelineFrameIndex = useAppStore((state) => state.setTimelineFrameIndex);

  const timelineQuery = useMapTimelineQuery();
  const layers = useMemo(() => timelineQuery.data?.layers ?? [], [timelineQuery.data?.layers]);
  const activeLayer =
    layers.find((layer) => layer.key === timeline.activeLayerKey) ?? layers[0] ?? null;

  useEffect(() => {
    if (layers.length === 0) {
      if (!timelineQuery.isLoading && timeline.activeLayerKey) {
        setTimelineLayer(null);
      }
      return;
    }
    if (!timeline.activeLayerKey || !layers.some((layer) => layer.key === timeline.activeLayerKey)) {
      setTimelineLayer(layers[0].key);
    }
  }, [layers, setTimelineLayer, timeline.activeLayerKey, timelineQuery.isLoading]);

  const provisionalFrameCount = activeLayer?.frame_count ?? 0;
  const provisionalClampedIndex = Math.min(
    timeline.frameIndex,
    Math.max(provisionalFrameCount - 1, 0),
  );
  const framePageOffset = Math.floor(provisionalClampedIndex / FRAME_PAGE_SIZE) * FRAME_PAGE_SIZE;
  const framesQuery = useProductFramesQuery(
    activeLayer?.product_id ?? null,
    FRAME_PAGE_SIZE,
    framePageOffset,
  );
  const frames = framesQuery.data?.frames ?? [];
  const frameCount = framesQuery.data?.frame_count ?? provisionalFrameCount;
  const clampedIndex = Math.min(timeline.frameIndex, Math.max(frameCount - 1, 0));
  const currentPageOffset = framesQuery.data?.offset ?? framePageOffset;
  const currentFrame = frames[clampedIndex - currentPageOffset] ?? null;

  useEffect(() => {
    if (activeLayer && frameCount > 0 && clampedIndex !== timeline.frameIndex) {
      setTimelineFrameIndex(clampedIndex);
    }
  }, [activeLayer, clampedIndex, frameCount, setTimelineFrameIndex, timeline.frameIndex]);

  return {
    layers,
    activeLayer,
    frames,
    frameCount,
    clampedIndex,
    currentFrame,
    timelineLoading: timelineQuery.isLoading,
    framesLoading: framesQuery.isLoading,
    framesStale: Boolean(activeLayer?.stale || framesQuery.data?.stale),
    missingFrames: framesQuery.data?.missing_frames ?? 0,
    retrievedAt: framesQuery.data?.retrieved_at ?? activeLayer?.source_time ?? null,
  };
}
