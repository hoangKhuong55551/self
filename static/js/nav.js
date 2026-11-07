/**
 * Life OS — chuyển trang nhanh từ menu (sidebar, thanh dưới)
 *
 * Tải lại cả trang mất ~0.2-0.4s: trang cũ đứng yên rồi trang mới thay vào đột ngột.
 * Ở đây: rê chuột / chạm vào mục menu là tải sẵn HTML; bấm thì chỉ thay phần nội dung
 * (<main>, thông báo, script riêng của trang), giữ nguyên sidebar, topbar, CSS, JS.
 *
 * Gặp gì bất thường (lỗi mạng, bị chuyển hướng, trang có bộ đếm giờ/kéo thả...)
 * thì quay về tải lại cả trang như bình thường.
 */
(function () {
  if (!window.fetch || !window.DOMParser || !history.pushState) return;

  // Trang có trạng thái chạy liên tục (setInterval, kéo thả, biến toàn cục) → luôn tải đủ
  const FULL_RELOAD = [/^\/productivity\/pomodoro/, /^\/productivity\/kanban/];
  const NAV_LINKS = '.app-sidebar a[href], .bottom-nav a[href]';
  const CACHE_MS = 15000;

  const cache = new Map(); // url -> { at, promise }
  let navSeq = 0;

  const needsFull = path => FULL_RELOAD.some(re => re.test(path));

  function eligible(a) {
    if (!a || a.target && a.target !== '_self' || a.hasAttribute('download')) return false;
    const url = new URL(a.href, location.href);
    if (url.origin !== location.origin || url.hash && url.pathname === location.pathname) return false;
    if (/logout|admin/.test(url.pathname)) return false;
    return !needsFull(url.pathname) && !needsFull(location.pathname);
  }

  function load(url) {
    const hit = cache.get(url);
    if (hit && Date.now() - hit.at < CACHE_MS) return hit.promise;
    const promise = fetch(url, { credentials: 'same-origin', headers: { 'X-Requested-With': 'lifeos-nav' } })
      .then(res => {
        const finalPath = new URL(res.url).pathname;
        // Bị chuyển hướng sang trang khác (vd. hết phiên đăng nhập) → để trình duyệt tự tải
        if (!res.ok || finalPath !== new URL(url).pathname) throw new Error('fallback');
        return res.text();
      });
    promise.catch(() => cache.delete(url));
    cache.set(url, { at: Date.now(), promise });
    return promise;
  }

  // ── Chạy lại script riêng của trang ──
  // Script của các trang bọc trong DOMContentLoaded (đã qua) → gom lại rồi gọi sau.
  async function runScripts(container) {
    const pending = [];
    const realAdd = document.addEventListener;
    const realWinAdd = window.addEventListener;
    document.addEventListener = function (type, fn, opts) {
      if (type === 'DOMContentLoaded') return pending.push(fn);
      return realAdd.call(this, type, fn, opts);
    };
    window.addEventListener = function (type, fn, opts) {
      if (type === 'load' || type === 'DOMContentLoaded') return pending.push(fn);
      return realWinAdd.call(this, type, fn, opts);
    };
    try {
      for (const old of [...container.querySelectorAll('script')]) {
        const type = old.getAttribute('type');
        if (type && !/javascript|module/.test(type)) continue; // JSON data: không cần chạy
        const s = document.createElement('script');
        for (const { name, value } of old.attributes) s.setAttribute(name, value);
        s.textContent = old.textContent;
        const done = s.src ? new Promise(r => { s.onload = s.onerror = r; }) : null;
        old.replaceWith(s);
        if (done) await done;
      }
    } finally {
      document.addEventListener = realAdd;
      window.addEventListener = realWinAdd;
    }
    const evt = new Event('DOMContentLoaded');
    pending.forEach(fn => { try { fn.call(document, evt); } catch (e) { console.error(e); } });
  }

  function syncActive(doc) {
    // Sidebar/thanh dưới giữ nguyên, chỉ chép class "active" từ trang mới sang
    ['.app-sidebar a[href]', '.bottom-nav a[href]'].forEach(sel => {
      const fresh = doc.querySelectorAll(sel);
      document.querySelectorAll(sel).forEach((a, i) => {
        if (fresh[i] && fresh[i].getAttribute('href') === a.getAttribute('href')) a.className = fresh[i].className;
      });
    });
  }

  function initContent() {
    if (window.bootstrap) {
      document.querySelectorAll('.content-container [data-bs-toggle="tooltip"]').forEach(el => new bootstrap.Tooltip(el));
      document.querySelectorAll('#flashMessages .alert.alert-dismissible').forEach(alert => {
        setTimeout(() => bootstrap.Alert.getOrCreateInstance(alert)?.close(), 4000);
      });
    }
    window.LifeFX?.initPage?.();
  }

  async function go(url, { push = true, scroll = 0 } = {}) {
    const seq = ++navSeq;
    document.documentElement.classList.add('nav-loading');
    let html;
    try {
      html = await load(url);
    } catch (e) {
      location.href = url;
      return;
    }
    if (seq !== navSeq) return; // người dùng đã bấm sang mục khác

    const doc = new DOMParser().parseFromString(html, 'text/html');
    const main = doc.querySelector('main.content-container');
    const curMain = document.querySelector('main.content-container');
    if (!main || !curMain || !doc.getElementById('pageScripts')) { location.href = url; return; }

    // Đóng các thứ đang mở (dropdown, tooltip, sidebar trên mobile)
    document.querySelectorAll('.tooltip, .dropdown-menu.show').forEach(el => el.classList.remove('show'));
    document.getElementById('appSidebar')?.classList.remove('show');
    document.getElementById('sidebarOverlay')?.classList.remove('show');

    if (push) history.pushState({ lifeosNav: true }, '', url);
    document.title = doc.title;
    curMain.replaceWith(document.adoptNode(main));
    document.getElementById('flashMessages')?.replaceWith(document.adoptNode(doc.getElementById('flashMessages')));
    const scripts = document.adoptNode(doc.getElementById('pageScripts'));
    document.getElementById('pageScripts').replaceWith(scripts);
    syncActive(doc);
    window.scrollTo(0, scroll);

    main.classList.add('nav-enter');
    main.addEventListener('animationend', () => main.classList.remove('nav-enter'), { once: true });
    document.documentElement.classList.remove('nav-loading');

    await runScripts(scripts);
    initContent();
    // Trang vừa đổi có thể đã đổi dữ liệu → bỏ bản tải sẵn cũ của chính nó
    cache.delete(url);
  }

  // Tải sẵn khi rê chuột / chạm / focus vào mục menu
  const warm = e => {
    const a = e.target.closest?.(NAV_LINKS);
    if (a && eligible(a)) load(a.href).catch(() => {});
  };
  document.addEventListener('pointerover', warm, { passive: true });
  document.addEventListener('touchstart', warm, { passive: true });
  document.addEventListener('focusin', warm);

  document.addEventListener('click', e => {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    const a = e.target.closest(NAV_LINKS);
    if (!a || !eligible(a)) return;
    e.preventDefault();
    if (a.href === location.href) { window.scrollTo({ top: 0, behavior: 'smooth' }); return; }
    go(a.href);
  });

  // Back / Forward
  history.replaceState({ lifeosNav: true, ...(history.state || {}) }, '');
  window.addEventListener('popstate', e => {
    if (!e.state || !e.state.lifeosNav || needsFull(location.pathname)) { location.reload(); return; }
    go(location.href, { push: false });
  });

  // Sau khi gửi form, dữ liệu đổi → bỏ các trang đã tải sẵn
  document.addEventListener('submit', () => cache.clear());
})();
