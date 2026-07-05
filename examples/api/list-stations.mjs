#!/usr/bin/env node
import { getJson, optionValue, query } from "./_lib.mjs";

const args = process.argv.slice(2);
const type = optionValue(args, "--type");
const q = optionValue(args, "--q");
const limit = optionValue(args, "--limit", "10");

const payload = await getJson(`/api/v1/stations${query({ type, q, limit })}`);
for (const station of payload.stations) {
  console.log(
    [
      station.id,
      station.name,
      station.station_type,
      station.latest_observed_at ?? "no timestamp",
      station.source.attribution,
    ].join("\t"),
  );
}
if (payload.empty_state) {
  console.error(`${payload.empty_state.code}: ${payload.empty_state.message}`);
}
