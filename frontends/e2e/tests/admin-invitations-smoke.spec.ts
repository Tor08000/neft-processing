import { test, expect } from "playwright/test";
import { ADMIN_BASE_URL, loginAdmin } from "./helpers";

test("@smoke admin invitations page opens", async ({ page }) => {
  await loginAdmin(page);
  await page.goto(`${ADMIN_BASE_URL}/invitations`);
  await expect(page.getByRole("heading", { name: "Invitations" })).toBeVisible();
});
