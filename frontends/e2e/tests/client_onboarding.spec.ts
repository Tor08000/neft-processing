import { test, expect } from "@playwright/test";
import { CLIENT_BASE_URL, expectHeading, loginClient } from "./utils";

test("client dashboard opens with summary or empty state", async ({ page }) => {
  await loginClient(page);
  await page.goto(`${CLIENT_BASE_URL}/dashboard`);

  await expectHeading(page, /Обзор клиента/i);

  const kpiCards = page.locator(".kpi-card");
  if ((await kpiCards.count()) >= 2) {
    await expect(kpiCards.first()).toBeVisible();
  } else {
    await expect(page.getByText(/Нет данных для обзора/i)).toBeVisible();
  }
});
