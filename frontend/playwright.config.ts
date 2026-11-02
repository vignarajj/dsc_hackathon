import { defineConfig, devices } from "@playwright/test";

// The API runs with a fake model gateway (backend/tests/fake_server.py), so
// these tests never call Meta. CHROMIUM_PATH points at a browser that is
// already installed; otherwise run `pnpm exec playwright install chromium`.
// The ports can be moved when something else on the machine holds these.
const WEB_PORT = process.env.E2E_WEB_PORT ?? "3100";
const API_PORT = process.env.E2E_API_PORT ?? "8100";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  forbidOnly: Boolean(process.env.CI),
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: `http://127.0.0.1:${WEB_PORT}`,
    acceptDownloads: true,
    launchOptions: process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {},
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    {
      name: "mobile-dark",
      use: { ...devices["Desktop Chrome"], viewport: { width: 375, height: 800 }, colorScheme: "dark" },
    },
  ],
  // Never reuse a running server: one on these ports could be a real API.
  webServer: [
    {
      command: `uv run python tests/fake_server.py ${API_PORT}`,
      cwd: "../backend",
      url: `http://127.0.0.1:${API_PORT}/api/health`,
      reuseExistingServer: false,
      env: { CORS_ORIGINS: `http://127.0.0.1:${WEB_PORT}`, FAKE_DELAY_SECONDS: "1" },
    },
    {
      // The API address is baked in at build time, so build against the fake one.
      command: `pnpm exec next build && pnpm exec next start --hostname 127.0.0.1 --port ${WEB_PORT}`,
      url: `http://127.0.0.1:${WEB_PORT}`,
      reuseExistingServer: false,
      timeout: 240_000,
      env: { NEXT_PUBLIC_API_BASE_URL: `http://127.0.0.1:${API_PORT}`, NEXT_DIST_DIR: ".next-e2e" },
    },
  ],
});
