import { useEffect } from "react";

import { LAYERS } from "../lib/layers";
import { useAppStore } from "../store/appStore";

export const FOCUS_SEARCH_EVENT = "meteolens:focus-search";

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  const tag = target.tagName;
  return (
    tag === "INPUT" ||
    tag === "TEXTAREA" ||
    tag === "SELECT" ||
    target.isContentEditable
  );
}

const LAYER_BY_HOTKEY = new Map(LAYERS.map((layer) => [layer.hotkey, layer.key]));

/** Global keyboard shortcuts. Never hijacks text inputs. */
export function useKeyboardShortcuts(): void {
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const store = useAppStore.getState();

      // Escape works everywhere: close help, then clear selection.
      if (event.key === "Escape") {
        if (store.shortcutHelpOpen) {
          store.setShortcutHelpOpen(false);
        } else if (store.selection) {
          store.clearSelection();
        }
        return;
      }

      if (isTypingTarget(event.target) || event.metaKey || event.ctrlKey || event.altKey) {
        return;
      }

      if (event.key === "/") {
        event.preventDefault();
        window.dispatchEvent(new CustomEvent(FOCUS_SEARCH_EVENT));
        return;
      }

      if (event.key === "?") {
        event.preventDefault();
        store.setShortcutHelpOpen(!store.shortcutHelpOpen);
        return;
      }

      const layerKey = LAYER_BY_HOTKEY.get(event.key);
      if (layerKey) {
        event.preventDefault();
        store.toggleLayer(layerKey);
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);
}
