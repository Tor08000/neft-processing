import { test } from "@playwright/test";
import { CLIENT_BASE_URL, expectHeading, expectTableOrEmptyState, loginClient } from "./helpers";

test("client support requests list loads", async ({ page }) => {
  await loginClient(page);
  await page.goto(`${CLIENT_BASE_URL}/support/requests`);

  await expectHeading(page, /Запросы \/ Обращения/i);
  await expectTableOrEmptyState(page);
});
