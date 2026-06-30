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

## Timeline And Animation

Timeline appears only for time-aware data. MVP can support current/latest data
first; archive/radar/model timelines are post-MVP.

Controls:

- play/pause,
- previous/next step,
- speed selector,
- current timestamp label,
- stale/missing frame indication.

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
- Source line in every detail panel.
- Source metadata in export dialogs.
- Processed-data notice near derived or normalized data.
