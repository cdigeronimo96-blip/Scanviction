/* Scanviction service worker — native Web Push + light offline support.
 *
 * Served by Streamlit's static file server at /app/static/sw.js (config.toml has
 * enableStaticServing = true). Registered by the push-enable flow in Settings →
 * Profile. Replaces the OneSignal SDK: pushes are sent directly from the app's
 * own alert pipeline via VAPID (see webpush.py).
 */

self.addEventListener('install', (e) => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(clients.claim()));

/* ── Push: show the notification ── */
self.addEventListener('push', (event) => {
  let data = { title: 'Scanviction', body: 'New market signal', url: '/' };
  try { data = Object.assign(data, event.data.json()); } catch (_) {}
  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: '/app/static/icon-192.png',
      badge: '/app/static/icon-192.png',
      data: { url: data.url || '/' },
      tag: 'scanviction-signal',
      renotify: true,
    })
  );
});

/* ── Click: focus an open tab or open the app ── */
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || '/';
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((tabs) => {
      for (const t of tabs) {
        if ('focus' in t) { t.navigate(url); return t.focus(); }
      }
      return clients.openWindow(url);
    })
  );
});
