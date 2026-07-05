# UI_UX.md - MeteoLens UI/UX

## Product Direction

MeteoLens should feel like a practical weather and hydrology operations panel,
not a marketing site. The first screen is the map dashboard.

## Primary Layout

Desktop:

- Full-screen map.
- Top compact toolbar with search, active location, theme, simple/expert mode,
  and export actions.
- Left or right control panel for layers, filters, and legends.
- Side details panel for selected station or warning.
- Bottom timeline only when a selected layer has time-aware data.

Mobile:

- Full-screen map.
- Compact top controls.
- Layer/filter controls in a sheet.
- Details as bottom sheet.
- Timeline above mobile navigation/sheet handle.

## Map Layers

MVP layers:

- Synoptic stations.
- Hydrological stations.
- Meteorological stations.
- Meteorological warnings.
- Hydrological warnings.

Each layer needs:

- visible legend,
- loading state,
- empty state,
- stale data marker when applicable,
- source timestamp,
- error message when source fails.

## Selection Details

Station panel:

- station name,
- station type,
- source ID,
- coordinates if available,
- reviewed coordinate source when coordinates come from a geometry dataset,
- latest metrics,
- measurement timestamp,
- retrieval timestamp,
- data delay,
- missing fields,
- chart tab,
- export buttons,
- expert raw data section.

Warning panel:

- phenomenon/event name,
- warning level,
- probability,
- valid from/to,
- published timestamp,
- office,
- affected area labels/codes,
- content,
- comment,
- geometry status (resolved, partial, or missing) without hiding unresolved
  area codes,
- source/retrieval metadata,
- expert raw data section.

## Simple And Expert Modes

Simple mode:

- prioritizes readable labels,
- shows key values and warnings,
- still shows timestamp, delay, missing data, and source.

Expert mode:

- shows raw JSON,
- shows parser/cache metadata,
- shows source URL,
- shows missing-field list,
- shows raw timestamps and source field names.

## Filters

MVP quick filters:

- data type,
- province or administrative area when geometry is available,
- warning level,
- phenomenon/event type,
- time range for time-aware data.

Filters must be reflected in permalink state.

Stage 8 should add metric, date/time range, aggregation interval, and station
comparison filters for time-series views. Stage 9 should add province, county,
and basin filters only where reviewed geometry exists. Stage 11 should add
advanced expert filters without hiding missing values or stale-source states.

## Timeline And Animation

Timeline appears only for time-aware data. MVP can support current/latest data
first; archive/radar/model timelines are post-MVP.

Controls:

- play/pause,
- previous/next step,
- speed selector,
- current timestamp label,
- stale/missing frame indication.

Stage 8 should enable the timeline for historical observation series where real
multi-point data exists. Stage 10 extends the same control pattern to radar/product
frames using cached manifest metadata. The timeline appears when
`/api/v1/map/timeline` returns layers.

Stage 14 adds the first rendered layer: for renderable products (COSMO `*_00`
2 m temperature) the timeline offers an explicit "Pokaż na mapie" toggle that
draws the rendered frame as a semi-transparent map overlay (image source under
station markers and warning polygons). The overlay is opt-in because the first
render of each frame triggers a large backend download. While a rendered layer
is active the timeline shows the variable name, unit, a colour legend, the
attribution line, and the processed-data notice. Frames outside the render
window/step, constant-field files, and readme entries carry explicit
non-renderable labels; overlay image load failures surface as a visible error
message in the timeline bar. Non-renderable products (including radar
composites with source-blocked downloads) keep metadata-only labels and never
draw anything on the map.

Timeline labels must distinguish:

- source time,
- frame or observation time (plus model run time for forecast products),
- retrieval time,
- stale frames,
- missing frames,
- renderable vs metadata-only frames (with the non-renderable reason),
- processed-data notice.

## Permalinks

Permalink state includes:

- map center,
- zoom,
- active layers,
- selected object,
- filters,
- simple/expert mode,
- theme preference when appropriate.

Permalinks must not encode raw sensitive local browser state.

## Keyboard Shortcuts

Planned MVP shortcuts:

- `/` focuses search.
- `Escape` closes details/sheets or clears selection.
- `Space` toggles timeline play/pause when timeline is visible.
- Arrow keys step timeline frames when timeline is focused.
- Number keys toggle primary map layers when focus is not inside an input.
- `?` opens shortcut help.

Shortcuts must not hijack text inputs and must be documented in the UI only
through an intentional help surface, not scattered instructional text.

## Error And Empty States

Use explicit states:

- loading source,
- source unavailable,
- parser failed,
- no active warnings,
- no station geometry,
- stale cache,
- partial data,
- unsupported product.

Do not hide source failures behind an empty map.

Future stages must add explicit states for:

- unresolved TERYT or basin geometry,
- unresolved synoptic station coordinates,
- no observations in selected time range,
- product file unavailable,
- product frame missing,
- stale product frame,
- local alert rule disabled because data is stale or incomplete.

## Visual Style

- Clear, dense, readable operational UI.
- Use restrained color with strong contrast for warnings and hydrological
  statuses.
- Avoid decorative hero sections and marketing copy.
- Use icons for layer toggles, exports, theme, play/pause, search, and location.
- Keep cards for repeated objects or panels; do not nest cards.
- Ensure text does not overlap on mobile.

## Attribution Placement

- Always visible map attribution.
- Reviewed geometry attribution when administrative polygons or reviewed
  coordinate datasets are displayed or exported.
- Source line in every detail panel.
- Source metadata in export dialogs.
- Processed-data notice near derived or normalized data.

Stage 11 local alerts must include a clear responsibility boundary: MeteoLens
may notify about local rules and nearby data, but it must not present itself as
an official warning system.

## Stage 5 Implementation Status

The map-first dashboard is implemented. Notable, intentional deviations from the
target spec above, driven by current backend data:

- Meteorological warnings render reviewed PRG county/voivodeship polygons where
  TERYT codes resolve; unresolved areas stay visible in counts, list records,
  and the details panel. Hydro basin warnings remain list-only until a reviewed
  basin dataset is imported.
- The IMGW cache exposes a single observation timestamp per station, so the
  station chart shows current metric values (missing values excluded) rather
  than a time series, and the bottom timeline/animation control is omitted until
  time-aware (archive/radar) data is available.
- Quick filters implemented for MVP include warning level, phenomenon, province,
  county, and basin-code filtering where reviewed geometry or source area codes
  support them. Time-range filters wait on archive series.
- Layer legends are rendered as coloured swatches with on-map counts in the
  layer toggles; warning legend entries note the missing geometry.
- The PNG export captures the current MapLibre canvas; CSV/JSON/GeoJSON exports
  are backend downloads.

## Planned Future UX

- Stage 7 should add production/demo readiness tasks around README screenshots
  and public deployment documentation, but it should not change the app into a
  marketing landing page.
- Stage 8 should replace snapshot-only charts with real time-series charts,
  station comparison, rankings, and time-range exports.
- Stage 9 should render warning polygons and location-specific warning matching
  only where reviewed geometry and reliable code mapping exist; unresolved
  geometry remains visible as partial data.
- Stage 10 adds a product timeline shell driven by frame metadata APIs. Radar/GRIB
  map layers and tile rendering remain future work once binary ingestion exists.
- Stage 11 adds saved locations/views (browser-local), dashboard widget toggles,
  local alert rules with an official-warning disclaimer, freshness monitor,
  warning-vs-station comparison, expert filters, and a minimal PWA shell. Trend/
  anomaly automation and generated API clients remain documented future work.
