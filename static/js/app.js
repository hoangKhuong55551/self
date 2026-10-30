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
  // 7. Smooth page entrance animation
  // ─────────────────────────────────────────────
  const mainContent = document.querySelector('.content-container');
  if (mainContent) {
    mainContent.style.opacity = '0';
    mainContent.style.transform = 'translateY(8px)';
    mainContent.style.transition = 'opacity 0.25s ease, transform 0.25s ease';
    requestAnimationFrame(() => {
      mainContent.style.opacity = '1';
      mainContent.style.transform = 'translateY(0)';
    });
  }
});

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
