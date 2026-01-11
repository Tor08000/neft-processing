import { test } from "@playwright/test";
import { CLIENT_BASE_URL, expectHeading, loginClient } from "./utils";

test("client reconciliation requests page loads", async ({ page }) => {
  await loginClient(page);
  await page.goto(`${CLIENT_BASE_URL}/finance/reconciliation`);

  await expectHeading(page, /Акты сверки/i);
  await page.getByRole("heading", { name: /Новый запрос/i }).waitFor();
});
