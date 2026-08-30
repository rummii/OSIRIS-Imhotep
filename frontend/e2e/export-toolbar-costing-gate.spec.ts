import { test, expect, type Page } from "@playwright/test";

/**
 * export-toolbar-costing-gate.spec.ts
 *
 * Verifies the feature-gate wiring for costing-format exports (xlsx, csv).
 *
 * The server-side gate (EXPORT_COSTING_ENABLED env var → /api/admin/config)
 * controls whether costing buttons appear.  When the gate is closed the
 * ExportToolbar must hide (not merely disable) xlsx and csv.
 *
 * Strategy: use the real /documents/[id] page with route stubs for
 * /api/sow/{id} and /api/admin/config.
 */

async function login(page: Page, username = "testadmin", password = "adminpassword123") {
  await page.goto("/login");
  await page.fill("#username", username);
  await page.fill("#password", password);
  await page.click('button[type="submit"]');
  await page.waitForURL((url) => new URL(url).pathname === "/");
}

const STUB_DOC = {
  id: 999,
  user_id: 1,
  sow_id: 1,
  title: "Test HVAC SOW",
  content_md: "# Test",
  content_plain: '{"project_title":"Test HVAC SOW","generated_at":"2025-01-01T00:00:00Z","currency":"PHP","executive_summary":{"overview":"Test","overall_condition":"Good"},"visual_findings":[],"recommended_services":[],"scope_breakdown":[],"cost_breakdown":{"currency":"PHP","labor":1000,"materials":500,"equipment":200,"subtotal":1700,"contingency_pct":10,"contingency":170,"total":1870}}',
  created_at: "2025-01-01T00:00:00Z",
  updated_at: "2025-01-01T00:00:00Z",
  is_published: false,
  sow: null,
  spatial_context: null,
};

function stubConfig(context: import("@playwright/test").BrowserContext, costingEnabled: boolean) {
  context.route("**/api/admin/config", (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ export_costing_enabled: costingEnabled }),
    });
  });
}

function stubDocument(
  context: import("@playwright/test").BrowserContext,
  docId: number,
) {
  context.route(`**/api/sow/${docId}`, (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(STUB_DOC),
    });
  });
}

test.describe("ExportToolbar — costing gate", () => {
  test.beforeAll(async ({ request }) => {
    const apiBase = process.env.API_URL ?? "http://127.0.0.1:8000";
    await request
      .post(`${apiBase}/api/_test/reset-rate-limit`)
      .catch(() => {/* only enabled in dev/test env */});
  });

  test("costing enabled → xlsx and csv buttons are visible", async ({ page, context }) => {
    stubConfig(context, true);
    stubDocument(context, 999);
    await login(page);
    await page.goto("/documents/999");
    await expect(page.locator("text=Word")).toBeVisible();
    await expect(page.locator("text=Excel")).toBeVisible();
    await expect(page.locator("text=CSV")).toBeVisible();
  });

  test("costing disabled → xlsx and csv buttons are hidden (not disabled)", async ({ page, context }) => {
    stubConfig(context, false);
    stubDocument(context, 999);
    await login(page);
    await page.goto("/documents/999");
    await expect(page.locator("text=Word")).toBeVisible();
    // Costing buttons must not be rendered at all.
    await expect(page.locator("text=Excel")).not.toBeVisible();
    await expect(page.locator("text=CSV")).not.toBeVisible();
  });

  test("costing enabled + non-superadmin → xlsx/csv still hidden (no config access)", async ({
    page,
    context,
  }) => {
    stubConfig(context, false); // 403 / unreachable → defaults to hidden
    stubDocument(context, 999);
    await login(page, "testuser", "testpassword");
    await page.goto("/documents/999");
    await expect(page.locator("text=Word")).toBeVisible();
    await expect(page.locator("text=Excel")).not.toBeVisible();
    await expect(page.locator("text=CSV")).not.toBeVisible();
  });
});
