import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { defineConfig, devices } from "@playwright/test";

const frontendDir = path.dirname(fileURLToPath(import.meta.url));
const backendDir = path.resolve(frontendDir, "../backend");

const BACKEND_PORT = 8123;
const FRONTEND_PORT = 5183;

// Local dev sets up `backend/.venv` (see CLAUDE.md); CI installs into the
// runner's system Python instead, so fall back to plain `python`/`uvicorn`.
const hasVenv = existsSync(path.join(backendDir, ".venv/bin/python"));
const backendPython = hasVenv ? ".venv/bin/python" : "python";
const backendUvicorn = hasVenv ? ".venv/bin/uvicorn" : "uvicorn";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  fullyParallel: false,
  workers: 1,
  reporter: "list",
  use: {
    baseURL: `http://localhost:${FRONTEND_PORT}`,
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      // Seeds a throwaway cache from the backend's own parser fixtures so the
      // suite exercises real API responses without calling out to IMGW-PIB.
      command:
        `rm -rf .e2e-cache && ${backendPython} -m tests.e2e_seed_cache .e2e-cache && ` +
        `${backendUvicorn} app.main:app --port ${BACKEND_PORT}`,
      cwd: backendDir,
      port: BACKEND_PORT,
      env: {
        METEOLENS_CACHE_DIR: ".e2e-cache",
        METEOLENS_FRONTEND_ORIGIN: `http://localhost:${FRONTEND_PORT}`,
      },
      reuseExistingServer: false,
      timeout: 30_000,
    },
    {
      command: `npm run dev -- --port ${FRONTEND_PORT} --strictPort`,
      cwd: frontendDir,
      port: FRONTEND_PORT,
      env: {
        VITE_API_BASE_URL: `http://localhost:${BACKEND_PORT}`,
      },
      reuseExistingServer: false,
      timeout: 30_000,
    },
  ],
});
