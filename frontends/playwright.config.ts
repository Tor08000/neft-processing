import { defineConfig } from "@playwright/test";

const viewportOverride = process.env.UI_SNAPSHOT_VIEWPORT;
const defaultViewport = { width: 1440, height: 900 };

const viewport = viewportOverride
  ? (() => {
      const [width, height] = viewportOverride.split("x").map((value) => Number.parseInt(value, 10));
      if (Number.isFinite(width) && Number.isFinite(height)) {
        return { width, height };
      }
      return defaultViewport;
    })()
  : defaultViewport;

const headless = process.env.UI_SNAPSHOT_HEADLESS === "0" ? false : true;

export default defineConfig({
  testDir: "./e2e/tests",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  workers: 1,
  reporter: [["list"]],
  projects: [
    {
      name: "chromium",
      use: {
        headless,
        viewport,
        screenshot: "off",
      },
    },
  ],
});
