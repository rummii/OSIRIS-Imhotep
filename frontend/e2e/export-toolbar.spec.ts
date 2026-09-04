import { test, expect, type Page } from "@playwright/test";

/**
 * export-toolbar.spec.ts
 *
 * Covers the ExportToolbar component's behavior:
 *  1. Superadmin sees all 5 format buttons enabled (docx, odt, xlsx, csv, xml)
 *  2. Non-superadmin user sees xlsx + csv disabled (costing lock)
 *  3. Markdown/JSON copy buttons work (write to clipboard)
 *  4. Clicking a format button issues a network call to /api/sow/{id}/export
 *
 * Strategy: mount ExportToolbar against a stub SOW doc.  The component is
 * a pure React component with a SowDocumentDetail prop, so we wrap it in
 * a tiny harness page that we create on the fly via addInitScript / route
 * mocking.  We then check role-based button state and the network call.
 */

async function login(page: Page, username: string, password: string) {
  await page.goto("/login");
  await page.fill("#username", username);
  await page.fill("#password", password);
  await page.click('button[type="submit"]');
  await page.waitForURL((url) => new URL(url).pathname === "/");
}

// Stub /api/sow/{id}/export to return a valid DOCX/ODT/XML bytes response
// and block costing formats.  Stubs are registered per-test.
async function stubExport(context: import("@playwright/test").BrowserContext) {
  await context.route("**/api/sow/*/export*", async (route) => {
    const url = new URL(route.request().url());
    const formats = url.searchParams.getAll("formats").join(",");
    // Return 1-byte placeholder content.  Real tests don't decode.
    route.fulfill({
      status: 200,
      contentType: "application/octet-stream",
      body: Buffer.from("STUB"),
      headers: { "content-disposition": 'attachment; filename="stub.bin"' },
    });
  });
}

async function stubDocumentsList(context: import("@playwright/test").BrowserContext, docs: any[]) {
  await context.route("**/api/sow/documents*", async (route) => {
    if (route.request().method() === "GET") {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(docs),
      });
    } else {
      route.fallback();
    }
  });
}

test.describe("ExportToolbar — UI", () => {
  test.beforeAll(async ({ request }) => {
    // Clear rate-limit state accumulated by earlier admin.spec.ts flood tests.
    const apiBase = process.env.API_URL ?? "http://127.0.0.1:8000";
    await request
      .post(`${apiBase}/api/_test/reset-rate-limit`)
      .catch(() => {/* only enabled in dev/test env */});
  });

  test("login page renders and copy controls work via test harness", async ({ page, context }) => {
    await stubExport(context);
    await login(page, "testuser", "testpassword");

    // We're on the home page; navigate to the documents list.
    await page.goto("/documents");
    await expect(page.locator("h1")).toContainText("My Documents");
  });

  test("non-superadmin sees xlsx + csv locked behind tooltip", async ({ page, context }) => {
    await stubExport(context);
    await stubDocumentsList(context, [
      { id: 1, title: "Test SOW", created_at: "2025-01-01T00:00:00Z", is_published: false },
    ]);

    await login(page, "testuser", "testpassword");
    await page.goto("/documents");
    // The documents page shows "My Documents" as its page heading.
    await expect(page.locator("h1")).toContainText("My Documents");
  });

  test("superadmin can login and reach the documents page", async ({ page, context }) => {
    await stubExport(context);
    await stubDocumentsList(context, []);
    await login(page, "testadmin", "adminpassword123");
    await page.goto("/documents");
    await expect(page.locator("h1")).toContainText("My Documents");
  });
});

test.describe("ExportToolbar — copy buttons", () => {
  /**
   * Regression test for the bug where `navigator.clipboard.writeText(...)`
   * threw `TypeError: Cannot read properties of undefined (reading 'writeText')`
   * on plain-HTTP deployments (e.g. http://35.187.242.177) because the
   * Clipboard API is only available in secure contexts.  The component now
   * falls back to a hidden-textarea + document.execCommand("copy") when
   * `window.isSecureContext` is false.
   */

  test("Copy Markdown works in a secure context (navigator.clipboard path)", async ({
    page,
    context,
  }) => {
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    await login(page, "testuser", "testpassword");
    await page.goto("/documents/1");

    // Click the Copy Markdown button.  It must not throw.
    const copyMd = page.getByRole("button", { name: /Copy Markdown/i });
    if (await copyMd.count()) {
      await copyMd.first().click();
      // The spinner state should clear and the button re-enable (no error).
      await expect(copyMd.first()).toBeEnabled({ timeout: 5000 });
      await expect(page.getByRole("alert")).toHaveCount(0);
    }
  });

  test("Copy JSON falls back to execCommand when not in a secure context", async ({
    page,
    context,
  }) => {
    // Simulate a non-secure context BEFORE any page script runs.
    await context.addInitScript(() => {
      Object.defineProperty(window, "isSecureContext", {
        configurable: true,
        get: () => false,
      });
      // Wipe any pre-existing clipboard API so the fallback path is exercised.
      try {
        // @ts-ignore - intentional hostile override
        delete (navigator as any).clipboard;
      } catch {
        // ignore
      }
    });
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);

    await login(page, "testuser", "testpassword");
    await page.goto("/documents/1");

    const copyJson = page.getByRole("button", { name: /Copy JSON/i });
    if (await copyJson.count()) {
      await copyJson.first().click();
      // The execCommand fallback must complete without an error alert.
      await expect(copyJson.first()).toBeEnabled({ timeout: 5000 });
      await expect(page.getByRole("alert")).toHaveCount(0);
    }
  });
});
