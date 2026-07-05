#!/usr/bin/env node
import { getJson, optionValue, query } from "./_lib.mjs";

const args = process.argv.slice(2);
const stationId = args[0];
if (!stationId) {
  throw new Error("Usage: fetch-station-observations.mjs <station-id> [--metric metric]");
}

const payload = await getJson(
  `/api/v1/stations/${encodeURIComponent(stationId)}/observations${query({
    metric: optionValue(args, "--metric"),
    from: optionValue(args, "--from"),
    to: optionValue(args, "--to"),
    interval: optionValue(args, "--interval", "raw"),
    limit: optionValue(args, "--limit", "20"),
  })}`,
);

console.log(`${payload.station_id}\t${payload.series_kind}\t${payload.series_origin}`);
console.log(`${payload.source.attribution} ${payload.source.processed_notice}`);
for (const observation of payload.observations) {
  console.log(
    [
      observation.metric,
      observation.value ?? "",
      observation.unit ?? "",
      observation.observed_at ?? "",
      observation.missing,
      observation.origin ?? payload.series_origin,
    ].join("\t"),
  );
}
