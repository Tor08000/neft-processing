import { test, expect } from "@playwright/test";
import { CLIENT_BASE_URL, loginClient } from "./helpers";

test("@smoke client invitations page opens", async ({ page }) => {
  await loginClient(page);
  await page.goto(`${CLIENT_BASE_URL}/controls?tab=users`);
  await expect(page.getByRole("heading", { name: "Приглашения" })).toBeVisible();
});
