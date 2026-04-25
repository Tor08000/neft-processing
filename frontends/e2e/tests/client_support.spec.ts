import { test } from "playwright/test";
import { CLIENT_BASE_URL, expectHeading, expectTableOrEmptyState, loginClient } from "./helpers";

test("client support requests list loads", async ({ page }) => {
  await loginClient(page);
  await page.goto(`${CLIENT_BASE_URL}/client/support`);

  await expectHeading(page, /Поддержка/i);
  await expectTableOrEmptyState(page);
});
