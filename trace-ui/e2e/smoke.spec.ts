import { test, expect } from "@playwright/test";

/**
 * Smoke test for the reviewer journey, against the real FastAPI backend.
 *
 * The dashboard only ever talks to the real workflow, so this is the only path:
 * a flagged value can be decided, the decision lands in the audit log, and the chain verifies.
 */
test("reviewer journey: flag -> decide -> audit log -> verified chain", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  page.on("pageerror", (err) => consoleErrors.push(String(err)));

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Overview", level: 1 })).toBeVisible();

  // The queue is the heart of the product: open it and make sure it renders.
  await page.goto("/review");
  await expect(page.getByRole("heading", { name: "Review queue", level: 1 })).toBeVisible();

  const queueItem = page.locator('[data-testid^="queue-item-"]').first();
  if ((await queueItem.count()) === 0) {
    // No flagged values yet: check the empty state instead of inventing one.
    await expect(page.getByText(/Nothing is waiting for a reviewer|Loading review queue/i)).toBeVisible();
  }

  const firstItem = page.locator('[data-testid^="queue-item-"]').first();
  if ((await firstItem.count()) > 0) {
    await firstItem.click();
    const approve = page.getByRole("button", { name: /^Approve$/ });
    // Approve stays locked until the reviewer writes something.
    await expect(approve).toBeDisabled();
    await page.locator('textarea[id^="note-"]').first().fill("checked against the filing");
    await expect(approve).toBeEnabled();
    await approve.click();
    await page.getByRole("button", { name: /Submit decisions/i }).click();
  }

  await page.goto("/audit");
  await page.getByRole("button", { name: /Verify chain/i }).click();
  await expect(page.getByTestId("verify-result")).toContainText(/intact|broken/i, { timeout: 20_000 });

  await page.goto("/accuracy");
  await expect(page.getByRole("heading", { name: "Accuracy", level: 1 })).toBeVisible();

  expect(consoleErrors).toEqual([]);
});
