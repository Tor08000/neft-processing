import { test } from "playwright/test";
import { CLIENT_BASE_URL, expectHeading, loginClient } from "./helpers";

test("client legal page is reachable", async ({ page }) => {
  await loginClient(page);
  await page.goto(`${CLIENT_BASE_URL}/legal`);

  await expectHeading(page, /Юридические документы/i);
  await page.getByText(/обязательные документы/i).first().waitFor();
});
