#!/usr/bin/env node
import { getJson } from "./_lib.mjs";

const payload = await getJson("/api/v1/status/freshness");
console.log(`overall\t${payload.overall_status}`);
console.log(payload.attribution);
console.log(payload.processed_notice);
for (const source of payload.sources) {
  console.log(
    [
      source.source_key,
      source.cache_status,
      source.stale ? "stale" : "fresh",
      source.age_seconds ?? "",
      source.error ?? "",
    ].join("\t"),
  );
}
