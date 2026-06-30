import { Loader2, MapPin, Search } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import type { StationListItem } from "../api/client";
import { useStationSearchQuery } from "../api/queries";
import { FOCUS_SEARCH_EVENT } from "../hooks/useKeyboardShortcuts";
import { flyTo } from "../lib/mapBus";
import { useAppStore } from "../store/appStore";

function useDebounced<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(id);
  }, [value, delay]);
  return debounced;
}

export function SearchBox() {
  const [term, setTerm] = useState("");
  const [open, setOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const debounced = useDebounced(term, 250);
  const select = useAppStore((state) => state.select);
  const searchQuery = useStationSearchQuery(debounced);
  const results = searchQuery.data?.stations ?? [];

  useEffect(() => {
    const focus = () => inputRef.current?.focus();
    window.addEventListener(FOCUS_SEARCH_EVENT, focus);
    return () => window.removeEventListener(FOCUS_SEARCH_EVENT, focus);
  }, []);

  const onPick = (station: StationListItem) => {
    select({ kind: "station", id: station.id });
    if (station.lon != null && station.lat != null) {
      flyTo({ lng: station.lon, lat: station.lat, zoom: 9 });
    }
    setOpen(false);
    setTerm(station.name);
  };

  const showDropdown = open && debounced.trim().length >= 2;

  return (
    <div className="relative w-full max-w-lg">
      <label className="flex items-center gap-2 rounded-md border border-border bg-background px-3 py-2 text-sm">
        <Search aria-hidden className="size-4 text-muted-foreground" />
        <input
          ref={inputRef}
          className="min-w-0 flex-1 bg-transparent outline-none"
          placeholder="Szukaj stacji (np. Warszawa)"
          type="search"
          aria-label="Szukaj stacji"
          value={term}
          onChange={(event) => {
            setTerm(event.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => window.setTimeout(() => setOpen(false), 150)}
        />
        {searchQuery.isFetching && <Loader2 aria-hidden className="size-4 animate-spin text-muted-foreground" />}
      </label>

      {showDropdown && (
        <ul className="absolute z-30 mt-1 max-h-72 w-full overflow-auto rounded-md border border-border bg-card text-card-foreground shadow-lg">
          {searchQuery.isError && (
            <li className="px-3 py-2 text-sm text-warning">Wyszukiwanie niedostępne — sprawdź backend.</li>
          )}
          {!searchQuery.isError && results.length === 0 && !searchQuery.isFetching && (
            <li className="px-3 py-2 text-sm text-muted-foreground">Brak pasujących stacji.</li>
          )}
          {results.map((station) => (
            <li key={station.id}>
              <button
                type="button"
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-muted"
                // onMouseDown fires before input blur so the pick is not lost.
                onMouseDown={(event) => {
                  event.preventDefault();
                  onPick(station);
                }}
              >
                <MapPin aria-hidden className="size-4 shrink-0 text-muted-foreground" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium">{station.name}</span>
                  <span className="block text-xs text-muted-foreground">
                    {station.station_type}
                    {station.lat == null || station.lon == null ? " · brak współrzędnych" : ""}
                  </span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
