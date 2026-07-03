// Stage 12 frontend smoke test against a live-cache MeteoLens stack.
//
// Drives a real browser through the map shell, station details, warnings,
// exports, expert tools, and the timeline shell, and optionally captures the
// populated-cache screenshots referenced from README.md.
//
// Usage (dev stack): node scripts/smoke.mjs http://localhost:5173 http://localhost:8000 [screenshotDir]
// Usage (prod stack): node scripts/smoke.mjs http://localhost:8080 http://localhost:8080 [screenshotDir]
import { mkdir } from "node:fs/promises";
import { chromium } from "@playwright/test";

const BASE = process.argv[2] ?? "http://localhost:5173";
const API_BASE = process.argv[3] ?? "http://localhost:8000";
const OUT = process.argv[4] ?? null;

const results = [];
function record(name, ok, note = "") {
  results.push({ name, ok, note });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${note ? ` — ${note}` : ""}`);
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

async function chooseStationName() {
  const stationsApi = await fetch(`${API_BASE}/api/v1/stations`)
    .then((res) => res.json())
    .catch(() => null);
  const stations = stationsApi?.stations ?? [];
  const station =
    stations.find((item) => /Warszawa/i.test(item.name)) ??
    stations.find((item) => item.lat != null && item.lon != null) ??
    stations[0];

  return station?.name ?? "Warszawa";
}

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
page.setDefaultTimeout(20000);
if (OUT) await mkdir(OUT, { recursive: true });

try {
  await page.goto(BASE, { waitUntil: "networkidle" });

  // 1. Map shell + attribution
  await page.getByRole("heading", { name: "MeteoLens" }).waitFor();
  await page.getByLabel("Mapa MeteoLens").waitFor();
  const attributionVisible = await page
    .getByText("Źródło danych: IMGW-PIB.")
    .first()
    .isVisible();
  record("map shell renders with IMGW-PIB attribution", attributionVisible);

  // let MapLibre finish tile/marker rendering before the screenshot
  await page.waitForTimeout(6000);
  if (OUT) await page.screenshot({ path: `${OUT}/map-stations-light.png` });

  // 2. Timeline shell. It renders only when cached product frame manifests
  // exist (`/api/v1/map/timeline` layers non-empty); hidden-on-empty is the
  // documented empty state, so verify UI visibility against the API.
  const timeline = page.getByLabel("Oś czasu produktów");
  const timelineVisible = await timeline.isVisible().catch(() => false);
  const timelineApi = await fetch(`${API_BASE}/api/v1/map/timeline`)
    .then((res) => res.json())
    .catch(() => null);
  const timelineLayers = timelineApi?.layers?.length ?? null;
  if (timelineVisible) {
    const note = (await timeline.innerText()).replace(/\s+/g, " ").slice(0, 120);
    record("timeline shell renders cached product frames", true, note);
  } else {
    record(
      "timeline shell hidden matches empty timeline API",
      timelineLayers === 0,
      `timeline API layers: ${timelineLayers === null ? "unreachable" : timelineLayers}`,
    );
  }

  // 3. Expert mode + station details via search
  const stationName = await chooseStationName();
  await page.getByLabel("Przełącz tryb prosty/ekspercki").click();
  await page.getByLabel("Szukaj stacji").fill(stationName);
  await page
    .getByRole("button", { name: new RegExp(escapeRegExp(stationName), "i") })
    .first()
    .click();
  const panel = page.getByRole("dialog", { name: "Panel szczegółów" });
  await panel.waitFor();
  await panel.getByText(/Pobrano:/).waitFor();
  record("station details panel opens from search", true, stationName);
  const panelText = await panel.innerText();
  record(
    "station details show retrieval timestamp and delay",
    /Pobrano:/.test(panelText) && /Opóźnienie/.test(panelText),
  );
  record(
    "expert mode exposes raw source data",
    // the heading is CSS-uppercased, so innerText returns capitals
    /surowe dane źródła/i.test(panelText),
  );
  const csvVisible = await panel.getByRole("link", { name: "CSV" }).first().isVisible();
  const jsonVisible = await panel.getByRole("link", { name: "JSON" }).first().isVisible();
  record("station CSV/JSON export links present", csvVisible && jsonVisible);
  await page.waitForTimeout(1500);
  if (OUT) await page.screenshot({ path: `${OUT}/station-details-expert.png` });
  await page.getByLabel("Zamknij panel szczegółów").click();

  // 4. Warnings list + warning details
  const warningsHeading = page.getByText(/Aktywne ostrzeżenia \(\d+\)/);
  await warningsHeading.first().waitFor();
  const controlPanel = page.getByLabel("Panel warstw i filtrów");
  const warningsHeadingText = await warningsHeading.first().innerText();
  const warningCount = Number(warningsHeadingText.match(/\((\d+)\)/)?.[1] ?? NaN);
  record("warning list renders", Number.isFinite(warningCount), warningsHeadingText);

  if (warningCount > 0) {
    const firstWarning = controlPanel
      .locator("button")
      .filter({ hasText: /poziom|st\.|Burze|upał|Susza|deszcz|wezbrani/i })
      .first();
    await firstWarning.click();
    await panel.waitFor();
    const warnText = await panel.innerText();
    record(
      "warning details show validity + office metadata",
      /Ważne|Obowiązuje|Biuro|IMGW/i.test(warnText),
    );
    record(
      "missing area geometry stays explicit",
      /Brak geometrii obszaru/i.test(warnText),
    );
    await page.waitForTimeout(1000);
    if (OUT) await page.screenshot({ path: `${OUT}/warning-details-list.png` });
    await page.getByLabel("Zamknij panel szczegółów").click();
  } else {
    const emptyWarningState = controlPanel.getByText("Brak aktywnych ostrzeżeń");
    record("warning empty state renders", await emptyWarningState.isVisible());
    if (OUT) await page.screenshot({ path: `${OUT}/warning-details-list.png` });
  }

  // 5. Export menu (map-level GeoJSON/PNG)
  const exportButton = page.getByLabel("Eksport danych");
  await exportButton.click();
  await page.waitForTimeout(500);
  const bodyText = await page.locator("body").innerText();
  record(
    "export menu offers GeoJSON and PNG",
    /GeoJSON/i.test(bodyText) && /PNG/i.test(bodyText),
  );
  const downloadPromise = page.waitForEvent("download", { timeout: 15000 });
  await page.getByText(/Bieżąca mapa — PNG/i).click();
  const download = await downloadPromise.catch(() => null);
  record(
    "current-map PNG export downloads a file",
    download !== null,
    download ? download.suggestedFilename() : "no download event",
  );

  // 6. Power-user (advanced tools) panel in expert mode. The header toggle
  // button and the panel itself share the same aria-label, so target the
  // button by role and the panel by excluding buttons.
  const advancedToggle = page.getByRole("button", {
    name: "Panel narzędzi zaawansowanych",
  });
  const advancedPanel = page.locator(
    '[aria-label="Panel narzędzi zaawansowanych"]:not(button)',
  );
  await advancedToggle.click();
  await advancedPanel.waitFor();
  record("power-user panel opens in expert mode", await advancedPanel.isVisible());
  await page.waitForTimeout(500);
  if (OUT) await page.screenshot({ path: `${OUT}/power-user-panel.png` });
} catch (err) {
  record("smoke script completed", false, String(err).slice(0, 300));
  if (OUT) await page.screenshot({ path: `${OUT}/smoke-failure.png` }).catch(() => {});
} finally {
  await browser.close();
}

const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
process.exit(failed.length ? 1 : 0);
