/* Life OS service worker: network-first, cache chỉ dùng khi mất mạng. */
{% url 'admin:index' as admin_url %}const ADMIN_PREFIX = '{{ admin_url|escapejs }}';
const CACHE = 'lifeos-v3';
const OFFLINE_URL = '/offline/';
const PRECACHE = [OFFLINE_URL, '/static/icons/icon-192.png'];

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(PRECACHE)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', event => {
  event.waitUntil(
    // Navigation preload: gửi request trang song song lúc service worker khởi động
    (self.registration.navigationPreload ? self.registration.navigationPreload.enable() : Promise.resolve())
      .then(() => caches.keys())
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);

  // Chỉ xử lý GET cùng origin, bỏ qua admin và các API JSON
  if (request.method !== 'GET' || url.origin !== location.origin) return;
  if (url.pathname.startsWith(ADMIN_PREFIX) || url.pathname.startsWith('/search/') ||
      url.pathname.startsWith('/export/') || url.pathname.endsWith('/lookup/')) return;

  // File tĩnh có ?v= (main.css, app.js, fx.js...) đổi tên khi đổi nội dung: lấy thẳng từ cache,
  // khỏi tải lại mỗi lần chuyển trang (chúng chặn lần vẽ đầu tiên).
  if (url.pathname.startsWith('/static/') && url.searchParams.has('v')) {
    event.respondWith(caches.open(CACHE).then(cache => cache.match(request).then(cached =>
      cached || fetch(request).then(response => {
        if (response.ok) cache.put(request, response.clone());
        return response;
      })
    )));
    return;
  }

  const network = request.mode === 'navigate'
    ? Promise.resolve(event.preloadResponse).then(r => r || fetch(request))
    : fetch(request);

  event.respondWith(
    network
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
