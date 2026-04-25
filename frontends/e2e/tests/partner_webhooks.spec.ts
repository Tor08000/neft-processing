import { test } from "playwright/test";
import { PARTNER_BASE_URL, expectHeading, expectTableOrEmptyState, loginPartner } from "./helpers";

test("partner integrations webhooks page loads", async ({ page }) => {
  await loginPartner(page);
  await page.goto(`${PARTNER_BASE_URL}/integrations`);

  await expectHeading(page, /Integrations|Интеграции|Webhooks/i);
  await expectTableOrEmptyState(page);
});
