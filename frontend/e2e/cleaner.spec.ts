import { readFile } from "node:fs/promises";

import { expect, type Page, test } from "@playwright/test";

async function cleanSample(page: Page) {
  await page.goto("/");
  await page.getByRole("button", { name: /Signed form with a photo/ }).click();
  await expect(page.getByText("signed-form.jpg")).toBeVisible();
  await page.getByRole("button", { name: "Clean screenshot" }).click();
  await expect(page.getByRole("tablist", { name: "Result" })).toBeVisible();
}

async function download(page: Page, button: ReturnType<Page["getByRole"]>) {
  const pending = page.waitForEvent("download");
  await button.click();
  const file = await pending;
  return { name: file.suggestedFilename(), body: await readFile((await file.path()) ?? "") };
}

test.beforeEach(({ page }) => {
  page.on("console", (message) => {
    if (message.type() === "error") {
      throw new Error(`Console error: ${message.text()}`);
    }
  });
});

test("a sample goes through every tab, and each download produces a file", async ({ page }) => {
  await cleanSample(page);

  const overview = page.getByRole("tabpanel", { name: "Overview" });
  await expect(overview.getByRole("button", { name: /Stamp.*1 found/ })).toBeVisible();
  await expect(overview.getByRole("button", { name: /Signature.*1 found/ })).toBeVisible();
  await expect(overview.getByTestId("highlight")).toHaveCount(0);
  await overview.getByRole("button", { name: /Signature.*1 found/ }).hover();
  await expect(overview.getByTestId("highlight")).toHaveCount(1);
  await overview.getByRole("slider", { name: "Compare the original with the SAM overlay" }).fill("20");
  const overlay = await download(page, overview.getByRole("button", { name: "Download overlay PNG" }));
  expect(overlay.name).toBe("signed-form.overlay.png");
  expect(overlay.body.subarray(1, 4).toString()).toBe("PNG");

  await page.getByRole("tab", { name: "Text" }).click();
  const text = page.getByRole("tabpanel", { name: "Text" });
  await expect(text.getByText("Signature", { exact: true })).toBeVisible();
  const markdown = await download(page, text.getByRole("button", { name: "Download Markdown" }));
  expect(markdown.name).toBe("signed-form.cleaned.md");
  expect(markdown.body.toString()).toContain("Signature of applicant");

  await page.getByRole("tab", { name: "Data" }).click();
  const data = page.getByRole("tabpanel", { name: "Data" });
  await expect(data.getByText("Form", { exact: true })).toBeVisible();
  await expect(data.getByRole("row", { name: /Membership.*not found in text/ })).toBeVisible();
  const csv = await download(page, data.getByRole("button", { name: "Download CSV" }));
  expect(csv.name).toBe("signed-form.data.csv");
  expect(csv.body.toString()).toContain('"Full name","Daniel Okafor"');
  const json = await download(page, data.getByRole("button", { name: "Download JSON" }));
  expect(JSON.parse(json.body.toString()).document.type).toBe("form");

  await page.getByRole("tab", { name: "Share-safe" }).click();
  const share = page.getByRole("tabpanel", { name: "Share-safe" });
  await expect(share.getByText("Full name: [NAME]")).toBeVisible();
  await share.getByRole("slider", { name: "Compare the original with the share-safe copy" }).fill("0");
  const safe = await download(page, share.getByRole("button", { name: "Download share-safe image" }));
  expect(safe.name).toBe("signed-form.safe.png");
  expect(safe.body.subarray(1, 4).toString()).toBe("PNG");

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth,
  );
  expect(overflow).toBe(false);
});

test("tabs follow the arrow, Home, and End keys", async ({ page }) => {
  await cleanSample(page);
  const overview = page.getByRole("tab", { name: "Overview" });
  await overview.focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("tab", { name: "Text" })).toBeFocused();
  await expect(page.getByRole("tab", { name: "Text" })).toHaveAttribute("aria-selected", "true");
  await page.keyboard.press("End");
  await expect(page.getByRole("tab", { name: "Share-safe" })).toBeFocused();
  await page.keyboard.press("ArrowRight");
  await expect(overview).toBeFocused();
  await page.keyboard.press("ArrowLeft");
  await expect(page.getByRole("tabpanel", { name: "Share-safe" })).toBeVisible();
});

test("focusing a region chip outlines its boxes", async ({ page }) => {
  await cleanSample(page);
  const panel = page.getByRole("tabpanel", { name: "Overview" });
  await panel.getByRole("button", { name: /Stamp.*1 found/ }).focus();
  await expect(panel.getByTestId("highlight")).toHaveCount(1);
  await expect(panel.getByRole("button", { name: /Rectangle.*none found/ })).toBeDisabled();
});

test("empty tabs say how to fill them", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /Chat screenshot/ }).click();
  await page.getByRole("checkbox", { name: "Pull out the document type and key fields" }).uncheck();
  for (const name of ["Signature", "Photograph"]) {
    await page.getByRole("group", { name: "Share-safe copy" }).getByRole("checkbox", { name }).uncheck();
  }
  await page
    .getByRole("checkbox", { name: /Also hide phone numbers/ })
    .uncheck();
  await page.getByRole("button", { name: "Clean screenshot" }).click();
  await page.getByRole("tab", { name: "Data" }).click();
  await expect(page.getByText(/Data was not requested/)).toBeVisible();
  await page.getByRole("tab", { name: "Share-safe" }).click();
  await expect(page.getByText(/Nothing was hidden in this run/)).toBeVisible();
});

test("cancel returns the page to idle", async ({ page }) => {
  await page.route("**/api/process", () => {
    // Never answer, so the request stays in flight until it is cancelled.
  });
  await page.goto("/");
  await page.getByRole("button", { name: /Invoice with a PAID stamp/ }).click();
  await page.getByRole("button", { name: "Clean screenshot" }).click();
  await expect(page.getByRole("button", { name: "Cleaning…" })).toBeDisabled();
  await page.getByRole("button", { name: "Cancel" }).click();
  await expect(page.getByRole("button", { name: "Clean screenshot" })).toBeEnabled();
  await expect(page.getByRole("tablist", { name: "Result" })).toHaveCount(0);
});

test("a blocked custom region is explained before anything is sent", async ({ page }) => {
  await page.goto("/");
  const field = page.getByLabel("Find something else (up to 3)");
  await field.fill("receipt");
  await field.press("Enter");
  await expect(page.locator("#custom-error")).toHaveText(
    "SAM marks objects, not text. Try a stamp, logo, or QR code.",
  );
});
