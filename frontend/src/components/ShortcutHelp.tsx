import { X } from "lucide-react";

import { LAYERS } from "../lib/layers";
import { useAppStore } from "../store/appStore";

const SHORTCUTS: Array<{ keys: string; description: string }> = [
  { keys: "/", description: "Przejdź do wyszukiwarki" },
  { keys: "Esc", description: "Zamknij panel / wyczyść zaznaczenie" },
  { keys: "?", description: "Otwórz/zamknij tę pomoc" },
  ...LAYERS.map((layer) => ({ keys: layer.hotkey, description: `Przełącz: ${layer.title}` })),
];

export function ShortcutHelp() {
  const open = useAppStore((state) => state.shortcutHelpOpen);
  const setOpen = useAppStore((state) => state.setShortcutHelpOpen);

  if (!open) {
    return null;
  }

  return (
    <div
      className="absolute inset-0 z-40 flex items-center justify-center bg-black/40 p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Skróty klawiszowe"
      onClick={() => setOpen(false)}
    >
      <div
        className="w-full max-w-sm rounded-lg border border-border bg-card p-4 text-card-foreground shadow-xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold">Skróty klawiszowe</h2>
          <button
            type="button"
            className="inline-flex size-8 items-center justify-center rounded-md border border-border bg-background text-muted-foreground hover:text-foreground"
            aria-label="Zamknij"
            onClick={() => setOpen(false)}
          >
            <X aria-hidden className="size-4" />
          </button>
        </div>
        <dl className="space-y-2 text-sm">
          {SHORTCUTS.map((shortcut) => (
            <div key={shortcut.keys} className="flex items-center justify-between gap-3">
              <dt className="text-muted-foreground">{shortcut.description}</dt>
              <dd>
                <kbd className="rounded border border-border bg-background px-2 py-0.5 text-xs">
                  {shortcut.keys}
                </kbd>
              </dd>
            </div>
          ))}
        </dl>
        <p className="mt-3 text-[11px] text-muted-foreground">
          Skróty nie działają, gdy kursor znajduje się w polu tekstowym.
        </p>
      </div>
    </div>
  );
}
