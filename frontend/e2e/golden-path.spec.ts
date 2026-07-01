import { expect, test } from "@playwright/test";

// The webServer config seeds the backend cache from the parser test fixtures
// (backend/tests/fixtures), so station/warning ids and values below mirror
// those fixtures — see backend/tests/e2e_seed_cache.py.
const HYDRO_STATION_ID = "hydro:151140030";
const METEO_WARNING_ID = "warningsmeteo:Sk20260630043222424";

test("loads the map shell with attribution and layer toggles", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "MeteoLens" })).toBeVisible();
  await expect(page.getByLabel("Mapa MeteoLens")).toBeVisible();
  await expect(page.getByText("Źródło danych: IMGW-PIB.")).toBeVisible();
  await expect(page.getByLabel("Warstwa Stacje synoptyczne")).toBeChecked();
});

test("searches for a station and shows its details honestly, including missing values", async ({
  page,
}) => {
  await page.goto("/");

  await page.getByLabel("Szukaj stacji").fill("Przewo");
  await page.getByRole("button", { name: /Przewoźniki/ }).click();

  const panel = page.getByRole("dialog", { name: "Panel szczegółów" });
  await expect(panel.getByRole("heading", { name: "Przewoźniki" })).toBeVisible();
  // temperatura_wody is null in the seeded fixture — it must render as an
  // explicit missing value, never silently coerced to 0.
  await expect(panel.getByText("brak danych")).toBeVisible();
  await expect(panel.getByText("Braki danych:", { exact: false })).toBeVisible();

  const csvLink = panel.getByRole("link", { name: "CSV" });
  await expect(csvLink).toHaveAttribute(
    "href",
    new RegExp(`/export/station/${encodeURIComponent(HYDRO_STATION_ID)}\\.csv$`),
  );

  await panel.getByLabel("Zamknij panel szczegółów").click();
  await expect(panel).not.toBeVisible();
});

test("toggling a layer checkbox updates its checked state", async ({ page }) => {
  await page.goto("/");
  const checkbox = page.getByLabel("Warstwa Stacje synoptyczne");

  await expect(checkbox).toBeChecked();
  await checkbox.click();
  await expect(checkbox).not.toBeChecked();
  await checkbox.click();
  await expect(checkbox).toBeChecked();
});

test("opens and closes keyboard shortcut help", async ({ page }) => {
  await page.goto("/");

  await page.keyboard.press("?");
  const dialog = page.getByRole("dialog", { name: "Skróty klawiszowe" });
  await expect(dialog).toBeVisible();

  await page.keyboard.press("Escape");
  await expect(dialog).not.toBeVisible();
});

test("deep-links to a warning and surfaces the missing-geometry notice", async ({ page }) => {
  await page.goto(`/?sel=w:${METEO_WARNING_ID}`);

  const panel = page.getByRole("dialog", { name: "Panel szczegółów" });
  await expect(panel.getByRole("heading", { name: "Burze" })).toBeVisible();
  await expect(panel.getByText("Brak geometrii obszaru")).toBeVisible();
});
