/* global workbox */
importScripts("https://storage.googleapis.com/workbox-cdn/releases/6.5.4/workbox-sw.js");

const APP_SHELL_CACHE = "pwa-shell-v1";
const ASSETS_CACHE = "pwa-assets-v1";
const STATUS_CACHE = "pwa-statuses-v1";
const CLIENT_BASE = "/client";

if (workbox) {
  workbox.core.skipWaiting();
  workbox.core.clientsClaim();

  workbox.routing.registerRoute(
    ({ request }) => request.mode === "navigate",
    new workbox.strategies.NetworkFirst({
      cacheName: APP_SHELL_CACHE,
      plugins: [new workbox.expiration.ExpirationPlugin({ maxEntries: 20 })],
    }),
  );

  workbox.routing.registerRoute(
    ({ url, request }) =>
      request.method === "GET" &&
      url.pathname.includes("/api/core") &&
      (url.pathname.includes("/marketplace/orders") || url.pathname.includes("/documents")),
    new workbox.strategies.StaleWhileRevalidate({
      cacheName: STATUS_CACHE,
      plugins: [
        new workbox.expiration.ExpirationPlugin({
          maxEntries: 50,
          maxAgeSeconds: 60 * 60 * 24,
        }),
      ],
    }),
  );

  workbox.routing.registerRoute(
    ({ request }) => ["style", "script", "image", "font"].includes(request.destination),
    new workbox.strategies.StaleWhileRevalidate({
      cacheName: ASSETS_CACHE,
      plugins: [
        new workbox.expiration.ExpirationPlugin({
          maxEntries: 80,
          maxAgeSeconds: 60 * 60 * 24 * 7,
        }),
      ],
    }),
  );
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(APP_SHELL_CACHE).then((cache) =>
      cache.addAll([`${CLIENT_BASE}/`, `${CLIENT_BASE}/index.html`, `${CLIENT_BASE}/manifest.webmanifest`]),
    ),
  );
});

self.addEventListener("push", (event) => {
  const payload = event.data?.json() ?? {};
  const title = payload.title ?? "Новый статус";
  const options = {
    body: payload.body ?? "Откройте приложение, чтобы посмотреть обновления.",
    icon: `${CLIENT_BASE}/pwa-icon.svg`,
    data: {
      url: payload.url ?? `${CLIENT_BASE}/marketplace/orders`,
    },
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const targetUrl = event.notification?.data?.url ?? `${CLIENT_BASE}/`;
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if ("focus" in client && client.url.includes(targetUrl)) {
          return client.focus();
        }
      }
      if (self.clients.openWindow) {
        return self.clients.openWindow(targetUrl);
      }
      return undefined;
    }),
  );
});
