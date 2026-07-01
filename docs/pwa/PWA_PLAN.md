# PWA Support Plan

Stage 11 adds a minimal installable shell without offline IMGW data access.

## Implemented

- Web app manifest (`frontend/public/manifest.webmanifest`)
- SVG icon (`frontend/public/icon.svg`)
- Service worker caching the static shell only (`frontend/public/sw.js`)
- Production registration in `frontend/src/main.tsx`

## Explicit Non-Goals

- Offline IMGW fetch or cache refresh in the service worker
- Background sync of warnings or station data
- Push notifications for local alert rules

Local alert rules remain in-browser evaluations against live backend data. A future
PWA phase could add explicit user consent flows before any notification permission
request.

## Next Steps

1. Add production nginx/Caddy `Service-Worker-Allowed` headers if scope changes.
2. Evaluate `vite-plugin-pwa` once offline asset hashing requirements are clear.
3. Document install steps in `README.md` after a public demo deployment exists.
4. Keep attribution and processed-data notices visible in installed mode.

## Legal And Responsibility Notes

An installed PWA must still show that MeteoLens is not an official IMGW-PIB
alerting channel. Do not use PWA install badges or notification UX that implies
official warning delivery.
