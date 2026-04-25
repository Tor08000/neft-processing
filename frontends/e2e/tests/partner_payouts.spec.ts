import { test } from "playwright/test";
import { PARTNER_BASE_URL, expectHeading, expectTableOrEmptyState, loginPartner } from "./helpers";

test("partner payouts page loads", async ({ page }) => {
  await loginPartner(page);
  await page.goto(`${PARTNER_BASE_URL}/payouts`);

  await expectHeading(page, /Выплаты|Settlements/i);
  await expectTableOrEmptyState(page);
});
