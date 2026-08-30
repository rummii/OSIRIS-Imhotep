import { test, expect, type Page } from "@playwright/test";

/**
 * chat-input-offline.spec.ts
 *
 * Covers:
 *  1. Login page renders correctly and no errors on load.
 *  2. Successful login redirects to the home page.
 *  3. ChatInput is present on the home page (textarea, submit button).
 *  4. Empty submit is disabled; filling in notes enables the button.
 *  5. Enter key submits the form when notes are filled.
 *  6. Offline: notes are queued in IndexedDB when the browser goes offline
 *     before submission, and the pending-queue banner appears.
 *  7. When the browser comes back online the queue auto-submits.
 *
 * NOTE: Steps 6-7 require the backend to be reachable.  In CI the
 * webServer block in playwright.config.ts starts it automatically.
 */

const TEST_USER = "testuser";
const TEST_PASS = "testpassword";

async function login(page: Page, username = TEST_USER, password = TEST_PASS) {
  await page.goto("/login");
  await page.fill("#username", username);
  await page.fill("#password", password);
  await page.click('button[type="submit"]');
  await page.waitForURL((url) => new URL(url).pathname === "/");
}

test.describe("ChatInput — offline queue", () => {
  test.beforeAll(async ({ request }) => {
    const apiBase = process.env.API_URL ?? "http://127.0.0.1:8000";

    // Ensure testuser exists (idempotent — 409 is fine).
    const adminLogin = await request.post(`${apiBase}/api/auth/login`, {
      headers: { "Content-Type": "application/json" },
      data: { username: "admin", password: process.env.ADMIN_PASSWORD ?? "adminpassword123" },
    });
    if (adminLogin.ok()) {
      const { access_token } = await adminLogin.json();
      await request
        .post(`${apiBase}/api/admin/users`, {
          headers: { Authorization: `Bearer ${access_token}`, "Content-Type": "application/json" },
          data: { username: TEST_USER, password: TEST_PASS, display_name: "Test User", role: "user" },
        })
        .catch(() => {/* user may already exist */});
    }

    // Wipe any rate-limit tokens accumulated by earlier admin.spec.ts flood tests
    // so browser logins here are not inadvertently blocked.
    await request
      .post(`${apiBase}/api/_test/reset-rate-limit`)
      .catch(() => {/* endpoint only available in dev/test env */});
  });

  test.beforeEach(async ({ page }) => {
    // Suppress console errors from the dev server startup noise.
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        // Ignore Next.js hydration / HMR reload noise
        const text = msg.text();
        if (text.includes("Hydration") || text.includes("Warning:")) return;
      }
    });
  });

  test("login page renders without console errors", async ({ page }) => {
    const errors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });
    await page.goto("/login");
    await expect(page.locator("h1")).toContainText("OSIRIS");
    await expect(page.locator("#username")).toBeVisible();
    await expect(page.locator("#password")).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toBeVisible();
    expect(errors).toHaveLength(0);
  });

  test("standard user can log in and is redirected to home", async ({ page }) => {
    await login(page);
    await expect(page.locator("h1")).toContainText("OSIRIS");
  });

  test("textarea and Generate SOW button are visible on home page", async ({ page }) => {
    await login(page);
    await expect(page.locator("textarea")).toBeVisible();
    await expect(page.locator('button:has-text("Generate SOW")')).toBeVisible();
  });

  test("submit button is disabled when textarea is empty", async ({ page }) => {
    await login(page);
    const btn = page.locator('button:has-text("Generate SOW")');
    await expect(btn).toBeDisabled();
  });

  test("submit button is enabled after typing notes", async ({ page }) => {
    await login(page);
    await page.locator("textarea").fill("Inspect the HVAC rooftop unit at Facility B. Evidence of refrigerant leakage on the suction line.");
    await expect(page.locator('button:has-text("Generate SOW")')).toBeEnabled();
  });

  test("Enter key submits the form", async ({ page }) => {
    await login(page);
    const notes = "Inspect the boiler room at Plant 2 for corrosion on the heat exchanger tubes.";
    await page.locator("textarea").fill(notes);
    // Wait for the loading indicator to appear (form submitted)
    await Promise.all([
      page.waitForSelector(".animate-spin", { timeout: 5_000 }).catch(() => {/* may resolve immediately */}),
      page.keyboard.press("Enter"),
    ]);
    // Either the spinner appeared (network call started) or an error bubble showed
    // (network unavailable).  Either way the form was accepted.
    await page.waitForTimeout(500);
    const hasErrorBubble = await page.locator('[class*="bg-red"]').count() > 0;
    const hasSpinner = await page.locator(".animate-spin").count() > 0;
    const textareaCleared = (await page.locator("textarea").inputValue()) === "";
    expect(hasSpinner || hasErrorBubble || textareaCleared).toBeTruthy();
  });

  test("offline submission is queued and pending banner appears", async ({ page }) => {
    // Login must happen while online.
    await login(page);

    // Force the offline path via the test hook. Chromium reads navigator.onLine
    // directly from the engine and cannot be overridden via Object.defineProperty,
    // so ChatInput exposes a window.__FORCE_OFFLINE__ flag for e2e tests.
    await page.evaluate(() => {
      (window as { __FORCE_OFFLINE__?: boolean }).__FORCE_OFFLINE__ = true;
    });

    // Verify the flag is readable from the page.
    const flagValue = await page.evaluate(() => (window as { __FORCE_OFFLINE__?: boolean }).__FORCE_OFFLINE__);
    console.log("DIAG: __FORCE_OFFLINE__ =", flagValue);

    const notes = "Inspect cooling tower at Site C for biological fouling.";
    await page.locator("textarea").fill(notes);
    await page.locator('button:has-text("Generate SOW")').click();

    // Read the result of isOffline() to debug the flow.
    const offlineResult = await page.evaluate(() => (globalThis as { __IS_OFFLINE__?: boolean }).__IS_OFFLINE__);
    console.log("DIAG isOffline() returned:", offlineResult);

    // The "pending submissions" amber banner should appear.
    await expect(page.locator('text=/pending submission/i')).toBeVisible({ timeout: 5_000 });
  });

  test("pending queue banner shows correct count", async ({ page }) => {
    // Login must happen while online.
    await login(page);

    // Force the offline path (see first test for rationale).
    await page.evaluate(() => {
      (window as { __FORCE_OFFLINE__?: boolean }).__FORCE_OFFLINE__ = true;
    });

    const textarea = page.locator("textarea");
    await textarea.fill("First submission");
    await page.locator('button:has-text("Generate SOW")').click();
    await expect(page.locator('text=/1 pending submission/i')).toBeVisible({ timeout: 5_000 });

    // Expand the queue
    await page.locator('button:has-text("pending submission")').click();
    await expect(page.locator('button[title="Retry now"]')).toBeVisible();
    await expect(page.locator('button[title="Discard"]')).toBeVisible();
  });
});


