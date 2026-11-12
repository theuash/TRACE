import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  retries: 0,
  fullyParallel: false,
  use: {
    baseURL: "http://localhost:5173",
    viewport: { width: 1440, height: 900 },
    channel: "chrome",
  },
  webServer: {
    command: "npm run dev",
    url: "http://localhost:5173",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
