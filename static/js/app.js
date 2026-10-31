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

  if (toggleBtn && sidebar) {
    toggleBtn.addEventListener('click', function () {
      sidebar.classList.toggle('show');
      if (overlay) overlay.classList.toggle('show', sidebar.classList.contains('show'));
    });
  }

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
    themeBtn.addEventListener('click', function () {
      const current = html.getAttribute('data-bs-theme');
      const next = current === 'dark' ? 'light' : 'dark';
      applyTheme(next);
      try { localStorage.setItem('lifeos-theme', next); } catch (e) {}
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
    render(pages.map(p => ({ ...p, group: 'Trang' })));
    requestAnimationFrame(() => input.focus());
  }

  function close() { if (root) root.hidden = true; }
  function toggle() { if (root) (root.hidden ? open() : close()); }

  function onInput() {
    const q = input.value.trim();
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
    if (!item) return;
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
