import { defineConfig, devices } from "@playwright/test";

const backendPort = Number(process.env.PLAYWRIGHT_BACKEND_PORT ?? "8000");
const backendUrl =
  process.env.PLAYWRIGHT_BACKEND_URL ?? `http://127.0.0.1:${backendPort}`;
const frontendPort = Number(process.env.PLAYWRIGHT_FRONTEND_PORT ?? "3000");
const frontendUrl =
  process.env.PLAYWRIGHT_FRONTEND_URL ?? `http://127.0.0.1:${frontendPort}`;

/**
 * Recoup Hackathon — Playwright E2E Config
 *
 * Starts backend and frontend (:3000) before running tests.
 * Run: npx playwright test
 * Smoke only: npx playwright test --grep @smoke
 *
 * If port 8000 is occupied (e.g. Docker), use your live API port:
 *   PLAYWRIGHT_BACKEND_PORT=8010 npx playwright test
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 360_000,
  retries: process.env.CI ? 1 : 0,
  workers: 1, // Serial — tests share in-memory backend state
  reporter: [["list"], ["html", { open: "never" }]],

  use: {
    baseURL: frontendUrl,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],

  webServer: [
    {
      command: `cd ../backend && RECOUP_SNS_DRY_RUN=1 PYTHONPATH=src python3 -m uvicorn recoup.api.main:app --port ${backendPort}`,
      url: `${backendUrl}/health`,
      timeout: 120_000,
      reuseExistingServer: process.env.PLAYWRIGHT_REUSE_SERVERS === "1",
    },
    {
      command: `NEXT_PUBLIC_API_URL=${backendUrl} npm run dev -- --port ${frontendPort} --hostname 127.0.0.1`,
      url: frontendUrl,
      timeout: 120_000,
      reuseExistingServer: process.env.PLAYWRIGHT_REUSE_SERVERS === "1",
    },
  ],
});
