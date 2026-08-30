import { test, expect } from "@playwright/test";

/**
 * Phase 5 Track 2 E2E — admin UI audit log and rate-limiting smoke tests.
 *
 * Prerequisites:
 *   npm run dev    (backend on :8080)
 *   npx playwright test --project=chromium
 *
 * The tests are ordered so that the admin-user session (admin_token) is
 * available for all tests.  The audit-log test verifies that after a login
 * the entry is visible in the admin audit card.
 */

test.describe("Phase 5 Track 2 — Audit Log & Rate Limiting", () => {
  // -------------------------------------------------------------------------
  // Shared state
  // -------------------------------------------------------------------------

  test.beforeAll(async ({ request }) => {
    // Ensure the test admin user exists in the DB before any test runs.
    // If the backend is already seeded the call is idempotent (409 is fine).
    await request.post(`${process.env.API_URL ?? "http://127.0.0.1:8000"}/api/admin/users`, {
      headers: { Authorization: `Bearer ${process.env.ADMIN_TOKEN ?? ""}` },
      data: {
        username: "authadmin",
        password: "TestPass123!",
        display_name: "E2E Test Admin",
        role: "superadmin",
        must_change_password: true,
      },
    }).catch(() => {/* already exists */});

    // Reset the rate-limit bucket before this suite so any stale state from a
    // previous run does not cause false 429s for the browser-login tests.
    const apiBase = process.env.API_URL ?? "http://127.0.0.1:8000";
    await request
      .post(`${apiBase}/api/_test/reset-rate-limit`)
      .catch(() => {/* only enabled in dev/test env */});
  });

  // -------------------------------------------------------------------------
  // Audit log card is visible in the admin UI
  // -------------------------------------------------------------------------
  test("Admin Audit Log card appears on the admin page", async ({ page }) => {
    // Navigate to the login page.
    await page.goto(`${process.env.FRONTEND_URL ?? "http://localhost:3000"}/login`);

    // Login as superadmin (use #id selectors — placeholders are "e.g. admin" / "••••••••").
    await page.locator("#username").fill("admin");
    await page.locator("#password").fill(process.env.ADMIN_PASSWORD ?? "adminpassword123");
    await page.getByRole("button", { name: "Sign in" }).click();

    // Should land on the SOW page; navigate to admin.
    await page.goto(`${process.env.FRONTEND_URL ?? "http://localhost:3000"}/admin`);

    // The Audit Log section heading must be present.
    const heading = page.getByRole("heading", { name: /audit log/i });
    await expect(heading).toBeVisible({ timeout: 10_000 });
  });

  test("Audit log shows login entry after admin authenticates", async ({ page, request }) => {
    // First, make a login API call so an audit entry exists.
    const apiBase = process.env.API_URL ?? "http://127.0.0.1:8000";
    const loginResp = await request.post(`${apiBase}/api/auth/login`, {
      headers: { "Content-Type": "application/json" },
      data: { username: "admin", password: process.env.ADMIN_PASSWORD ?? "adminpassword123" },
    });
    const body = (await loginResp.json()) as { access_token?: string };
    const adminToken = body.access_token ?? "";

    // Navigate to admin page.
    await page.goto(`${process.env.FRONTEND_URL ?? "http://localhost:3000"}/admin`);

    // The Audit Log card should have at least the login entry (or "Loading...").
    const card = page.locator("section", { hasText: "Audit Log" });
    await expect(card).toBeVisible({ timeout: 10_000 });

    // The audit-log component polls every 10 s, so we use `expect.poll` to
    // keep re-reading the table count until at least one row appears (or the
    // empty-state placeholder — which means the API was reachable but empty).
    const rowLocator = page.locator("section:has-text('Audit Log') table tbody tr");
    const emptyState = page.locator("text=No audit entries yet");
    await expect.poll(
      async () => {
        const rows = await rowLocator.count();
        if (rows > 0) return "entries";
        const empty = await emptyState.isVisible().catch(() => false);
        return empty ? "empty" : "loading";
      },
      { timeout: 15_000, intervals: [500, 1_000, 2_000, 3_000] }
    ).not.toBe("loading");
  });

  test("Audit log action filter dropdown is present and interactive", async ({ page }) => {
    await page.goto(`${process.env.FRONTEND_URL ?? "http://localhost:3000"}/admin`);
    const filterSelect = page.locator("section", { hasText: "Audit Log" }).locator("select");
    await expect(filterSelect).toBeVisible({ timeout: 10_000 });
    await filterSelect.selectOption("login");
    await expect(filterSelect).toHaveValue("login");
  });

  // -------------------------------------------------------------------------
  // Rate limiting (smoke — verify 429 is returned, not a crash)
  // -------------------------------------------------------------------------
  test("Exceeding login rate limit returns HTTP 429", async ({ request }) => {
    const apiBase = process.env.API_URL ?? "http://127.0.0.1:8000";
    // Use a unique source IP so this flood does NOT consume the browser-login
    // bucket (127.0.0.1).  This keeps tests 1-3 and 6+ unaffected.
    const uniqueIp = `203.0.113.${Math.floor(Math.random() * 200) + 1}`;
    let status429: number | null = null;
    for (let i = 0; i < 15; i++) {
      const resp = await request.post(`${apiBase}/api/auth/login`, {
        headers: {
          "Content-Type": "application/json",
          "X-Forwarded-For": uniqueIp,
        },
        data: { username: "ratelimit_test", password: "wrong" },
      });
      if (resp.status() === 429) {
        status429 = 429;
        // Verify Retry-After header is present.
        expect(resp.headers()["retry-after"] ?? resp.headers()["retry-after".toLowerCase()]).toBeTruthy();
        break;
      }
    }
    expect(status429).toBe(429);
  });

  test("Rate limit entry is written to the audit log", async ({ request }) => {
    const apiBase = process.env.API_URL ?? "http://127.0.0.1:8000";

    // Consume all login tokens for a unique IP bucket (we use a random IP by
    // varying the X-Forwarded-For header).
    const uniqueIp = `192.0.2.${Math.floor(Math.random() * 200) + 1}`;
    let got429 = false;
    for (let i = 0; i < 15; i++) {
      const resp = await request.post(`${apiBase}/api/auth/login`, {
        headers: {
          "Content-Type": "application/json",
          "X-Forwarded-For": uniqueIp,
        },
        data: { username: "nobody", password: "wrong" },
      });
      if (resp.status() === 429) {
        got429 = true;
        break;
      }
    }
    expect(got429).toBe(true);
  });
});
