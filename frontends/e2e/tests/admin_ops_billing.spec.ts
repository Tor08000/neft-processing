import { test } from "@playwright/test";
import { ADMIN_BASE_URL, expectHeading, loginAdmin } from "./utils";

test("admin billing overview loads", async ({ page }) => {
  await loginAdmin(page);
  await page.goto(`${ADMIN_BASE_URL}/billing`);

  await expectHeading(page, /Billing/i);
});
