import { test } from "@playwright/test";
import {
  ADMIN_ROUTES,
  CLIENT_ROUTES,
  CREDENTIALS,
  PARTNER_ROUTES,
  createReportState,
  resolveBaseUrls,
  runSnapshots,
  writeReport,
} from "./utils/ui_snapshot";

test.describe.serial("UI Snapshot (Gateway/Direct)", () => {
  const baseUrls = resolveBaseUrls();
  const report = createReportState(baseUrls);

  test.afterAll(() => {
    writeReport(report);
  });

  test("Admin UI snapshots", async ({ page }) => {
    await runSnapshots({
      page,
      app: "admin",
      baseUrl: baseUrls.admin,
      credentials: CREDENTIALS.admin,
      routes: ADMIN_ROUTES,
      report,
    });
  });

  test("Client UI snapshots", async ({ page }) => {
    await runSnapshots({
      page,
      app: "client",
      baseUrl: baseUrls.client,
      credentials: CREDENTIALS.client,
      routes: CLIENT_ROUTES,
      report,
    });
  });

  test("Partner UI snapshots", async ({ page }) => {
    await runSnapshots({
      page,
      app: "partner",
      baseUrl: baseUrls.partner,
      credentials: CREDENTIALS.partner,
      routes: PARTNER_ROUTES,
      report,
    });
  });
});
