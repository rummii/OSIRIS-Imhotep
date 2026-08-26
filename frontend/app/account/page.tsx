"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, KeyRound, Loader2 } from "lucide-react";
import { changePassword, fetchMe } from "@/lib/api";
import { clearAuth, getToken } from "@/lib/auth";

function AccountPage() {
  const router = useRouter();
  const params = useSearchParams();
  const forced = params.get("force") === "1";

  const [me, setMe] = useState<Record<string, unknown> | null>(null);
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    fetchMe()
      .then(setMe)
      .catch(() => {});
  }, [router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (next.length < 8) {
      setError("New password must be at least 8 characters.");
      return;
    }
    if (next !== confirm) {
      setError("New passwords do not match.");
      return;
    }
    setLoading(true);
    try {
      await changePassword(current, next);
      setSuccess(true);
      setCurrent("");
      setNext("");
      setConfirm("");
      if (forced) {
        setTimeout(() => router.replace("/"), 1200);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update password");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white px-4 py-3 sm:px-6">
        <div className="mx-auto flex max-w-2xl items-center justify-between">
          <button
            type="button"
            onClick={() => router.replace("/")}
            className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-900"
          >
            <ArrowLeft size={16} /> Back to workspace
          </button>
          <span className="text-sm font-semibold text-slate-900">Account settings</span>
        </div>
      </header>

      <main className="mx-auto max-w-2xl px-4 py-8 sm:px-6">
        {forced && (
          <div className="mb-5 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            Your administrator has reset your password — please set a new one before continuing.
          </div>
        )}

        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          {me && (
            <div className="mb-5 border-b border-slate-100 pb-4">
              <p className="text-sm font-semibold text-slate-900">
                {String(me.display_name || me.username)}
              </p>
              <p className="text-xs text-slate-500">
                @{String(me.username)} ·{" "}
                <span className="capitalize">{String(me.role)}</span>
              </p>
            </div>
          )}

          {success ? (
            <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
              Password updated successfully.
              {forced ? " Redirecting…" : ""}
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="flex items-center gap-2">
                <KeyRound size={16} className="text-slate-400" />
                <h2 className="text-sm font-semibold text-slate-900">Change password</h2>
              </div>

              <div>
                <label className="mb-1 block text-xs font-medium text-slate-600">Current password</label>
                <input
                  type="password"
                  required
                  autoComplete="current-password"
                  value={current}
                  onChange={(e) => setCurrent(e.target.value)}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm outline-none transition focus:border-blue-600 focus:ring-2 focus:ring-blue-100"
                />
              </div>

              <div>
                <label className="mb-1 block text-xs font-medium text-slate-600">New password</label>
                <input
                  type="password"
                  required
                  autoComplete="new-password"
                  value={next}
                  onChange={(e) => setNext(e.target.value)}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm outline-none transition focus:border-blue-600 focus:ring-2 focus:ring-blue-100"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-600">Confirm new password</label>
                <input
                  type="password"
                  required
                  autoComplete="new-password"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm outline-none transition focus:border-blue-600 focus:ring-2 focus:ring-blue-100"
                />
              </div>

              {error && (
                <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-600">
                  {error}
                </p>
              )}

              <button
                type="submit"
                disabled={loading}
                className="inline-flex items-center gap-2 rounded-md bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-700 disabled:opacity-40"
              >
                {loading && <Loader2 size={15} className="animate-spin" />}
                Update password
              </button>
            </form>
          )}
        </div>

        <div className="mt-6 flex justify-end">
          <button
            type="button"
            onClick={() => {
              clearAuth();
              router.replace("/login");
            }}
            className="text-xs text-slate-400 hover:text-red-600"
          >
            Sign out
          </button>
        </div>
      </main>
    </div>
  );
}

export default function AccountPageWrapper() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-slate-50" />}>
      <AccountPage />
    </Suspense>
  );
}
