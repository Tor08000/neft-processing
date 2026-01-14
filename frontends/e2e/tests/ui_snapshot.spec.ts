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
} from "./helpers";

test.describe.serial("UI Snapshot (Gateway/Direct)", () => {
  const baseUrls = resolveBaseUrls();
  const report = createReportState(baseUrls);

  test.afterAll(() => {
    const reportPath = writeReport(report);
    const failedRoutes = (["admin", "client", "partner"] as const).flatMap((app) =>
      report.routes[app].filter((route) => route.status.startsWith("FAIL")),
    );
    if (report.errors.length > 0 || failedRoutes.length > 0) {
      const details = [
        report.errors.length > 0 ? `Errors: ${report.errors.join("; ")}` : null,
        failedRoutes.length > 0
          ? `Failed routes: ${failedRoutes.map((route) => `${route.id} (${route.status})`).join(", ")}`
          : null,
      ]
        .filter(Boolean)
        .join("\n");
      throw new Error(`UI snapshot failures detected. See ${reportPath}.\n${details}`);
    }
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
