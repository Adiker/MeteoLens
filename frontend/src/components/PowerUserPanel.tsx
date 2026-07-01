import {
  AlertTriangle,
  Bookmark,
  Gauge,
  MapPinned,
  Save,
  Trash2,
  X,
} from "lucide-react";
import { useMemo, useState } from "react";

import {
  useFreshnessQuery,
  useLocationSummaryQuery,
  useSourcesQuery,
  useWarningComparisonQuery,
} from "../api/queries";
import { evaluateAlertRule, staleSourceKeys } from "../lib/alertRules";
import { flyTo } from "../lib/mapBus";
import { formatTimestamp, formatValue } from "../lib/format";
import { activeLayerKeys, useAppStore } from "../store/appStore";
import {
  ALERTING_DISCLAIMER,
  createId,
  type AlertRule,
  type AlertRuleType,
} from "../lib/userData";
import { cn } from "../lib/utils";
import { Spinner, StateNotice } from "./primitives";

function ExpertFilters() {
  const filters = useAppStore((state) => state.filters);
  const setFilter = useAppStore((state) => state.setFilter);
  return (
    <section className="space-y-2">
      <h3 className="text-xs font-semibold uppercase text-muted-foreground">Filtry eksperckie</h3>
      <label className="block text-xs">
        <span className="mb-1 block font-medium text-muted-foreground">Maks. opóźnienie (min)</span>
        <input
          type="number"
          min={0}
          className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm"
          value={filters.maxDataDelayMinutes ?? ""}
          onChange={(event) =>
            setFilter(
              "maxDataDelayMinutes",
              event.target.value ? Number(event.target.value) : null,
            )
          }
        />
      </label>
      <label className="flex items-center gap-2 text-xs">
        <input
          type="checkbox"
          checked={filters.onlyStaleCache}
          onChange={(event) => setFilter("onlyStaleCache", event.target.checked)}
        />
        Podświetl tylko warstwy z przestarzałym cache
      </label>
    </section>
  );
}

function FreshnessDashboard() {
  const query = useFreshnessQuery();
  if (query.isLoading) {
    return <Spinner label="Ładowanie monitora świeżości..." />;
  }
  if (query.isError) {
    return <StateNotice tone="error" title="Nie udało się pobrać statusu świeżości." />;
  }
  const data = query.data;
  if (!data) {
    return null;
  }
  return (
    <section className="space-y-2">
      <h3 className="flex items-center gap-2 text-xs font-semibold uppercase text-muted-foreground">
        <Gauge aria-hidden className="size-3.5" /> Świeżość danych ({data.overall_status})
      </h3>
      <ul className="space-y-1 text-xs">
        {data.sources.map((source) => (
          <li key={source.source_key} className="flex items-start justify-between gap-2">
            <span>{source.title}</span>
            <span className={cn("text-right", source.stale && "text-amber-600")}>
              {source.cache_status}
              {source.age_seconds !== null ? ` · ${Math.round(source.age_seconds / 60)} min` : ""}
            </span>
          </li>
        ))}
      </ul>
      {data.notes.map((note) => (
        <p key={note} className="text-[11px] text-muted-foreground">
          {note}
        </p>
      ))}
    </section>
  );
}

function SavedLocationsSection() {
  const savedLocations = useAppStore((state) => state.savedLocations);
  const userLocation = useAppStore((state) => state.userLocation);
  const addSavedLocation = useAppStore((state) => state.addSavedLocation);
  const removeSavedLocation = useAppStore((state) => state.removeSavedLocation);
  const setUserLocation = useAppStore((state) => state.setUserLocation);
  const [name, setName] = useState("");

  const saveCurrent = () => {
    if (!userLocation) {
      return;
    }
    addSavedLocation({
      id: createId("loc"),
      name: name.trim() || `Lokalizacja ${savedLocations.length + 1}`,
      lat: userLocation.lat,
      lon: userLocation.lon,
      createdAt: new Date().toISOString(),
    });
    setName("");
  };

  return (
    <section className="space-y-2">
      <h3 className="flex items-center gap-2 text-xs font-semibold uppercase text-muted-foreground">
        <MapPinned aria-hidden className="size-3.5" /> Zapisane lokalizacje
      </h3>
      <div className="flex gap-2">
        <input
          type="text"
          className="min-w-0 flex-1 rounded-md border border-border bg-background px-2 py-1 text-sm"
          placeholder="Nazwa"
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
        <button
          type="button"
          className="rounded-md border border-border bg-background px-2 py-1 text-xs"
          disabled={!userLocation}
          onClick={saveCurrent}
        >
          Zapisz bieżącą
        </button>
      </div>
      <ul className="space-y-1">
        {savedLocations.map((location) => (
          <li
            key={location.id}
            className="flex items-center justify-between gap-2 rounded-md border border-border px-2 py-1 text-xs"
          >
            <button
              type="button"
              className="min-w-0 flex-1 text-left hover:text-primary"
              onClick={() => {
                setUserLocation({ lat: location.lat, lon: location.lon });
                flyTo({ lat: location.lat, lng: location.lon, zoom: 9 });
              }}
            >
              <span className="block font-medium">{location.name}</span>
              <span className="text-muted-foreground">
                {location.lat.toFixed(4)}, {location.lon.toFixed(4)}
              </span>
            </button>
            <button
              type="button"
              aria-label={`Usuń ${location.name}`}
              className="text-muted-foreground hover:text-foreground"
              onClick={() => removeSavedLocation(location.id)}
            >
              <Trash2 aria-hidden className="size-3.5" />
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

function SavedViewsSection() {
  const savedViews = useAppStore((state) => state.savedViews);
  const addSavedView = useAppStore((state) => state.addSavedView);
  const removeSavedView = useAppStore((state) => state.removeSavedView);
  const applySavedView = useAppStore((state) => state.applySavedView);
  const mapView = useAppStore((state) => state.mapView);
  const activeLayers = useAppStore((state) => state.activeLayers);
  const filters = useAppStore((state) => state.filters);
  const mode = useAppStore((state) => state.mode);
  const theme = useAppStore((state) => state.theme);
  const [name, setName] = useState("");

  const saveCurrent = () => {
    addSavedView({
      id: createId("view"),
      name: name.trim() || `Widok ${savedViews.length + 1}`,
      mapView,
      activeLayers: activeLayerKeys(activeLayers),
      filters,
      mode,
      theme,
      createdAt: new Date().toISOString(),
    });
    setName("");
  };

  return (
    <section className="space-y-2">
      <h3 className="flex items-center gap-2 text-xs font-semibold uppercase text-muted-foreground">
        <Bookmark aria-hidden className="size-3.5" /> Zapisane widoki mapy
      </h3>
      <div className="flex gap-2">
        <input
          type="text"
          className="min-w-0 flex-1 rounded-md border border-border bg-background px-2 py-1 text-sm"
          placeholder="Nazwa widoku"
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
        <button
          type="button"
          className="rounded-md border border-border bg-background px-2 py-1 text-xs"
          onClick={saveCurrent}
        >
          <Save aria-hidden className="size-3.5" />
        </button>
      </div>
      <ul className="space-y-1">
        {savedViews.map((view) => (
          <li
            key={view.id}
            className="flex items-center justify-between gap-2 rounded-md border border-border px-2 py-1 text-xs"
          >
            <button
              type="button"
              className="min-w-0 flex-1 text-left hover:text-primary"
              onClick={() => {
                applySavedView(view);
                flyTo({ lat: view.mapView.lat, lng: view.mapView.lng, zoom: view.mapView.zoom });
              }}
            >
              <span className="block font-medium">{view.name}</span>
              <span className="text-muted-foreground">{formatTimestamp(view.createdAt)}</span>
            </button>
            <button
              type="button"
              aria-label={`Usuń ${view.name}`}
              className="text-muted-foreground hover:text-foreground"
              onClick={() => removeSavedView(view.id)}
            >
              <Trash2 aria-hidden className="size-3.5" />
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

function LocalAlertsSection() {
  const alertRules = useAppStore((state) => state.alertRules);
  const addAlertRule = useAppStore((state) => state.addAlertRule);
  const removeAlertRule = useAppStore((state) => state.removeAlertRule);
  const updateAlertRule = useAppStore((state) => state.updateAlertRule);
  const userLocation = useAppStore((state) => state.userLocation);
  const selection = useAppStore((state) => state.selection);
  const sourcesQuery = useSourcesQuery();
  const locationQuery = useLocationSummaryQuery(userLocation);
  const comparisonQuery = useWarningComparisonQuery(
    selection?.kind === "station" ? selection.id : null,
  );

  const context = useMemo(() => {
    const warnings = locationQuery.data?.warnings ?? [];
    const levels = warnings
      .map((warning) => warning.level)
      .filter((level): level is number => level !== null);
    const observations = comparisonQuery.data?.observations ?? [];
    const firstObservation = observations[0];
    return {
      userLocation,
      nearbyWarningCount: warnings.length,
      maxNearbyWarningLevel: levels.length ? Math.max(...levels) : null,
      stationMetricValue: firstObservation?.value ?? null,
      staleSourceKeys: staleSourceKeys(sourcesQuery.data?.sources ?? []),
    };
  }, [comparisonQuery.data, locationQuery.data, sourcesQuery.data, userLocation]);

  const evaluations = alertRules.map((rule) => evaluateAlertRule(rule, context));

  const addRule = (type: AlertRuleType) => {
    const rule: AlertRule = {
      id: createId("alert"),
      name:
        type === "warning_nearby"
          ? "Ostrzeżenia w pobliżu"
          : type === "warning_level"
            ? "Ostrzeżenie poziom 2+"
            : type === "station_threshold"
              ? "Próg stacji"
              : "Przestarzałe źródło synop",
      enabled: true,
      type,
      warningLevel: type === "warning_level" ? 2 : undefined,
      sourceKey: type === "stale_source" ? "synop" : undefined,
      operator: "gt",
      threshold: 0,
    };
    addAlertRule(rule);
  };

  return (
    <section className="space-y-2">
      <h3 className="flex items-center gap-2 text-xs font-semibold uppercase text-muted-foreground">
        <AlertTriangle aria-hidden className="size-3.5" /> Lokalne reguły alertów
      </h3>
      <StateNotice tone="warning" title="To nie jest urzędowy system ostrzegania">
        {ALERTING_DISCLAIMER}
      </StateNotice>
      <div className="flex flex-wrap gap-1">
        <button
          type="button"
          className="rounded-md border border-border px-2 py-1 text-[11px]"
          onClick={() => addRule("warning_nearby")}
        >
          + pobliże
        </button>
        <button
          type="button"
          className="rounded-md border border-border px-2 py-1 text-[11px]"
          onClick={() => addRule("warning_level")}
        >
          + poziom
        </button>
        <button
          type="button"
          className="rounded-md border border-border px-2 py-1 text-[11px]"
          onClick={() => addRule("stale_source")}
        >
          + stale cache
        </button>
      </div>
      <ul className="space-y-1">
        {evaluations.map((evaluation) => {
          const rule = alertRules.find((item) => item.id === evaluation.ruleId);
          if (!rule) {
            return null;
          }
          return (
            <li
              key={rule.id}
              className={cn(
                "rounded-md border px-2 py-1 text-xs",
                evaluation.triggered ? "border-amber-500/50 bg-amber-500/10" : "border-border",
              )}
            >
              <div className="flex items-start justify-between gap-2">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={rule.enabled}
                    onChange={(event) =>
                      updateAlertRule({ ...rule, enabled: event.target.checked })
                    }
                  />
                  <span>{evaluation.message}</span>
                </label>
                <button
                  type="button"
                  aria-label={`Usuń regułę ${rule.name}`}
                  onClick={() => removeAlertRule(rule.id)}
                >
                  <Trash2 aria-hidden className="size-3.5" />
                </button>
              </div>
              {evaluation.disabledReason && (
                <p className="mt-1 text-[11px] text-muted-foreground">{evaluation.disabledReason}</p>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function WarningComparisonSection() {
  const selection = useAppStore((state) => state.selection);
  const stationId = selection?.kind === "station" ? selection.id : null;
  const query = useWarningComparisonQuery(stationId);

  if (!stationId) {
    return (
      <StateNotice tone="info" title="Porównanie ostrzeżeń">
        Zaznacz stację na mapie, aby porównać pomiary z aktywnymi ostrzeżeniami.
      </StateNotice>
    );
  }

  if (query.isLoading) {
    return <Spinner label="Porównywanie ostrzeżeń i pomiarów..." />;
  }
  if (query.isError || !query.data) {
    return <StateNotice tone="error" title="Nie udało się pobrać porównania." />;
  }

  return (
    <section className="space-y-2">
      <h3 className="text-xs font-semibold uppercase text-muted-foreground">
        Ostrzeżenia vs pomiar stacji
      </h3>
      <p className="text-xs text-muted-foreground">{query.data.alerting_disclaimer}</p>
      <div className="grid gap-2 sm:grid-cols-2">
        <div className="rounded-md border border-border p-2 text-xs">
          <p className="mb-1 font-medium">Pomiary</p>
          <ul className="space-y-1">
            {query.data.observations.map((observation) => (
              <li key={observation.metric}>
                {observation.metric}: {formatValue(observation.value, observation.unit)}
              </li>
            ))}
          </ul>
        </div>
        <div className="rounded-md border border-border p-2 text-xs">
          <p className="mb-1 font-medium">Aktywne ostrzeżenia ({query.data.warnings.length})</p>
          <ul className="space-y-1">
            {query.data.warnings.map((warning) => (
              <li key={warning.id}>{warning.event}</li>
            ))}
          </ul>
        </div>
      </div>
      {query.data.notes.map((note) => (
        <p key={note} className="text-[11px] text-muted-foreground">
          {note}
        </p>
      ))}
    </section>
  );
}

export function PowerUserPanel() {
  const open = useAppStore((state) => state.powerPanelOpen);
  const setOpen = useAppStore((state) => state.setPowerPanelOpen);
  const mode = useAppStore((state) => state.mode);
  const dashboardWidgets = useAppStore((state) => state.dashboardWidgets);
  const setDashboardWidgets = useAppStore((state) => state.setDashboardWidgets);

  if (!open || mode !== "expert") {
    return null;
  }

  return (
    <aside
      className="absolute bottom-0 right-0 top-0 z-30 flex w-[min(420px,100vw)] flex-col gap-4 overflow-y-auto border-l border-border bg-card/95 p-3 text-card-foreground shadow-xl backdrop-blur lg:bottom-4 lg:right-4 lg:top-4 lg:max-h-[calc(100%-2rem)] lg:rounded-lg lg:border"
      aria-label="Panel narzędzi zaawansowanych"
      data-testid="power-user-panel"
    >
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold">Narzędzia zaawansowane</h2>
        <button
          type="button"
          className="inline-flex size-8 items-center justify-center rounded-md border border-border bg-background"
          aria-label="Zamknij panel narzędzi"
          onClick={() => setOpen(false)}
        >
          <X aria-hidden className="size-4" />
        </button>
      </div>

      <section className="space-y-2">
        <h3 className="text-xs font-semibold uppercase text-muted-foreground">Układ pulpitu</h3>
        {(Object.keys(dashboardWidgets) as Array<keyof typeof dashboardWidgets>).map((key) => (
          <label key={key} className="flex items-center gap-2 text-xs">
            <input
              type="checkbox"
              checked={dashboardWidgets[key]}
              onChange={(event) =>
                setDashboardWidgets({ ...dashboardWidgets, [key]: event.target.checked })
              }
            />
            {key}
          </label>
        ))}
      </section>

      <ExpertFilters />
      {dashboardWidgets.showFreshness && <FreshnessDashboard />}
      {dashboardWidgets.showSavedViews && (
        <>
          <SavedLocationsSection />
          <SavedViewsSection />
        </>
      )}
      {dashboardWidgets.showAlerts && <LocalAlertsSection />}
      {dashboardWidgets.showComparison && <WarningComparisonSection />}
    </aside>
  );
}
