import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { AttributionBar } from "../components/AttributionBar";
import { ControlPanel } from "../components/ControlPanel";
import { DetailsPanel } from "../components/DetailsPanel";
import { HeaderBar } from "../components/HeaderBar";
import { ShortcutHelp } from "../components/ShortcutHelp";
import { useKeyboardShortcuts } from "../hooks/useKeyboardShortcuts";
import { usePermalink } from "../hooks/usePermalink";
import { useTheme } from "../hooks/useTheme";
import { MapShell } from "../map/MapShell";

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false } },
});

function AppShell() {
  useTheme();
  usePermalink();
  useKeyboardShortcuts();

  return (
    <main className="grid h-screen grid-rows-[auto_1fr_auto] bg-background text-foreground">
      <HeaderBar />
      <section className="relative min-h-0 overflow-hidden">
        <MapShell />
        <ControlPanel />
        <DetailsPanel />
        <ShortcutHelp />
      </section>
      <AttributionBar />
    </main>
  );
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppShell />
    </QueryClientProvider>
  );
}
