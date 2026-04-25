import { test, expect } from "playwright/test";
import { CLIENT_BASE_URL, loginClient, portalUrl } from "./helpers";

test("@smoke client portal login", async ({ page }) => {
  await loginClient(page);
  await page.goto(portalUrl(CLIENT_BASE_URL, "/dashboard"));
  await expect(page.locator("nav, aside, [data-testid='sidebar']").first()).toBeVisible();
});
