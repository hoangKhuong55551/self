/**
 * Life OS — Global Interactions, Theme Toggle & UX Enhancements
 */

document.addEventListener('DOMContentLoaded', function () {
  // ─────────────────────────────────────────────
  // 1. Sidebar Toggle (Mobile)
  // ─────────────────────────────────────────────
  const sidebar = document.getElementById('appSidebar');
  const toggleBtn = document.getElementById('sidebarToggleBtn');
  const overlay = document.getElementById('sidebarOverlay');

  // Màn hình rộng: ẩn/hiện hẳn menu, nhớ lựa chọn. Màn hình hẹp: menu trượt ra đè lên nội dung.
  const desktop = window.matchMedia('(min-width: 992px)');
  const syncToggleState = () => {
    if (!toggleBtn) return;
    const open = desktop.matches
      ? !document.documentElement.classList.contains('sidebar-collapsed')
      : !!sidebar?.classList.contains('show');
    toggleBtn.setAttribute('aria-expanded', String(open));
  };
  const toggleSidebar = () => {
    if (!sidebar) return;
    if (desktop.matches) {
      const collapsed = document.documentElement.classList.toggle('sidebar-collapsed');
      try { localStorage.setItem('lifeos-sidebar', collapsed ? 'collapsed' : 'open'); } catch (e) {}
    } else {
      sidebar.classList.toggle('show');
      if (overlay) overlay.classList.toggle('show', sidebar.classList.contains('show'));
    }
    syncToggleState();
  };
  window.LifeOSSidebar = { toggle: toggleSidebar };
  toggleBtn?.addEventListener('click', toggleSidebar);
  desktop.addEventListener?.('change', syncToggleState);
  syncToggleState();

  if (overlay) {
    overlay.addEventListener('click', function () {
      sidebar.classList.remove('show');
      overlay.classList.remove('show');
    });
  }

  // ─────────────────────────────────────────────
  // 2. Dark / Light Mode Toggle
  // ─────────────────────────────────────────────
  const themeBtn = document.getElementById('themeToggleBtn');
  const themeIcon = document.getElementById('themeIcon');
  const html = document.documentElement;

  // Restore saved theme
  applyTheme(html.getAttribute('data-bs-theme') || 'dark');

  if (themeBtn) {
    themeBtn.addEventListener('click', function (e) {
      const current = html.getAttribute('data-bs-theme');
      const next = current === 'dark' ? 'light' : 'dark';
      try { localStorage.setItem('lifeos-theme', next); } catch (err) {}

      const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      if (!document.startViewTransition || reduce) { applyTheme(next); return; }

      // Theme mới lan ra thành vòng tròn từ chính nút vừa bấm
      const r = themeBtn.getBoundingClientRect();
      const x = e.clientX || r.left + r.width / 2;
      const y = e.clientY || r.top + r.height / 2;
      const radius = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));
      html.classList.add('theme-reveal', 'theme-spin');
      const transition = document.startViewTransition(() => applyTheme(next));
      transition.ready.then(() => {
        html.animate(
          { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${radius}px at ${x}px ${y}px)`] },
          { duration: 650, easing: 'cubic-bezier(0.65, 0, 0.35, 1)', pseudoElement: '::view-transition-new(root)' }
        );
      }).catch(() => {});
      transition.finished.finally(() => {
        html.classList.remove('theme-reveal');
        setTimeout(() => html.classList.remove('theme-spin'), 400);
      });
    });
  }

  function applyTheme(theme) {
    // All colors live in main.css under [data-bs-theme]; only the attribute changes here
    html.setAttribute('data-bs-theme', theme);
    if (themeIcon) {
      themeIcon.className = theme === 'dark' ? 'bi bi-sun-fill' : 'bi bi-moon-stars-fill';
    }
    const metaTheme = document.querySelector('meta[name="theme-color"]');
    if (metaTheme) metaTheme.setAttribute('content', theme === 'dark' ? '#070b1a' : '#eef1fb');
    if (window.Chart) {
      Chart.defaults.color = theme === 'dark' ? '#a5b0c6' : '#4b5675';
      Chart.defaults.borderColor = theme === 'dark' ? 'rgba(255,255,255,0.06)' : 'rgba(15,23,42,0.08)';
      Object.values(Chart.instances || {}).forEach(function (c) { c.update(); });
    }
  }

  // ─────────────────────────────────────────────
  // 3. Keyboard Shortcuts
  // ─────────────────────────────────────────────
  document.addEventListener('keydown', function (e) {
    // Ctrl/Cmd+B → Ẩn/hiện menu (trừ khi đang gõ chữ)
    if ((e.ctrlKey || e.metaKey) && !e.shiftKey && !e.altKey && e.key.toLowerCase() === 'b' &&
        !e.target.closest?.('input, textarea, select, [contenteditable="true"]')) {
      e.preventDefault();
      toggleSidebar();
      return;
    }
    // Ctrl/Cmd+K → Command palette
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      CommandPalette.toggle();
      return;
    }
    // Alt+T → Toggle theme
    if (e.altKey && e.key === 't') {
      themeBtn && themeBtn.click();
    }
    // Alt+D → Go to Dashboard
    if (e.altKey && e.key === 'd') {
      window.location.href = '/';
    }
    // Alt+F → Go to Finance
    if (e.altKey && e.key === 'f') {
      window.location.href = '/finance/';
    }
    // Alt+P → Go to Productivity
    if (e.altKey && e.key === 'p') {
      window.location.href = '/productivity/';
    }
    // Alt+A → Go to Academic
    if (e.altKey && e.key === 'a') {
      window.location.href = '/academic/';
    }
    // Alt+L → Go to Library
    if (e.altKey && e.key === 'l') {
      window.location.href = '/library/';
    }
  });

  // ─────────────────────────────────────────────
  // 4. Auto-dismiss alerts after 4 seconds
  // ─────────────────────────────────────────────
  const alerts = document.querySelectorAll('.alert.alert-dismissible');
  alerts.forEach(function (alert) {
    setTimeout(function () {
      const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
      if (bsAlert) bsAlert.close();
    }, 4000);
  });

  // ─────────────────────────────────────────────
  // 5. Active link pulse animation on click
  // ─────────────────────────────────────────────
  document.querySelectorAll('.sidebar-link').forEach(function (link) {
    link.addEventListener('click', function () {
      this.style.transform = 'scale(0.97)';
      setTimeout(() => { this.style.transform = ''; }, 150);
    });
  });

  // ─────────────────────────────────────────────
  // 6. Tooltip initialization (Bootstrap)
  // ─────────────────────────────────────────────
  const tooltipEls = document.querySelectorAll('[data-bs-toggle="tooltip"]');
  tooltipEls.forEach(function (el) {
    new bootstrap.Tooltip(el);
  });

  // ─────────────────────────────────────────────
  // 7. Accent color picker
  // ─────────────────────────────────────────────
  const swatches = document.querySelectorAll('[data-accent-choice]');
  const markActiveSwatch = () => {
    const current = html.getAttribute('data-accent') || '';
    swatches.forEach(s => s.classList.toggle('active', s.dataset.accentChoice === current));
  };
  swatches.forEach(function (swatch) {
    swatch.addEventListener('click', function () {
      const accent = swatch.dataset.accentChoice;
      if (accent) html.setAttribute('data-accent', accent); else html.removeAttribute('data-accent');
      try { localStorage.setItem('lifeos-accent', accent); } catch (e) {}
      markActiveSwatch();
    });
  });
  markActiveSwatch();

  // ─────────────────────────────────────────────
  // 10. Mobile bottom nav "Menu" opens the sidebar
  // ─────────────────────────────────────────────
  document.getElementById('bottomNavMenu')?.addEventListener('click', () => toggleBtn?.click());
});

// Tick việc nhỏ trong checklist của task (thẻ Kanban...): lưu ngay, không tải lại trang
document.addEventListener('change', function (e) {
  const box = e.target.closest?.('[data-checklist-toggle]');
  if (!box) return;
  const token = document.querySelector('meta[name="csrf-token"]')?.content || '';
  box.disabled = true;
  const body = new URLSearchParams({ index: box.dataset.index });
  fetch(box.dataset.checklistToggle, { method: 'POST', body, headers: { 'X-CSRFToken': token, 'Accept': 'application/json' } })
    .then(r => r.ok ? r.json() : Promise.reject())
    .then(d => {
      box.checked = d.done;
      box.nextElementSibling?.classList.toggle('is-done', d.done);
      const count = document.querySelector(`[data-checklist-count="${box.dataset.task}"]`);
      if (count) count.textContent = `${d.done_count}/${d.total}`;
    })
    .catch(() => { box.checked = !box.checked; showToast('Không lưu được, thử lại nhé.', 'danger'); })
    .finally(() => { box.disabled = false; });
});

// ─────────────────────────────────────────────
// 12. Thông báo đẩy: bật/tắt trên thiết bị này (menu chuông)
// ─────────────────────────────────────────────
(function () {
  const key = document.querySelector('meta[name="vapid-key"]')?.content;
  const panel = document.getElementById('pushPanel');
  if (!key || !panel || !('serviceWorker' in navigator) || !('PushManager' in window) || !window.isSecureContext) return;
  const status = document.getElementById('pushStatus');
  const toggle = document.getElementById('pushToggleBtn');
  const test = document.getElementById('pushTestBtn');
  const token = () => document.querySelector('meta[name="csrf-token"]')?.content || '';
  const post = (url, body) => fetch(url, {
    method: 'POST', body: body ? JSON.stringify(body) : undefined,
    headers: { 'X-CSRFToken': token(), 'Content-Type': 'application/json', 'Accept': 'application/json' },
  }).then(r => r.json().catch(() => ({})).then(d => ({ ok: r.ok && d.ok !== false, ...d })));
  const toKey = b64 => {
    const s = atob((b64 + '='.repeat((4 - b64.length % 4) % 4)).replace(/-/g, '+').replace(/_/g, '/'));
    return Uint8Array.from(s, c => c.charCodeAt(0));
  };

  async function current() {
    const reg = await navigator.serviceWorker.ready;
    return reg.pushManager.getSubscription();
  }
  async function render() {
    const sub = await current();
    const denied = Notification.permission === 'denied';
    panel.hidden = false;
    status.textContent = denied ? 'Thông báo bị chặn trong cài đặt trình duyệt'
      : sub ? 'Đang nhận nhắc việc trên thiết bị này' : 'Nhận nhắc việc trên thiết bị này';
    toggle.textContent = sub ? 'Tắt' : 'Bật';
    toggle.disabled = denied;
    toggle.classList.toggle('btn-primary', !sub);
    toggle.classList.toggle('btn-outline-secondary', !!sub);
    test.hidden = !sub;
  }
  toggle.addEventListener('click', async () => {
    toggle.disabled = true;
    try {
      const sub = await current();
      if (sub) {
        await post('/push/unsubscribe/', { endpoint: sub.endpoint });
        await sub.unsubscribe();
        showToast('Đã tắt thông báo trên thiết bị này', 'info');
      } else {
        if (await Notification.requestPermission() !== 'granted') { showToast('Bạn chưa cho phép thông báo', 'warning'); return; }
        const reg = await navigator.serviceWorker.ready;
        const fresh = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: toKey(key) });
        const res = await post('/push/subscribe/', fresh.toJSON());
        showToast(res.ok ? 'Đã bật nhắc việc trên thiết bị này' : (res.error || 'Không bật được'), res.ok ? 'success' : 'danger');
      }
    } catch (e) {
      showToast('Không bật được thông báo: ' + (e.message || e), 'danger');
    } finally {
      toggle.disabled = false;
      render();
    }
  });
  test.addEventListener('click', async () => {
    const res = await post('/push/test/');
    showToast(res.ok ? 'Đã gửi, xem thông báo của máy' : (res.error || 'Gửi không thành công'), res.ok ? 'success' : 'danger');
  });
  render();
})();

// Gỡ skeleton khi Chart.js vẽ xong lần đầu
if (window.Chart) {
  Chart.register({
    id: 'lifeosReady',
    afterRender(chart) { chart.canvas.closest('.chart-box')?.classList.add('chart-ready'); },
  });
}

// ─────────────────────────────────────────────
// 8. Global Toast Notification Helper
// ─────────────────────────────────────────────
function showToast(message, type = 'success') {
  let container = document.getElementById('toastContainer');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toastContainer';
    document.body.appendChild(container);
  }

  const iconMap = {
    success: 'bi-check-circle-fill text-success',
    danger: 'bi-exclamation-circle-fill text-danger',
    warning: 'bi-exclamation-triangle-fill text-warning',
    info: 'bi-info-circle-fill text-info',
  };

  const toast = document.createElement('div');
  toast.className = 'lifeos-toast';
  toast.setAttribute('role', 'status');
  toast.innerHTML = `
    <div class="d-flex align-items-center gap-2 p-3">
      <i class="bi ${iconMap[type] || iconMap.info} fs-5"></i>
      <span class="flex-grow-1 small fw-medium"></span>
      <button type="button" class="btn-close btn-close-sm ms-auto" aria-label="Đóng"></button>
    </div>
  `;
  toast.querySelector('span').textContent = message;

  const dismiss = () => {
    toast.classList.add('hide');
    setTimeout(() => toast.remove(), 250);
  };
  toast.querySelector('.btn-close').addEventListener('click', dismiss);
  container.appendChild(toast);
  setTimeout(dismiss, 4000);
}

// ─────────────────────────────────────────────
// 9. Command Palette (Ctrl+K): pages + live search across modules
// ─────────────────────────────────────────────
const CommandPalette = (function () {
  let root, input, list, pages = [], items = [], active = 0, timer = null, lastQuery = '';

  // Bỏ dấu tiếng Việt để "tai chinh" khớp "Tài chính"
  const fold = s => (s || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/g, 'd').replace(/Đ/g, 'D').toLowerCase();

  function init() {
    root = document.getElementById('cmdk');
    if (!root) return;
    input = document.getElementById('cmdkInput');
    list = document.getElementById('cmdkList');
    try { pages = JSON.parse(document.getElementById('cmdk-pages').textContent); } catch (e) { pages = []; }

    document.getElementById('cmdkTrigger')?.addEventListener('click', open);
    root.querySelectorAll('[data-cmdk-close]').forEach(el => el.addEventListener('click', close));
    input.addEventListener('input', onInput);
    input.addEventListener('keydown', onKey);
    list.addEventListener('mousemove', e => {
      const li = e.target.closest('.cmdk-item');
      if (li) setActive(Number(li.dataset.index));
    });
    list.addEventListener('click', e => {
      const li = e.target.closest('.cmdk-item');
      if (li) run(items[Number(li.dataset.index)]);
    });
  }

  function open() {
    if (!root) return;
    root.hidden = false;
    input.value = '';
    lastQuery = '';
    render(pages.map(p => ({ ...p, group: 'Trang' })).concat([QUICK_HINT]));
    requestAnimationFrame(() => input.focus());
  }

  function close() { if (root) root.hidden = true; }
  function toggle() { if (root) (root.hidden ? open() : close()); }

  // ── Thêm nhanh: "-50k cafe", "+15tr lương", "task nộp bài thứ 6" ──
  const QUICK_RE = /^\s*([-+]\s*\d|(task|t|vi[eệ]c)\s*:\s*\S)/i;
  const QUICK_HINT = {
    group: 'Thêm nhanh', icon: 'bi-lightning-charge', action: 'hint',
    title: 'Gõ "-50k cafe" để ghi chi, "+15tr lương" để ghi thu, "task: ..." để tạo việc',
    subtitle: '@ví  #danh mục/mục tiêu  hôm qua · mai · thứ 6 · 05/11  ! = khẩn cấp',
  };
  let quickTimer = null, quickSeq = 0;

  function quickPreview(q) {
    const seq = ++quickSeq;
    render([{ group: 'Thêm nhanh', icon: 'bi-hourglass-split', title: 'Đang đọc...', action: 'hint' }]);
    clearTimeout(quickTimer);
    quickTimer = setTimeout(() => {
      fetch('/quick-add/?q=' + encodeURIComponent(q), { headers: { 'Accept': 'application/json' } })
        .then(r => r.json())
        .then(d => {
          if (seq !== quickSeq || root.hidden) return;
          if (!d.match) return render([QUICK_HINT]);
          render([{
            group: 'Thêm nhanh', title: d.title, subtitle: d.subtitle || '',
            icon: d.ok ? (d.kind === 'task' ? 'bi-plus-square' : 'bi-cash-coin') : 'bi-exclamation-circle',
            action: d.ok ? 'quick' : 'hint', query: q,
          }]);
        })
        .catch(() => {});
    }, 120);
  }

  function quickCommit(q) {
    const body = new URLSearchParams({ q });
    const token = document.querySelector('meta[name="csrf-token"]')?.content || '';
    fetch('/quick-add/', { method: 'POST', body, headers: { 'X-CSRFToken': token, 'Accept': 'application/json' } })
      .then(r => r.json().then(d => ({ ok: r.ok, d })))
      .then(({ ok, d }) => {
        if (!ok || !d.ok) { showToast(d.title || 'Không lưu được, thử lại nhé.', 'danger'); return; }
        showToast(d.message, 'success');
        // Trang đang xem có thể hiển thị dữ liệu vừa đổi (số dư, danh sách task...) → tải lại
        if (/^\/(finance|productivity)?\/?$|^\/(finance|productivity)\//.test(location.pathname)) {
          setTimeout(() => location.reload(), 700);
        }
      })
      .catch(() => showToast('Không lưu được, kiểm tra kết nối.', 'danger'));
  }

  function onInput() {
    const q = input.value.trim();
    if (QUICK_RE.test(q)) { clearTimeout(timer); lastQuery = ''; quickPreview(q); return; }
    quickSeq++; // huỷ bản xem trước cũ đang chờ
    const fq = fold(q);
    const matchedPages = pages
      .filter(p => !fq || fold(p.title + ' ' + (p.keywords || '')).includes(fq))
      .map(p => ({ ...p, group: 'Trang' }));
    render(matchedPages, q.length >= 2);

    clearTimeout(timer);
    if (q.length < 2) return;
    timer = setTimeout(() => search(q, matchedPages), 180);
  }

  function search(q, matchedPages) {
    lastQuery = q;
    fetch('/search/?q=' + encodeURIComponent(q), { headers: { 'Accept': 'application/json' } })
      .then(r => r.ok ? r.json() : { results: [] })
      .then(data => {
        if (q !== lastQuery || root.hidden) return; // kết quả cũ, bỏ qua
        const found = (data.results || []).map(r => ({ ...r, group: r.type }));
        render(matchedPages.concat(found));
      })
      .catch(() => {});
  }

  function render(newItems, loading) {
    items = newItems;
    active = 0;
    list.innerHTML = '';
    if (!items.length) {
      const empty = document.createElement('li');
      empty.className = 'cmdk-empty';
      empty.textContent = loading ? 'Đang tìm...' : 'Không tìm thấy kết quả nào';
      list.appendChild(empty);
      return;
    }
    let lastGroup = null;
    items.forEach((item, i) => {
      if (item.group !== lastGroup) {
        lastGroup = item.group;
        const g = document.createElement('li');
        g.className = 'cmdk-group';
        g.textContent = item.group;
        list.appendChild(g);
      }
      const li = document.createElement('li');
      li.className = 'cmdk-item';
      li.dataset.index = i;
      li.setAttribute('role', 'option');
      li.innerHTML = '<i class="bi"></i><div class="cmdk-item-text"><div class="cmdk-item-title"></div><div class="cmdk-item-sub"></div></div>';
      li.querySelector('i').classList.add(item.icon || 'bi-arrow-right');
      li.querySelector('.cmdk-item-title').textContent = item.title;
      const sub = li.querySelector('.cmdk-item-sub');
      if (item.subtitle) sub.textContent = item.subtitle; else sub.remove();
      list.appendChild(li);
    });
    setActive(0);
  }

  function setActive(i) {
    const els = list.querySelectorAll('.cmdk-item');
    if (!els.length) return;
    active = (i + els.length) % els.length;
    els.forEach(el => el.classList.toggle('active', Number(el.dataset.index) === active));
    els[active].scrollIntoView({ block: 'nearest' });
  }

  function onKey(e) {
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive(active + 1); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive(active - 1); }
    else if (e.key === 'Enter') { e.preventDefault(); run(items[active]); }
    else if (e.key === 'Escape') { e.preventDefault(); close(); }
  }

  function run(item) {
    if (!item || item.action === 'hint') return;
    if (item.action === 'quick') { close(); quickCommit(item.query); return; }
    close();
    if (item.action === 'theme') {
      document.getElementById('themeToggleBtn')?.click();
    } else if (item.url) {
      window.location.href = item.url;
    }
  }

  document.addEventListener('DOMContentLoaded', init);
  return { open, close, toggle };
})();

// ─────────────────────────────────────────────
// 11. PWA: đăng ký service worker (cần HTTPS hoặc localhost)
// ─────────────────────────────────────────────
if ('serviceWorker' in navigator && window.isSecureContext) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  });
}
