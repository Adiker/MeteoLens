#!/usr/bin/env node
import { BASE_URL, optionValue, query } from "./_lib.mjs";

const args = process.argv.slice(2);
const stationId = args[0];
if (!stationId) {
  throw new Error("Usage: export-station-range.mjs <station-id> [--format csv|json]");
}

const format = optionValue(args, "--format", "csv");
if (!["csv", "json"].includes(format)) {
  throw new Error("--format must be csv or json");
}

const path = `/api/v1/export/station/${encodeURIComponent(
  stationId,
)}/observations.${format}${query({
  metric: optionValue(args, "--metric"),
  from: optionValue(args, "--from"),
  to: optionValue(args, "--to"),
  interval: optionValue(args, "--interval", "raw"),
  limit: optionValue(args, "--limit", "500"),
})}`;

console.log(`${BASE_URL}${path}`);
