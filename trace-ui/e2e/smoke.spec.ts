import { test, expect } from "@playwright/test";

test("trace end-to-end: run audit, decide, submit, verify chain", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  page.on("pageerror", (err) => consoleErrors.push(String(err)));

  await page.goto("/");
  await expect(page.getByTestId("data-mode")).toHaveText("Demo data");

  await page.goto("/new");
  await page.getByRole("button", { name: /Run audit/i }).click();
  await expect(page.getByText("Paused at checkpoint")).toBeVisible({ timeout: 40_000 });

  await page.getByRole("button", { name: /Open review queue/i }).click();
  await expect(page.getByTestId("queue-item-Revenue")).toBeVisible();

  await page.getByTestId("queue-item-Revenue").click();
  await page.getByRole("button", { name: /^Approve$/i }).click();
  await page.getByRole("button", { name: /Submit decisions/i }).click();

  await page.goto("/audit");
  await page.getByRole("button", { name: /Verify chain/i }).click();
  await expect(page.getByTestId("verify-result")).toContainText("intact", { timeout: 15_000 });

  expect(consoleErrors).toEqual([]);
});
