"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, X } from "lucide-react";
import { isIOSWebView, isStandalone } from "@/lib/platform";

export default function WebViewBanner() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    // Only show when in an iOS WebView and NOT in standalone mode.
    if (isIOSWebView() && !isStandalone()) {
      setVisible(true);
    }
  }, []);

  if (!visible) return null;

  return (
    <div
      className="relative flex items-start gap-3 bg-amber-50 border-b border-amber-200 px-4 py-3"
      role="alert"
    >
      <AlertTriangle
        size={16}
        className="mt-0.5 shrink-0 text-amber-600"
        aria-hidden="true"
      />
      <p className="text-sm text-amber-800 leading-relaxed">
        <strong>Limited browser mode detected.</strong> Some features — voice dictation,
        camera upload, and speech recognition — may not work in this embedded browser.{" "}
        <a
          href="https://github.com/your-org/osiris-imhotep/blob/main/docs/median-webview.md"
          target="_blank"
          rel="noopener noreferrer"
          className="underline hover:text-amber-900"
        >
          Learn how to open in Safari
        </a>{" "}
        for the full experience, or add this app to your home screen for offline access.
      </p>
      <button
        type="button"
        onClick={() => setVisible(false)}
        className="shrink-0 text-amber-600 hover:text-amber-800 transition"
        aria-label="Dismiss"
      >
        <X size={16} />
      </button>
    </div>
  );
}
