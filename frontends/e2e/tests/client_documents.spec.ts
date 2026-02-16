import { expect, test } from "@playwright/test";

test("client documents page renders tabs and empty state", async ({ page }) => {
  await page.goto("/client/documents");
  await expect(page.getByRole("heading", { name: "Документы" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Входящие" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Исходящие" })).toBeVisible();
  await expect(page.getByText("Документов пока нет")).toBeVisible();
});
