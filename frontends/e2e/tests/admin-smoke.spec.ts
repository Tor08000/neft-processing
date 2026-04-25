import { test, expect } from "playwright/test";
import { ADMIN_BASE_URL, loginAdmin, portalUrl } from "./helpers";

test("@smoke admin portal login", async ({ page }) => {
  await loginAdmin(page);
  await page.goto(portalUrl(ADMIN_BASE_URL, "/"));
  await expect(page.locator("nav, aside, [data-testid='sidebar']").first()).toBeVisible();
});
