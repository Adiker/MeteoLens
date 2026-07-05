#!/usr/bin/env node
import { getJson, optionValue, query } from "./_lib.mjs";

const args = process.argv.slice(2);
const lat = args[0];
const lon = args[1];
if (!lat || !lon) {
  throw new Error("Usage: active-warnings-for-location.mjs <lat> <lon> [--radius-km 50]");
}

const payload = await getJson(
  `/api/v1/location/summary${query({
    lat,
    lon,
    radius_km: optionValue(args, "--radius-km", "50"),
  })}`,
);

for (const warning of payload.warnings) {
  console.log(
    [
      warning.id,
      warning.warning_type,
      warning.level ?? "",
      warning.event,
      warning.valid_to ?? "",
      warning.geometry_status ?? "unknown_geometry",
    ].join("\t"),
  );
}
if (payload.notes.length > 0) {
  console.error(payload.notes.join("\n"));
}
