import { renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useAppStore } from "../store/appStore";
import { FOCUS_SEARCH_EVENT, useKeyboardShortcuts } from "./useKeyboardShortcuts";

function fireKey(key: string, target: EventTarget = window, extra: Partial<KeyboardEventInit> = {}) {
  const event = new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true, ...extra });
  target.dispatchEvent(event);
}

describe("useKeyboardShortcuts", () => {
  beforeEach(() => {
    useAppStore.setState({
      shortcutHelpOpen: false,
      selection: null,
    });
    useAppStore.getState().setActiveLayers([
      "synop_stations",
      "hydro_stations",
      "meteo_stations",
      "warnings_meteo",
      "warnings_hydro",
    ]);
  });

  afterEach(() => {
    useAppStore.setState({ shortcutHelpOpen: false, selection: null });
  });

  it("toggles the shortcut help panel on '?'", () => {
    renderHook(() => useKeyboardShortcuts());

    fireKey("?");
    expect(useAppStore.getState().shortcutHelpOpen).toBe(true);
    fireKey("?");
    expect(useAppStore.getState().shortcutHelpOpen).toBe(false);
  });

  it("closes the help panel on Escape before clearing selection", () => {
    renderHook(() => useKeyboardShortcuts());
    useAppStore.setState({ shortcutHelpOpen: true, selection: { kind: "station", id: "hydro:1" } });

    fireKey("Escape");

    expect(useAppStore.getState().shortcutHelpOpen).toBe(false);
    expect(useAppStore.getState().selection).not.toBeNull();
  });

  it("clears the selection on Escape when help is already closed", () => {
    renderHook(() => useKeyboardShortcuts());
    useAppStore.setState({ shortcutHelpOpen: false, selection: { kind: "station", id: "hydro:1" } });

    fireKey("Escape");

    expect(useAppStore.getState().selection).toBeNull();
  });

  it("dispatches a focus-search event on '/'", () => {
    renderHook(() => useKeyboardShortcuts());
    const listener = vi.fn();
    window.addEventListener(FOCUS_SEARCH_EVENT, listener);

    fireKey("/");

    expect(listener).toHaveBeenCalledTimes(1);
    window.removeEventListener(FOCUS_SEARCH_EVENT, listener);
  });

  it("toggles the mapped layer on its number hotkey", () => {
    renderHook(() => useKeyboardShortcuts());
    const before = useAppStore.getState().activeLayers.synop_stations;

    fireKey("1");

    expect(useAppStore.getState().activeLayers.synop_stations).toBe(!before);
  });

  it("ignores shortcuts while typing in an input", () => {
    renderHook(() => useKeyboardShortcuts());
    const input = document.createElement("input");
    document.body.appendChild(input);
    const before = useAppStore.getState().activeLayers.synop_stations;

    fireKey("1", input);

    expect(useAppStore.getState().activeLayers.synop_stations).toBe(before);
    document.body.removeChild(input);
  });

  it("ignores shortcuts combined with modifier keys", () => {
    renderHook(() => useKeyboardShortcuts());
    const before = useAppStore.getState().activeLayers.synop_stations;

    fireKey("1", window, { metaKey: true });

    expect(useAppStore.getState().activeLayers.synop_stations).toBe(before);
  });
});
