import "@testing-library/jest-dom/vitest";

import { vi } from "vitest";

// jsdom's localStorage support depends on the Node/jsdom version combination
// (observed missing under Node 26); the theme store hydrates from it at
// creation time, so tests need a reliable in-memory stand-in.
if (!window.localStorage) {
  class MemoryStorage implements Storage {
    #store = new Map<string, string>();

    get length(): number {
      return this.#store.size;
    }

    clear(): void {
      this.#store.clear();
    }

    getItem(key: string): string | null {
      return this.#store.has(key) ? this.#store.get(key)! : null;
    }

    key(index: number): string | null {
      return Array.from(this.#store.keys())[index] ?? null;
    }

    removeItem(key: string): void {
      this.#store.delete(key);
    }

    setItem(key: string, value: string): void {
      this.#store.set(key, String(value));
    }
  }

  Object.defineProperty(window, "localStorage", { value: new MemoryStorage() });
}

// jsdom lacks matchMedia; the theme hook depends on it.
if (!window.matchMedia) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

// jsdom lacks ResizeObserver; the chart component uses it.
if (!globalThis.ResizeObserver) {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}
