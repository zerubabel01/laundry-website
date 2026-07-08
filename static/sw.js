// A service worker is a script the browser runs in the background,
// separate from your page. It's what makes "Add to Home Screen" and
// offline support possible.

const CACHE_NAME = "laundry-app-v1";

// Files that rarely change - safe to cache aggressively
const STATIC_ASSETS = [
    "/static/style.css",
    "/static/dashboard.css",
    "/static/theme.css",
    "/static/theme.js",
    "/static/icons/icon-192.png",
    "/static/icons/icon-512.png",
];

// When the service worker is first installed, pre-cache the static assets
self.addEventListener("install", (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
    );
    self.skipWaiting();
});

// Clean up old caches if this file is ever updated (bump CACHE_NAME above)
self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(
                keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
            )
        )
    );
    self.clients.claim();
});

// Strategy:
// - Static files (CSS/JS/icons): serve from cache first, for speed + offline support
// - Everything else (actual pages with live data): try the network first,
//   since order/customer data changes constantly and shouldn't go stale.
self.addEventListener("fetch", (event) => {
    const isStaticAsset = STATIC_ASSETS.some((path) => event.request.url.includes(path));

    if (isStaticAsset) {
        event.respondWith(
            caches.match(event.request).then((cached) => cached || fetch(event.request))
        );
    } else {
        event.respondWith(
            fetch(event.request).catch(() =>
                new Response(
                    "<h1>You're offline</h1><p>Please reconnect to the internet to use the app.</p>",
                    { headers: { "Content-Type": "text/html" } }
                )
            )
        );
    }
});