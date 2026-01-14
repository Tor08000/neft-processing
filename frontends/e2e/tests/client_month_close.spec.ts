import { test } from "@playwright/test";
import { CLIENT_BASE_URL, expectHeading, expectTableOrEmptyState, loginClient } from "./helpers";

test("client documents page loads", async ({ page }) => {
  await loginClient(page);
  await page.goto(`${CLIENT_BASE_URL}/documents`);

  await expectHeading(page, /Документы|Documents/i);
  await expectTableOrEmptyState(page);
});
