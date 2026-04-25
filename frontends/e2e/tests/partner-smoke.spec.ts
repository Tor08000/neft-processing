import { test, expect } from "playwright/test";
import { PARTNER_BASE_URL, loginPartner, portalUrl } from "./helpers";

test("@smoke partner portal login", async ({ page }) => {
  await loginPartner(page);
  await page.goto(portalUrl(PARTNER_BASE_URL, "/dashboard"));
  await expect(page.locator("nav, aside, [data-testid='sidebar']").first()).toBeVisible();
});
