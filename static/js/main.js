/* ═══════════════════════════════════════════════════════════════
   Library Management System — main.js
   Pure Vanilla JavaScript — No jQuery, No Framework
   ═══════════════════════════════════════════════════════════════ */

'use strict';

/* ── Dark Mode ────────────────────────────────────────────────── */
const ThemeManager = {
  init() {
    const saved = localStorage.getItem('lms-theme') || 'light';
    this.apply(saved);
    document.querySelectorAll('.dark-toggle-btn').forEach(btn => {
      btn.addEventListener('click', () => this.toggle());
    });
  },
  apply(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('lms-theme', theme);

    if (theme === 'dark') {
      document.body.classList.add('dark-mode');
    } else {
      document.body.classList.remove('dark-mode');
    }

    const icons = document.querySelectorAll('.theme-icon');
    icons.forEach(i => { i.textContent = theme === 'dark' ? '☀️' : '🌙'; });
    const labels = document.querySelectorAll('.theme-label');
    labels.forEach(l => { l.textContent = theme === 'dark' ? 'Light Mode' : 'Dark Mode'; });
  },
  toggle() {
    const current = document.documentElement.getAttribute('data-theme') || 'light';
    this.apply(current === 'dark' ? 'light' : 'dark');
  }
};

/* ── Sidebar Collapse ─────────────────────────────────────────── */
const SidebarManager = {
  init() {
    const sidebar     = document.querySelector('.sidebar');
    const mainContent = document.querySelector('.main-content');
    const toggleBtn   = document.querySelector('.header-toggle');
    const overlay     = document.querySelector('.sidebar-overlay');

    if (!sidebar) return;

    // Restore state
    const collapsed = localStorage.getItem('lms-sidebar') === 'collapsed';
    if (collapsed) {
      sidebar.classList.add('collapsed');
      mainContent?.classList.add('expanded');
    }

    toggleBtn?.addEventListener('click', () => {
      const isCollapsed = sidebar.classList.toggle('collapsed');
      mainContent?.classList.toggle('expanded', isCollapsed);
      localStorage.setItem('lms-sidebar', isCollapsed ? 'collapsed' : 'open');

      // Mobile
      if (window.innerWidth <= 768) {
        sidebar.classList.remove('collapsed');
        sidebar.classList.toggle('mobile-open');
      }
    });

    overlay?.addEventListener('click', () => {
      sidebar.classList.remove('mobile-open');
    });

    // Highlight active nav item
    const currentPath = window.location.pathname;
    document.querySelectorAll('.nav-item').forEach(item => {
      const href = item.getAttribute('href');
      if (href && (currentPath === href || (href !== '/' && currentPath.startsWith(href)))) {
        item.classList.add('active');
      }
    });
  }
};

/* ── Toast Notifications ──────────────────────────────────────── */
const Toast = {
  container: null,

  init() {
    this.container = document.querySelector('.toast-container');
    if (!this.container) {
      this.container = document.createElement('div');
      this.container.className = 'toast-container';
      document.body.appendChild(this.container);
    }
    // Auto-show Django messages on page load
    this.showDjangoMessages();
  },

  show(message, type = 'info', duration = 4000) {
    const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
      <span class="toast-icon">${icons[type] || 'ℹ️'}</span>
      <span class="toast-message">${message}</span>
      <button class="toast-close" onclick="Toast.dismiss(this.parentElement)">✕</button>
    `;
    this.container.appendChild(toast);
    setTimeout(() => this.dismiss(toast), duration);
    return toast;
  },

  dismiss(toast) {
    if (!toast || !toast.parentElement) return;
    toast.classList.add('toast-exit');
    setTimeout(() => toast.remove(), 300);
  },

  showDjangoMessages() {
    // Django messages rendered as hidden data-toast elements
    document.querySelectorAll('[data-toast]').forEach(el => {
      const msg  = el.dataset.toast;
      const type = el.dataset.toastType || 'info';
      if (msg) this.show(msg, type);
      el.remove();
    });
  }
};

/* ── Confirm Dialog ───────────────────────────────────────────── */
const ConfirmDialog = {
  init() {
    // Create modal DOM once
    if (document.querySelector('.modal-overlay')) return;

    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.id = 'confirmModal';
    modal.innerHTML = `
      <div class="modal-box">
        <div class="modal-icon" id="confirmIcon">⚠️</div>
        <h3 class="modal-title" id="confirmTitle">Are you sure?</h3>
        <p class="modal-message" id="confirmMessage">This action cannot be undone.</p>
        <div class="modal-actions">
          <button class="btn btn-secondary" id="confirmCancel">Cancel</button>
          <button class="btn btn-danger" id="confirmOk">Delete</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);

    document.getElementById('confirmCancel').addEventListener('click', () => this.hide());
    modal.addEventListener('click', e => { if (e.target === modal) this.hide(); });
  },

  show({ title = 'Are you sure?', message = 'This cannot be undone.', icon = '🗑️',
         okText = 'Delete', okClass = 'btn-danger', onConfirm }) {
    document.getElementById('confirmTitle').textContent   = title;
    document.getElementById('confirmMessage').textContent = message;
    document.getElementById('confirmIcon').textContent    = icon;
    const okBtn = document.getElementById('confirmOk');
    okBtn.textContent  = okText;
    okBtn.className    = `btn ${okClass}`;
    okBtn.onclick      = () => { this.hide(); onConfirm?.(); };
    document.getElementById('confirmModal').classList.add('show');
  },

  hide() {
    document.getElementById('confirmModal')?.classList.remove('show');
  }
};

/* ── Delete Buttons with Confirm ──────────────────────────────── */
function initDeleteButtons() {
  document.querySelectorAll('[data-delete-url]').forEach(btn => {
    btn.addEventListener('click', () => {
      const url  = btn.dataset.deleteUrl;
      const name = btn.dataset.deleteName || 'this item';
      ConfirmDialog.show({
        title:     'Delete ' + name + '?',
        message:   `Are you sure you want to delete "${name}"? This action is permanent.`,
        icon:      '🗑️',
        okText:    'Yes, Delete',
        onConfirm: () => { window.location.href = url; }
      });
    });
  });
}

/* ── Autocomplete Search ──────────────────────────────────────── */
class Autocomplete {
  constructor(inputEl, apiUrl, onSelect) {
    this.input    = inputEl;
    this.apiUrl   = apiUrl;
    this.onSelect = onSelect;
    this.dropdown = null;
    this.debounceTimer = null;
    this.build();
  }

  build() {
    // Wrap input
    this.input.parentElement.style.position = 'relative';

    // Create dropdown
    this.dropdown = document.createElement('div');
    this.dropdown.className = 'autocomplete-dropdown';
    this.input.parentElement.appendChild(this.dropdown);

    this.input.addEventListener('input', () => {
      clearTimeout(this.debounceTimer);
      this.debounceTimer = setTimeout(() => this.search(), 250);
    });

    this.input.addEventListener('keydown', e => {
      if (e.key === 'Escape') this.hide();
    });

    document.addEventListener('click', e => {
      if (!this.input.parentElement.contains(e.target)) this.hide();
    });
  }

  async search() {
    const q = this.input.value.trim();
    if (q.length < 2) { this.hide(); return; }

    try {
      const res  = await fetch(`${this.apiUrl}?q=${encodeURIComponent(q)}`);
      const data = await res.json();
      this.render(data.results || []);
    } catch (err) {
      console.error('Autocomplete error:', err);
    }
  }

  render(results) {
    if (!results.length) { this.hide(); return; }

    this.dropdown.innerHTML = results.map(r => `
      <div class="autocomplete-item" data-id="${r.id}" data-label="${r.title || r.name}">
        <div class="autocomplete-item-title">${r.title || r.name}</div>
        <div class="autocomplete-item-sub">${r.author || r.student_id || ''} 
          ${r.available_copies !== undefined ? `· ${r.available_copies} copies` : ''}
          ${r.department || ''}
        </div>
      </div>
    `).join('');

    this.dropdown.querySelectorAll('.autocomplete-item').forEach(item => {
      item.addEventListener('click', () => {
        this.input.value = item.dataset.label;
        this.onSelect?.(item.dataset);
        this.hide();
      });
    });

    this.dropdown.classList.add('show');
  }

  hide() { this.dropdown.classList.remove('show'); }
}

/* ── Live Search (filter as you type) ────────────────────────── */
function initLiveSearch() {
  const searchInput = document.querySelector('[data-live-search]');
  if (!searchInput) return;

  let debounceTimer;
  searchInput.addEventListener('input', () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      const form = searchInput.closest('form');
      if (form) form.submit();
    }, 500);
  });
}

/* ── Header Date/Time ─────────────────────────────────────────── */
function updateDateTime() {
  const el = document.querySelector('.header-date');
  if (!el) return;
  const now = new Date();
  const options = { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' };
  el.textContent = now.toLocaleDateString('en-IN', options);
}

/* ── Animate Stats on Load ────────────────────────────────────── */
function animateCounters() {
  document.querySelectorAll('.stat-number[data-count]').forEach(el => {
    const target = parseInt(el.dataset.count, 10);
    let current = 0;
    const step = Math.max(1, Math.floor(target / 40));
    const timer = setInterval(() => {
      current = Math.min(current + step, target);
      el.textContent = current.toLocaleString('en-IN');
      if (current >= target) clearInterval(timer);
    }, 30);
  });
}

/* ── Fade-in animation observer ──────────────────────────────── */
function initFadeIn() {
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.style.animationPlayState = 'running';
      }
    });
  }, { threshold: 0.1 });

  document.querySelectorAll('.fade-in').forEach(el => {
    el.style.animationPlayState = 'paused';
    observer.observe(el);
  });
}

/* ── Return Book Quick Action ─────────────────────────────────── */
function initReturnButtons() {
  document.querySelectorAll('[data-return-url]').forEach(btn => {
    btn.addEventListener('click', () => {
      const url  = btn.dataset.returnUrl;
      const name = btn.dataset.bookName || 'this book';
      ConfirmDialog.show({
        title:     'Return Book?',
        message:   `Mark "${name}" as returned? Fine (if any) will be calculated automatically.`,
        icon:      '📚',
        okText:    'Yes, Return',
        okClass:   'btn-success',
        onConfirm: () => { window.location.href = url; }
      });
    });
  });
}

/* ── Table Sort ───────────────────────────────────────────────── */
function initTableSort() {
  document.querySelectorAll('th[data-sort]').forEach(th => {
    th.style.cursor = 'pointer';
    th.addEventListener('click', () => {
      const url    = new URL(window.location);
      const col    = th.dataset.sort;
      const curDir = url.searchParams.get('sort_dir') || 'asc';
      url.searchParams.set('sort',     col);
      url.searchParams.set('sort_dir', curDir === 'asc' ? 'desc' : 'asc');
      window.location.href = url.toString();
    });
  });
}

/* ── Fine Calculator Preview ──────────────────────────────────── */
function initFineCalculator() {
  const dueDateInput = document.getElementById('id_due_date');
  const fineDisplay  = document.getElementById('fine-preview');
  if (!dueDateInput || !fineDisplay) return;

  dueDateInput.addEventListener('change', () => {
    const due   = new Date(dueDateInput.value);
    const today = new Date();
    if (today > due) {
      const days = Math.floor((today - due) / (1000 * 60 * 60 * 24));
      fineDisplay.textContent = `⚠️ Already ${days} day(s) overdue — Fine: ₹${days * 5}`;
      fineDisplay.style.color = 'var(--accent-red)';
    } else {
      fineDisplay.textContent = '';
    }
  });
}

/* ── Issue Days → Due Date Preview ───────────────────────────── */
function initIssueDaysPreview() {
  const daysInput  = document.getElementById('days');
  const preview    = document.getElementById('due-date-preview');
  if (!daysInput || !preview) return;

  const update = () => {
    const days = parseInt(daysInput.value, 10);
    if (!isNaN(days) && days > 0) {
      const due = new Date();
      due.setDate(due.getDate() + days);
      preview.textContent = `Due: ${due.toLocaleDateString('en-IN', { day:'numeric', month:'short', year:'numeric' })}`;
    }
  };
  daysInput.addEventListener('input', update);
  update();
}

/* ── INIT ALL ─────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  ThemeManager.init();
  SidebarManager.init();
  Toast.init();
  ConfirmDialog.init();
  initDeleteButtons();
  initReturnButtons();
  initLiveSearch();
  initTableSort();
  initFineCalculator();
  initIssueDaysPreview();
  updateDateTime();
  animateCounters();
  initFadeIn();

  // Book search autocomplete (on issue form)
  const bookSearchInput = document.getElementById('book-search-input');
  if (bookSearchInput) {
    new Autocomplete(bookSearchInput, '/api/search-books/', data => {
      const hidden = document.getElementById('book_id');
      if (hidden) hidden.value = data.id;
    });
  }

  // Student search autocomplete (on issue form)
  const studentSearchInput = document.getElementById('student-search-input');
  if (studentSearchInput) {
    new Autocomplete(studentSearchInput, '/api/search-students/', data => {
      const hidden = document.getElementById('student_id');
      if (hidden) hidden.value = data.id;
    });
  }
});

// Expose globally
window.Toast = Toast;
window.ConfirmDialog = ConfirmDialog;