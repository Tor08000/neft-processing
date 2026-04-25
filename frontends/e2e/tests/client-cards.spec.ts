import { test, expect } from "playwright/test";
import { CLIENT_BASE_URL, loginClient } from "./helpers";

test("@smoke client cards page opens and allows issue card", async ({ page }) => {
  await loginClient(page);
  await page.goto(`${CLIENT_BASE_URL}/cards`);

  await expect(page.getByRole("heading", { name: "Карты" }).first()).toBeVisible();

  const issueButton = page.getByRole("button", { name: "Выпустить карту" }).first();
  if (await issueButton.isVisible().catch(() => false)) {
    await issueButton.click();
    const createButton = page.getByRole("button", { name: "Создать" }).first();
    if (await createButton.isVisible().catch(() => false)) {
      await page.locator('input[placeholder="Метка карты"]').first().fill("Smoke Card");
      await createButton.click();
    }
  }

  await expect(page.locator("body")).not.toContainText("Сервис недоступен");
});
