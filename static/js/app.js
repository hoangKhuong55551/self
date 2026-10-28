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
      if (overlay) overlay.style.display = sidebar.classList.contains('show') ? 'block' : 'none';
    });
  }

  if (overlay) {
    overlay.addEventListener('click', function () {
      sidebar.classList.remove('show');
      overlay.style.display = 'none';
    });
  }

  // ─────────────────────────────────────────────
  // 2. Dark / Light Mode Toggle
  // ─────────────────────────────────────────────
  const themeBtn = document.getElementById('themeToggleBtn');
  const themeIcon = document.getElementById('themeIcon');
  const html = document.documentElement;

  // Restore saved theme
  const savedTheme = localStorage.getItem('lifeos-theme') || 'dark';
  applyTheme(savedTheme);

  if (themeBtn) {
    themeBtn.addEventListener('click', function () {
      const current = html.getAttribute('data-bs-theme');
      const next = current === 'dark' ? 'light' : 'dark';
      applyTheme(next);
      localStorage.setItem('lifeos-theme', next);
    });
  }

  function applyTheme(theme) {
    html.setAttribute('data-bs-theme', theme);
    if (themeIcon) {
      themeIcon.className = theme === 'dark' ? 'bi bi-sun-fill' : 'bi bi-moon-stars-fill';
    }
    // Adjust custom CSS vars for light mode
    if (theme === 'light') {
      html.style.setProperty('--bg-base', '#f1f5f9');
      html.style.setProperty('--bg-surface', '#ffffff');
      html.style.setProperty('--bg-surface-elevated', '#f8fafc');
      html.style.setProperty('--bg-surface-hover', '#e2e8f0');
      html.style.setProperty('--text-main', '#0f172a');
      html.style.setProperty('--text-muted', '#475569');
      html.style.setProperty('--text-dim', '#94a3b8');
      html.style.setProperty('--border-subtle', 'rgba(0,0,0,0.08)');
      html.style.setProperty('--border-card', 'rgba(0,0,0,0.10)');
    } else {
      html.style.setProperty('--bg-base', '#0c1222');
      html.style.setProperty('--bg-surface', '#151f32');
      html.style.setProperty('--bg-surface-elevated', '#1e2c45');
      html.style.setProperty('--bg-surface-hover', '#263857');
      html.style.setProperty('--text-main', '#f8fafc');
      html.style.setProperty('--text-muted', '#94a3b8');
      html.style.setProperty('--text-dim', '#64748b');
      html.style.setProperty('--border-subtle', 'rgba(255,255,255,0.07)');
      html.style.setProperty('--border-card', 'rgba(255,255,255,0.08)');
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
    container.style.cssText = 'position:fixed;bottom:1.5rem;right:1.5rem;z-index:9999;display:flex;flex-direction:column;gap:0.5rem;';
    document.body.appendChild(container);
  }

  const iconMap = {
    success: 'bi-check-circle-fill text-success',
    danger: 'bi-exclamation-circle-fill text-danger',
    warning: 'bi-exclamation-triangle-fill text-warning',
    info: 'bi-info-circle-fill text-info',
  };

  const toast = document.createElement('div');
  toast.className = 'toast show align-items-center border-0';
  toast.style.cssText = 'background: var(--bg-surface-elevated); color: var(--text-main); border: 1px solid var(--border-card) !important; border-radius: 12px; min-width: 280px; box-shadow: 0 8px 24px rgba(0,0,0,0.4);';
  toast.innerHTML = `
    <div class="d-flex align-items-center gap-2 p-3">
      <i class="bi ${iconMap[type] || iconMap.info} fs-5"></i>
      <span class="flex-grow-1 small fw-medium">${message}</span>
      <button type="button" class="btn-close btn-close-white btn-close-sm ms-auto" style="filter:invert(0.5);" onclick="this.closest('.toast').remove()"></button>
    </div>
  `;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}
