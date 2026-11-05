/**
 * Life OS — hiệu ứng tương tác (LifeFX)
 *
 *  1. Số KPI đếm chạy khi mở trang (một lần, khi thẻ hiện ra trong màn hình)
 *  2. Thẻ KPI nghiêng 3D + vệt sáng chạy theo con trỏ
 *  3. "+N XP" bay lên khi XP tăng; hiệu ứng lên cấp kèm pháo giấy
 *  4. Pháo giấy dùng chung: LifeFX.confetti(x, y)
 *  5. Khối nội dung hiện ra lần lượt (trong màn hình) hoặc khi cuộn tới
 *  6. Thanh tiến độ chạy từ 0 bằng lò xo
 *  7. Gợn sóng tại điểm bấm  8. Nút chính hút theo con trỏ  9. Biểu đồ mọc lần lượt
 *
 * Tôn trọng prefers-reduced-motion: tắt chuyển động, vẫn hiển thị kết quả cuối.
 */
window.LifeFX = (function () {
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const canHover = window.matchMedia('(hover: hover) and (pointer: fine)');
  const still = () => reduceMotion.matches;

  // ───────────────────────── 1. Count-up ─────────────────────────
  // Hiểu định dạng Việt Nam: "12.600.000", "3,73", "0,0", "+15", "-250.000"
  function parseVN(token) {
    let m = token.match(/^(\d{1,3}(?:\.\d{3})+)(?:,(\d+))?$/);
    if (m) return { value: parseFloat(m[1].replace(/\./g, '') + (m[2] ? '.' + m[2] : '')), decimals: m[2] ? m[2].length : 0, group: true, sep: ',' };
    m = token.match(/^(\d+)(?:([.,])(\d+))?$/);
    if (m) return { value: parseFloat(m[1] + (m[3] ? '.' + m[3] : '')), decimals: m[3] ? m[3].length : 0, group: false, sep: m[2] || ',' };
    return null;
  }

  function formatVN(n, fmt) {
    let [int, frac] = n.toFixed(fmt.decimals).split('.');
    if (fmt.group) int = int.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
    return frac ? int + fmt.sep + frac : int;
  }

  function countUp(el) {
    // Chỉ đụng vào text node đầu tiên có số, giữ nguyên các thẻ <small> đơn vị
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      const match = node.nodeValue.match(/\d[\d.,]*/);
      if (!match) continue;
      const fmt = parseVN(match[0]);
      if (!fmt || fmt.value === 0) return;
      const before = node.nodeValue.slice(0, match.index);
      const after = node.nodeValue.slice(match.index + match[0].length);
      const duration = Math.min(1400, 700 + Math.log10(fmt.value + 1) * 120);
      const start = performance.now();
      el.classList.add('is-counting');
      const tick = now => {
        const t = Math.min((now - start) / duration, 1);
        const eased = 1 - Math.pow(1 - t, 4); // easeOutQuart: nhanh rồi chậm dần
        node.nodeValue = before + formatVN(fmt.value * eased, fmt) + after;
        if (t < 1) requestAnimationFrame(tick);
        else { node.nodeValue = before + match[0] + after; el.classList.remove('is-counting'); }
      };
      requestAnimationFrame(tick);
      return;
    }
  }

  function initCountUp() {
    if (still()) return;
    const els = document.querySelectorAll('.kpi-value:not([data-no-count])');
    if (!('IntersectionObserver' in window)) return els.forEach(countUp);
    const io = new IntersectionObserver(entries => {
      entries.forEach(e => {
        if (!e.isIntersecting) return;
        io.unobserve(e.target);
        // Bắt đầu đếm khi thẻ chứa nó đã nổi lên (theo thứ tự xuất hiện)
        const host = e.target.closest('.fx-in');
        const delay = host ? parseInt(host.style.getPropertyValue('--fx-delay')) || 0 : 0;
        setTimeout(() => countUp(e.target), delay + 150);
      });
    }, { threshold: 0.4 });
    els.forEach(el => io.observe(el));
  }

  // ───────────────────── 2. Tilt + spotlight ─────────────────────
  const MAX_TILT = 7; // độ

  function initTilt() {
    if (still() || !canHover.matches) return;
    document.querySelectorAll('.kpi-card').forEach(card => {
      let frame = null;
      card.addEventListener('pointermove', e => {
        const r = card.getBoundingClientRect();
        const px = (e.clientX - r.left) / r.width;   // 0..1
        const py = (e.clientY - r.top) / r.height;
        cancelAnimationFrame(frame);
        frame = requestAnimationFrame(() => {
          card.style.setProperty('--rx', ((0.5 - py) * MAX_TILT).toFixed(2) + 'deg');
          card.style.setProperty('--ry', ((px - 0.5) * MAX_TILT).toFixed(2) + 'deg');
          card.style.setProperty('--mx', (px * 100).toFixed(1) + '%');
          card.style.setProperty('--my', (py * 100).toFixed(1) + '%');
        });
      });
      card.addEventListener('pointerenter', () => card.classList.add('is-tilting'));
      card.addEventListener('pointerleave', () => {
        cancelAnimationFrame(frame);
        card.classList.remove('is-tilting');
        card.style.removeProperty('--rx');
        card.style.removeProperty('--ry');
      });
    });
  }

  // ───────────────────────── 3. Confetti ─────────────────────────
  const COLORS = ['#818cf8', '#c084fc', '#f472b6', '#fbbf24', '#34d399', '#38bdf8'];
  let canvas, ctx, particles = [], running = false;

  function ensureCanvas() {
    if (canvas) return;
    canvas = document.createElement('canvas');
    canvas.className = 'fx-confetti';
    canvas.setAttribute('aria-hidden', 'true');
    document.body.appendChild(canvas);
    ctx = canvas.getContext('2d');
    const resize = () => {
      const dpr = window.devicePixelRatio || 1;
      canvas.width = innerWidth * dpr;
      canvas.height = innerHeight * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    addEventListener('resize', resize);
  }

  function confetti(x = innerWidth / 2, y = innerHeight / 3, count = 90) {
    if (still()) return;
    ensureCanvas();
    for (let i = 0; i < count; i++) {
      const angle = Math.random() * Math.PI * 2;
      const speed = 4 + Math.random() * 7;
      particles.push({
        x, y,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed - 5,
        size: 5 + Math.random() * 5,
        rot: Math.random() * Math.PI,
        vr: (Math.random() - 0.5) * 0.3,
        color: COLORS[(Math.random() * COLORS.length) | 0],
        life: 0,
        ttl: 70 + Math.random() * 40,
        round: Math.random() < 0.3,
      });
    }
    if (!running) { running = true; requestAnimationFrame(step); }
  }

  function step() {
    ctx.clearRect(0, 0, innerWidth, innerHeight);
    particles = particles.filter(p => p.life < p.ttl && p.y < innerHeight + 20);
    for (const p of particles) {
      p.life++;
      p.vy += 0.22;          // trọng lực
      p.vx *= 0.985;         // lực cản không khí
      p.x += p.vx;
      p.y += p.vy;
      p.rot += p.vr;
      ctx.save();
      ctx.globalAlpha = Math.max(0, 1 - p.life / p.ttl);
      ctx.translate(p.x, p.y);
      ctx.rotate(p.rot);
      ctx.fillStyle = p.color;
      if (p.round) { ctx.beginPath(); ctx.arc(0, 0, p.size / 2, 0, Math.PI * 2); ctx.fill(); }
      else ctx.fillRect(-p.size / 2, -p.size / 4, p.size, p.size / 2);
      ctx.restore();
    }
    if (particles.length) requestAnimationFrame(step);
    else { running = false; ctx.clearRect(0, 0, innerWidth, innerHeight); }
  }

  // ───────────────────── 4. XP gain / level up ─────────────────────
  function xpAnchor() {
    const meter = document.getElementById('xpMeter');
    const visible = meter && meter.offsetParent !== null && meter.getBoundingClientRect().width > 0;
    const target = visible ? meter : document.querySelector('.topbar-chip');
    if (!target) return { x: innerWidth - 80, y: 60 };
    const r = target.getBoundingClientRect();
    return { x: r.left + r.width / 2, y: r.top };
  }

  function floatText(text, x, y, variant = 'xp') {
    const el = document.createElement('div');
    el.className = 'fx-float fx-float--' + variant;
    el.textContent = text;
    el.setAttribute('role', 'status');
    el.style.left = x + 'px';
    el.style.top = y + 'px';
    document.body.appendChild(el);
    el.addEventListener('animationend', () => el.remove());
    if (still()) setTimeout(() => el.remove(), 1600);
  }

  function xpGain(amount, at) {
    if (!amount) return;
    const pos = at || xpAnchor();
    floatText('+' + amount + ' XP', pos.x, pos.y, 'xp');
    const meter = document.getElementById('xpMeter');
    if (meter) {
      meter.classList.remove('fx-pulse');
      void meter.offsetWidth; // chạy lại animation
      meter.classList.add('fx-pulse');
    }
  }

  function levelUp(level) {
    const banner = document.createElement('div');
    banner.className = 'fx-levelup';
    banner.setAttribute('role', 'status');
    banner.innerHTML = '<div class="fx-levelup-card"><div class="fx-levelup-icon">⚔️</div><div><div class="fx-levelup-title"></div><div class="fx-levelup-sub">Hồi 10 HP. Tiếp tục phát huy!</div></div></div>';
    banner.querySelector('.fx-levelup-title').textContent = 'Lên cấp ' + level + '!';
    document.body.appendChild(banner);
    confetti(innerWidth / 2, innerHeight * 0.35, 160);
    setTimeout(() => banner.classList.add('is-leaving'), 2600);
    setTimeout(() => banner.remove(), 3100);
  }

  // So XP/level với lần xem trước (lưu theo user trong sessionStorage) để báo phần thưởng
  // cho mọi thao tác, kể cả form gửi đi rồi tải lại trang (tick habit, xong task...).
  function initXPWatcher() {
    const meter = document.getElementById('xpMeter');
    if (!meter) return;
    const key = 'lifeos-xp-' + meter.dataset.user;
    const now = { level: +meter.dataset.level, xp: +meter.dataset.xp };
    let prev = null;
    try { prev = JSON.parse(sessionStorage.getItem(key)); } catch (e) {}
    try { sessionStorage.setItem(key, JSON.stringify(now)); } catch (e) {}
    if (!prev) return;
    // Chờ trang ổn định để vị trí neo đúng
    setTimeout(() => report(prev, now), 350);
  }

  function report(prev, now) {
    if (now.level > prev.level) levelUp(now.level);
    else if (now.level === prev.level && now.xp > prev.xp) xpGain(now.xp - prev.xp);
  }

  /** Gọi sau thao tác AJAX trả về user_xp / user_level mới. */
  function syncXP(xp, level, at) {
    const meter = document.getElementById('xpMeter');
    if (!meter || xp == null) return;
    const prev = { level: +meter.dataset.level, xp: +meter.dataset.xp };
    const now = { level: level == null ? prev.level : +level, xp: +xp };
    meter.dataset.level = now.level;
    meter.dataset.xp = now.xp;
    // Cùng cấp thì cập nhật luôn số và thanh XP trên sidebar (lên cấp thì lần tải sau sẽ đúng)
    const next = +meter.dataset.next;
    if (now.level === prev.level && next) {
      const label = meter.querySelector('.xp-count');
      const bar = meter.querySelector('.progress-bar');
      if (label) label.textContent = now.xp + ' / ' + next + ' XP';
      if (bar) bar.style.width = Math.min(100, (now.xp / next) * 100) + '%';
    }
    try { sessionStorage.setItem('lifeos-xp-' + meter.dataset.user, JSON.stringify(now)); } catch (e) {}
    if (now.level > prev.level) levelUp(now.level);
    else if (now.xp > prev.xp) xpGain(now.xp - prev.xp, at);
  }

  // ───────────── 5. Khối nội dung hiện ra lần lượt ─────────────
  // Khối trong màn hình: nối đuôi nhau theo thứ tự. Khối bên dưới: hiện khi cuộn tới.
  const STAGGER = 70, MAX_DELAY = 480;

  function initEntrance() {
    const root = document.documentElement;
    if (!root.classList.contains('fx-ready')) return;
    const blocks = [...document.querySelectorAll('.content-container .row > [class*="col"]')];
    const reveal = (el, delay) => {
      el.style.setProperty('--fx-delay', delay + 'ms');
      el.classList.add('fx-in');
    };
    let order = 0;
    const later = [];
    blocks.forEach(el => {
      const r = el.getBoundingClientRect();
      if (r.top < innerHeight && r.bottom > 0) reveal(el, Math.min(order++ * STAGGER, MAX_DELAY));
      else later.push(el);
    });
    if (!later.length) return;
    if (!('IntersectionObserver' in window)) return later.forEach(el => reveal(el, 0));
    const io = new IntersectionObserver(entries => {
      // Các khối cùng lọt vào màn hình trong một lần cuộn cũng nối đuôi nhau
      entries.filter(e => e.isIntersecting).forEach((e, i) => {
        io.unobserve(e.target);
        reveal(e.target, Math.min(i * STAGGER, MAX_DELAY));
      });
    }, { rootMargin: '0px 0px -8% 0px' });
    later.forEach(el => io.observe(el));
  }

  // ───────────── 6. Thanh tiến độ chạy từ 0 khi cuộn tới ─────────────
  function initProgressBars() {
    if (!document.documentElement.classList.contains('fx-ready') || !('IntersectionObserver' in window)) return;
    const bars = [...document.querySelectorAll('.progress')].filter(p => !p.closest('.xp-meter'));
    bars.forEach(p => p.classList.add('fx-bar-wait'));
    const io = new IntersectionObserver(entries => {
      entries.filter(e => e.isIntersecting).forEach((e, i) => {
        io.unobserve(e.target);
        const p = e.target;
        // Chờ khối chứa nó hiện ra xong phần lớn rồi mới chạy
        const host = p.closest('.fx-in');
        const base = host ? parseInt(host.style.getPropertyValue('--fx-delay')) || 0 : 0;
        p.style.setProperty('--fx-delay', (base + 250 + i * 60) + 'ms');
        p.classList.add('fx-bar-go');
        requestAnimationFrame(() => requestAnimationFrame(() => p.classList.remove('fx-bar-wait')));
      });
    }, { threshold: 0.2 });
    bars.forEach(p => io.observe(p));
  }

  // ───────────── 7. Gợn sóng tại điểm bấm ─────────────
  const RIPPLE_TARGETS = '.btn, .sidebar-link, .bottom-nav a, .icon-btn';

  function initRipple() {
    document.addEventListener('pointerdown', e => {
      if (still() || e.button !== 0) return;
      const target = e.target.closest(RIPPLE_TARGETS);
      if (!target || target.disabled) return;
      let host = target.querySelector(':scope > .fx-ripple-host');
      if (!host) {
        host = document.createElement('span');
        host.className = 'fx-ripple-host';
        host.setAttribute('aria-hidden', 'true');
        target.prepend(host);
      }
      const r = target.getBoundingClientRect();
      const size = Math.max(r.width, r.height) * 2.4;
      const dot = document.createElement('span');
      dot.className = 'fx-ripple';
      dot.style.width = dot.style.height = size + 'px';
      dot.style.left = (e.clientX - r.left) + 'px';
      dot.style.top = (e.clientY - r.top) + 'px';
      host.appendChild(dot);
      dot.addEventListener('animationend', () => dot.remove());
    }, { passive: true });
  }

  // ───────────── 8. Nút chính hút theo con trỏ ─────────────
  const MAGNET = 0.28, MAGNET_MAX = 7; // tỉ lệ bám, độ lệch tối đa (px)

  function initMagnet() {
    if (still() || !canHover.matches) return;
    document.querySelectorAll('.btn-primary, .btn-kanban').forEach(btn => {
      btn.addEventListener('pointermove', e => {
        const r = btn.getBoundingClientRect();
        const clamp = v => Math.max(-MAGNET_MAX, Math.min(MAGNET_MAX, v));
        btn.style.setProperty('--mag-x', clamp((e.clientX - r.left - r.width / 2) * MAGNET) + 'px');
        btn.style.setProperty('--mag-y', clamp((e.clientY - r.top - r.height / 2) * MAGNET) + 'px');
        btn.classList.add('is-magnet');
      });
      btn.addEventListener('pointerleave', () => {
        btn.classList.remove('is-magnet');
        btn.style.removeProperty('--mag-x');
        btn.style.removeProperty('--mag-y');
      });
    });
  }

  // ───────────── 9. Biểu đồ: cột/điểm mọc lên lần lượt ─────────────
  // Đặt mặc định ngay (không chờ DOMContentLoaded) vì các trang tạo chart ở block extra_js.
  if (window.Chart && !still()) {
    Chart.defaults.animation = {
      duration: 900,
      easing: 'easeOutQuart',
      delay(ctx) {
        if (ctx.type !== 'data' || ctx.mode !== 'default' || ctx.dropped) return 0;
        ctx.dropped = true;
        return 250 + ctx.dataIndex * 45 + ctx.datasetIndex * 120;
      },
    };
  }

  document.addEventListener('DOMContentLoaded', () => {
    initEntrance();
    initCountUp();
    initTilt();
    initXPWatcher();
    initProgressBars();
    initRipple();
    initMagnet();
  });

  return { confetti, xpGain, levelUp, syncXP, floatText, countUp };
})();
