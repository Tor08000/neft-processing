import { expect, test } from "playwright/test";
import { loginPartner, PARTNER_BASE_URL, portalUrl } from "./helpers";

test("@smoke partner finance mounted contracts and settlements routes", async ({ page }) => {
  const ownerCalls: string[] = [];
  page.on("request", (request) => {
    const path = new URL(request.url()).pathname;
    if (/\/api\/(?:core\/)?partner\/(?:contracts|settlements)(?:\/|$|\?)/.test(path)) {
      ownerCalls.push(`${request.method()} ${path}`);
    }
  });

  await loginPartner(page);

  await page.goto(portalUrl(PARTNER_BASE_URL, "/finance"));
  await expect(page.getByRole("heading", { name: "Read-only finance registers" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Contracts" })).toHaveAttribute("href", "/partner/contracts");
  await expect(page.getByRole("link", { name: "Settlements" })).toHaveAttribute("href", "/partner/settlements");

  await page.goto(portalUrl(PARTNER_BASE_URL, "/contracts"));
  await expect(page.getByRole("heading", { name: "Contracts" })).toBeVisible();

  await page.goto(portalUrl(PARTNER_BASE_URL, "/settlements"));
  await expect(page.getByRole("heading", { name: "Settlements" })).toBeVisible();

  expect(ownerCalls.some((call) => call.includes("/partner/contracts"))).toBe(true);
  expect(ownerCalls.some((call) => call.includes("/partner/settlements"))).toBe(true);
});
