import { test, expect } from "@playwright/test";
import { ADMIN_BASE_URL, loginAdmin } from "./helpers";

test("@smoke admin portal login", async ({ page }) => {
  await loginAdmin(page);
  await page.goto(`${ADMIN_BASE_URL}/dashboard`);
  await expect(page.locator("nav, aside, [data-testid='sidebar']").first()).toBeVisible();
});
