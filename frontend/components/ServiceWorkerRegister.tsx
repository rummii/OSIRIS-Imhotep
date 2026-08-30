"use client";

import { useEffect } from "react";

/**
 * Registers the PWA service worker in production.  In development the SW is
 * skipped so that HMR and the test mock backend aren't disrupted.
 */
export default function ServiceWorkerRegister() {
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (process.env.NODE_ENV !== "production") return;
    if (!("serviceWorker" in navigator)) return;

    const onLoad = () => {
      navigator.serviceWorker
        .register("/sw.js", { scope: "/" })
        .catch((err) => {
          // Service worker registration is best-effort; we never want
          // a misbehaving SW to break the app.
          // eslint-disable-next-line no-console
          console.warn("[osiris] service worker registration failed:", err);
        });
    };

    if (document.readyState === "complete") {
      onLoad();
    } else {
      window.addEventListener("load", onLoad, { once: true });
      return () => window.removeEventListener("load", onLoad);
    }
  }, []);

  return null;
}
