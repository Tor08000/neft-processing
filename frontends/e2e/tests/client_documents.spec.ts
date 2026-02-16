import { expect, test } from "@playwright/test";

test("client outbound documents smoke: create + upload + download button", async ({ page }) => {
  await page.goto("/client/documents");
  await expect(page.getByRole("heading", { name: "Документы" })).toBeVisible();

  await page.getByRole("button", { name: "Исходящие" }).click();
  await page.getByRole("button", { name: "Создать документ" }).click();

  await page.getByPlaceholder("Название").fill("E2E OUTBOUND ACT");
  await page.getByRole("button", { name: "Создать" }).click();

  await expect(page.getByText("Загрузить файл")).toBeVisible();
  await page.locator("#file-upload").setInputFiles({
    name: "fixture.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("pdf"),
  });

  await expect(page.getByText("fixture.pdf")).toBeVisible();
  await expect(page.getByRole("button", { name: "Download" })).toBeVisible();
});
