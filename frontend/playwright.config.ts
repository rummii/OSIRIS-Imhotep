import { defineConfig, devices } from "@playwright/test";
import { readFileSync } from "fs";
import { resolve } from "path";

const envPath = resolve(process.cwd(), "../backend/.env");
const envContent = readFileSync(envPath, "utf-8");
const envVars: Record<string, string> = {};
for (const line of envContent.split("\n")) {
  const trimmed = line.trim();
  if (!trimmed || trimmed.startsWith("#")) continue;
  const idx = trimmed.indexOf("=");
  if (idx > 0) {
    envVars[trimmed.slice(0, idx)] = trimmed.slice(idx + 1);
  }
}

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [["html", { open: "never" }], ["list"]],
  use: {
    baseURL: "http://127.0.0.1:3000",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: [
    {
      command: "cd ../backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000",
      url: "http://127.0.0.1:8000/api/health",
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
      stdout: "pipe",
      stderr: "pipe",
      env: {
        SUPERADMIN_PASSWORD: envVars["SUPERADMIN_PASSWORD"] ?? "",
        JWT_SECRET: envVars["JWT_SECRET"] ?? "",
        DATABASE_URL: envVars["DATABASE_URL"] ?? "",
        APP_ENV: "development",
      },
    },
    {
      command: "npm run dev",
      url: "http://127.0.0.1:3000",
      reuseExistingServer: !process.env.CI,
      timeout: 90_000,  // next dev cold compile can take 22s+ on first run
      stdout: "pipe",
      stderr: "pipe",
    },
  ],
  // Pass API_URL and ADMIN_PASSWORD to the test process (used by admin.spec.ts and
  // chat-input-offline.spec.ts for request.post() calls against the backend).
  // Cast via `as unknown as` because Playwright's TypeScript types do not expose
  // this field but it is accepted at runtime.
  ...({ env: { API_URL: "http://127.0.0.1:8000", ADMIN_PASSWORD: envVars["SUPERADMIN_PASSWORD"] ?? "" } } as unknown as Record<string, unknown>),
});