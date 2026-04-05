import { defineConfig } from "@playwright/test";

const targetApp = process.env.TARGET_APP === "desktop" ? "desktop" : "web";
const port = targetApp === "desktop" ? 1420 : 5173;
const appFilter = targetApp === "desktop" ? "@echoisle/desktop" : "@echoisle/web";
const baseURL = `http://127.0.0.1:${port}`;
const chatApiBase = `${baseURL}/api`;
const notifyEventsBase = `${baseURL}/events`;

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  expect: {
    timeout: 5_000
  },
  fullyParallel: true,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure"
  },
  webServer: {
    command: `VITE_CHAT_API_BASE=${chatApiBase} VITE_NOTIFY_EVENTS_BASE=${notifyEventsBase} pnpm --filter ${appFilter} dev --host 127.0.0.1 --port ${port}`,
    url: baseURL,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000
  }
});
