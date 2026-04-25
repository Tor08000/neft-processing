import { test, expect } from "playwright/test";
import { CLIENT_BASE_URL, loginClient } from "./helpers";

test("@smoke client auth me returns 200 after login", async ({ page }) => {
  await loginClient(page);

  const meResponse = await page.request.get("http://localhost/api/v1/auth/me", {
    headers: {
      Authorization: `Bearer ${await page.evaluate(() => localStorage.getItem("access_token") ?? "")}`,
      "X-Portal": "client",
    },
  });

  expect(meResponse.status()).toBe(200);
  await page.goto(`${CLIENT_BASE_URL}/`);
  await expect(page).not.toHaveURL(/\/login/);
});
