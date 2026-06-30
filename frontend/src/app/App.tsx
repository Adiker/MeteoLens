import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { AttributionBar } from "../components/AttributionBar";
import { ControlPanel } from "../components/ControlPanel";
import { DetailsPanel } from "../components/DetailsPanel";
import { HeaderBar } from "../components/HeaderBar";
import { MapShell } from "../map/MapShell";

const queryClient = new QueryClient();

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <main className="grid h-screen grid-rows-[auto_1fr_auto] bg-background text-foreground">
        <HeaderBar />
        <section className="relative min-h-0 overflow-hidden">
          <MapShell />
          <ControlPanel />
          <DetailsPanel />
        </section>
        <AttributionBar />
      </main>
    </QueryClientProvider>
  );
}

