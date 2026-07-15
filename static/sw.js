// Service Worker for Laundry Service App

const CACHE_NAME = "laundry-app-v2";

// Files that rarely change - cache aggressively
const STATIC_ASSETS = [
    "/static/style.css",
    "/static/dashboard.css",
    "/static/theme.css",
    "/static/theme.js",
    "/static/icons/icon-192.png",
    "/static/icons/icon-512.png",
    "/static/icons/icon-maskable-512.png",
    "/static/manifest.json"
];

// Install event - cache static assets
self.addEventListener("install", (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => {
                console.log("Caching static assets...");
                return cache.addAll(STATIC_ASSETS);
            })
            .then(() => {
                console.log("All static assets cached!");
            })
    );
    self.skipWaiting();
});

// Activate event - clean up old caches
self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys().then((keys) => {
            return Promise.all(
                keys.filter((key) => key !== CACHE_NAME)
                    .map((key) => {
                        console.log("Deleting old cache:", key);
                        return caches.delete(key);
                    })
            );
        })
    );
    self.clients.claim();
});

// Fetch event - serve cached assets when offline
self.addEventListener("fetch", (event) => {
    const url = new URL(event.request.url);
    const isStaticAsset = STATIC_ASSETS.some((path) => 
        url.pathname.includes(path)
    );

    if (isStaticAsset) {
        // Static assets: cache first, then network
        event.respondWith(
            caches.match(event.request)
                .then((cached) => {
                    if (cached) {
                        return cached;
                    }
                    return fetch(event.request).then((response) => {
                        // Cache the new response for next time
                        const responseClone = response.clone();
                        caches.open(CACHE_NAME).then((cache) => {
                            cache.put(event.request, responseClone);
                        });
                        return response;
                    });
                })
        );
    } else {
        // Everything else: network first, fallback to offline page
        event.respondWith(
            fetch(event.request)
                .catch(() => {
                    return caches.match("/offline.html");
                })
        );
    }
});