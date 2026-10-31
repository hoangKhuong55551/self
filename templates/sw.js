/* Life OS service worker: network-first, cache chỉ dùng khi mất mạng. */
const CACHE = 'lifeos-v1';
const OFFLINE_URL = '/offline/';
const PRECACHE = [OFFLINE_URL, '/static/icons/icon-192.png'];

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(PRECACHE)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);

  // Chỉ xử lý GET cùng origin, bỏ qua admin và các API JSON
  if (request.method !== 'GET' || url.origin !== location.origin) return;
  if (url.pathname.startsWith('/admin/') || url.pathname.startsWith('/search/') ||
      url.pathname.startsWith('/export/') || url.pathname.endsWith('/lookup/')) return;

  event.respondWith(
    fetch(request)
      .then(response => {
        // Lưu bản mới nhất của trang và static để dùng khi offline
        if (response.ok && (request.mode === 'navigate' || url.pathname.startsWith('/static/'))) {
          const copy = response.clone();
          caches.open(CACHE).then(cache => cache.put(request, copy));
        }
        return response;
      })
      .catch(() => caches.match(request).then(cached =>
        cached || (request.mode === 'navigate' ? caches.match(OFFLINE_URL) : Response.error())
      ))
  );
});
