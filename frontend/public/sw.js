/* OSIRIS Imhotep — Field Service Worker
 *
 * Caching strategy:
 *   - APP SHELL     (HTML routes /):  network-first, fallback to cached shell.
 *   - STATIC ASSETS (_next/static):  cache-first (immutable hashes).
 *   - MAP TILES     (tile.openstreetmap.org): stale-while-revalidate.
 *   - API requests  (/api/*):         network-only.  POSTs are handled by the
 *                                     ChatInput offline queue; caching GETs
 *                                     would mask 401s and stale data.
 */
const CACHE_VERSION = "osiris-v1";
const SHELL_CACHE = `${CACHE_VERSION}-shell`;
const STATIC_CACHE = `${CACHE_VERSION}-static`;
const TILE_CACHE = `${CACHE_VERSION}-tiles`;

const APP_SHELL_URLS = [
  "/",
  "/documents",
  "/login",
  "/manifest.json",
  "/favicon.svg",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(SHELL_CACHE);
      // Best-effort: ignore any sub-path that 404s in dev.
      await Promise.allSettled(APP_SHELL_URLS.map((u) => cache.add(u)));
      self.skipWaiting();
    })(),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(
        keys
          .filter((k) => !k.startsWith(CACHE_VERSION))
          .map((k) => caches.delete(k)),
      );
      await self.clients.claim();
    })(),
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return; // never cache POSTs/PUTs/DELETEs
  const url = new URL(req.url);

  // Never cache API traffic.
  if (url.pathname.startsWith("/api/")) return;

  // Map tiles: stale-while-revalidate.
  if (/^https?:\/\/([a-z0-9-]+\.)?tile\.openstreetmap\.org\//i.test(req.url)) {
    event.respondWith(staleWhileRevalidate(req, TILE_CACHE));
    return;
  }

  // Next.js static assets (hashed, immutable): cache-first.
  if (url.pathname.startsWith("/_next/static/")) {
    event.respondWith(cacheFirst(req, STATIC_CACHE));
    return;
  }

  // App shell HTML routes: network-first, cached fallback when offline.
  if (req.mode === "navigate" || (req.headers.get("accept") || "").includes("text/html")) {
    event.respondWith(networkFirst(req, SHELL_CACHE));
    return;
  }

  // Other same-origin GETs: try cache, then network.
  if (url.origin === self.location.origin) {
    event.respondWith(cacheFirst(req, SHELL_CACHE));
  }
});

// ---------------------------------------------------------------------------
// Strategies
// ---------------------------------------------------------------------------

async function cacheFirst(req, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(req);
  if (cached) return cached;
  try {
    const res = await fetch(req);
    if (res && res.ok) cache.put(req, res.clone()).catch(() => {});
    return res;
  } catch (e) {
    return new Response("Offline", { status: 503, statusText: "Offline" });
  }
}

async function networkFirst(req, cacheName) {
  const cache = await caches.open(cacheName);
  try {
    const res = await fetch(req);
    if (res && res.ok) cache.put(req, res.clone()).catch(() => {});
    return res;
  } catch (e) {
    const cached = await cache.match(req);
    if (cached) return cached;
    return new Response("Offline", { status: 503, statusText: "Offline" });
  }
}

async function staleWhileRevalidate(req, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(req);
  const fetchPromise = fetch(req)
    .then((res) => {
      if (res && res.ok) cache.put(req, res.clone()).catch(() => {});
      return res;
    })
    .catch(() => cached || new Response("Tile unavailable", { status: 503 }));
  return cached || fetchPromise;
}
