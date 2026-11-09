/* KnowBridge AI — Main JavaScript */

// ─── Toast Notifications ─────────────────────────────────────────
const ToastManager = {
  container: null,
  init() {
    this.container = document.getElementById('toast-container');
    if (!this.container) {
      this.container = document.createElement('div');
      this.container.id = 'toast-container';
      this.container.className = 'toast-container';
      document.body.appendChild(this.container);
    }
  },
  show(message, type = 'info', duration = 4000) {
    if (!this.container) this.init();
    const icons = { success: '✅', danger: '❌', warning: '⚠️', info: 'ℹ️' };
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
      <span class="toast-icon">${icons[type] || icons.info}</span>
      <span class="toast-msg">${message}</span>
      <button onclick="this.parentElement.remove()" style="margin-left:auto;background:none;border:none;cursor:pointer;color:#9CA3AF;font-size:1rem;padding:0 0 0 .5rem;">&times;</button>`;
    this.container.appendChild(toast);
    setTimeout(() => { toast.style.opacity = '0'; toast.style.transition = 'opacity .3s'; setTimeout(() => toast.remove(), 300); }, duration);
  }
};

// ─── Modal Manager ───────────────────────────────────────────────
const Modal = {
  open(id) {
    const m = document.getElementById(id);
    if (m) { m.classList.add('show'); document.body.style.overflow = 'hidden'; }
  },
  close(id) {
    const m = document.getElementById(id);
    if (m) { m.classList.remove('show'); document.body.style.overflow = ''; }
  },
  closeAll() {
    document.querySelectorAll('.modal-backdrop.show').forEach(m => {
      m.classList.remove('show'); document.body.style.overflow = '';
    });
  }
};
document.addEventListener('keydown', e => { if (e.key === 'Escape') Modal.closeAll(); });
document.addEventListener('click', e => {
  if (e.target.classList.contains('modal-backdrop')) Modal.closeAll();
});

// ─── Sidebar Toggle ──────────────────────────────────────────────
function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  if (sidebar) sidebar.classList.toggle('open');
}

// ─── CSRF Token Helper ───────────────────────────────────────────
function getCSRF() {
  const m = document.querySelector('meta[name="csrf-token"]');
  return m ? m.content : '';
}

// ─── API Helpers ─────────────────────────────────────────────────
async function apiPost(url, formData) {
  const r = await fetch(url, {
    method: 'POST',
    headers: { 'X-CSRFToken': getCSRF() },
    body: formData
  });
  return r.json();
}

async function apiPut(url, data) {
  const r = await fetch(url, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRF() },
    body: JSON.stringify(data)
  });
  return r.json();
}

// ─── Knowledge Review Actions ─────────────────────────────────────
async function approveKnowledge(id, card) {
  const btn = card.querySelector('.approve-btn');
  if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner"></span>'; }
  const fd = new FormData();
  fd.append('csrf_token', getCSRF());
  const res = await apiPost(`/knowledge/${id}/approve`, fd);
  if (res.success) {
    card.classList.remove('pending');
    card.classList.add('approved');
    card.querySelector('.kc-actions').innerHTML = '<span class="badge badge-success">✅ Approved</span>';
    ToastManager.show(res.message, 'success');
    updateReviewCount();
  } else {
    ToastManager.show(res.error || 'Error approving.', 'danger');
    if (btn) { btn.disabled = false; btn.textContent = 'Approve'; }
  }
}

async function rejectKnowledge(id, card, reason) {
  const fd = new FormData();
  fd.append('csrf_token', getCSRF());
  fd.append('reason', reason || 'No reason provided');
  const res = await apiPost(`/knowledge/${id}/reject`, fd);
  if (res.success) {
    card.classList.remove('pending');
    card.classList.add('rejected');
    card.querySelector('.kc-actions').innerHTML = '<span class="badge badge-danger">❌ Rejected</span>';
    ToastManager.show('Item rejected.', 'warning');
    updateReviewCount();
  } else {
    ToastManager.show(res.error || 'Error.', 'danger');
  }
}

function updateReviewCount() {
  const el = document.getElementById('pending-review-count');
  if (el) {
    const c = parseInt(el.textContent) - 1;
    el.textContent = Math.max(0, c);
  }
}

// ─── Task Status Update ───────────────────────────────────────────
async function updateTaskStatus(id, status) {
  const res = await apiPut(`/api/tasks/${id}`, { status });
  if (res.success) {
    ToastManager.show('Task updated.', 'success');
  } else {
    ToastManager.show('Failed to update task.', 'danger');
  }
}

// ─── Risk Status Update ───────────────────────────────────────────
async function updateRiskStatus(id, status) {
  const res = await apiPut(`/api/risks/${id}`, { status });
  if (res.success) {
    ToastManager.show('Risk updated.', 'success');
  } else {
    ToastManager.show('Failed.', 'danger');
  }
}

// ─── Drag & Drop Upload ───────────────────────────────────────────
function initUploadZone(zoneId, inputId) {
  const zone = document.getElementById(zoneId);
  const input = document.getElementById(inputId);
  if (!zone || !input) return;

  zone.addEventListener('click', () => input.click());
  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', e => {
    e.preventDefault();
    zone.classList.remove('drag-over');
    if (e.dataTransfer.files.length > 0) {
      input.files = e.dataTransfer.files;
      updateFileLabel(zoneId, e.dataTransfer.files[0].name);
    }
  });
  input.addEventListener('change', () => {
    if (input.files.length > 0) updateFileLabel(zoneId, input.files[0].name);
  });
}

function updateFileLabel(zoneId, name) {
  const zone = document.getElementById(zoneId);
  if (zone) {
    zone.querySelector('p').innerHTML = `<strong>${name}</strong> selected. Ready to upload.`;
    zone.style.borderColor = 'var(--primary)';
    zone.style.background = 'var(--primary-light)';
  }
}

// ─── Tabs ─────────────────────────────────────────────────────────
function initTabs(containerId) {
  const container = document.getElementById(containerId);
  if (!container) return;
  const tabs = container.querySelectorAll('.kb-tab');
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      const target = tab.dataset.tab;
      container.querySelectorAll('.tab-content').forEach(c => {
        c.style.display = c.id === target ? 'block' : 'none';
      });
    });
  });
  // Show first tab
  if (tabs.length) tabs[0].click();
}

// ─── Confirm Delete ───────────────────────────────────────────────
function confirmDelete(formId, message) {
  if (confirm(message || 'Are you sure? This action cannot be undone.')) {
    document.getElementById(formId).submit();
  }
}

// ─── Search Filter ────────────────────────────────────────────────
function initSearch(inputId, tableId) {
  const input = document.getElementById(inputId);
  const table = document.getElementById(tableId);
  if (!input || !table) return;
  input.addEventListener('input', () => {
    const q = input.value.toLowerCase();
    table.querySelectorAll('tbody tr').forEach(row => {
      const text = row.textContent.toLowerCase();
      row.style.display = text.includes(q) ? '' : 'none';
    });
  });
}

// ─── Charts ───────────────────────────────────────────────────────
const KB_COLORS = {
  primary: '#A94F3B',    // Terracotta
  forest: '#467B75',     // Muted Teal
  sage: '#DCE9E4',       // Soft Sage Green
  charcoal: '#292D2B',   // Charcoal
  warning: '#D97706',
  success: '#059669',
  info: '#2563EB',
  danger: '#DC2626',
  muted: '#E5E1D8'       // Light Border
};

function createDoughnutChart(canvasId, labels, data, colors) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  return new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{ data, backgroundColor: colors, borderWidth: 2, borderColor: '#fff', hoverOffset: 6 }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      cutout: '68%',
      plugins: {
        legend: { position: 'bottom', labels: { font: { size: 11, family: 'Inter' }, padding: 12, usePointStyle: true } }
      }
    }
  });
}

function createBarChart(canvasId, labels, datasets) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  return new Chart(ctx, {
    type: 'bar',
    data: { labels, datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: 'top', labels: { font: { size: 11, family: 'Inter' }, usePointStyle: true } } },
      scales: {
        x: { grid: { display: false }, ticks: { font: { size: 11, family: 'Inter' } } },
        y: { grid: { color: '#F0EDE7' }, ticks: { font: { size: 11, family: 'Inter' } }, beginAtZero: true }
      }
    }
  });
}

function createLineChart(canvasId, labels, data, label) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  return new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label,
        data,
        borderColor: KB_COLORS.primary,
        backgroundColor: 'rgba(169,79,59,.08)',
        tension: 0.4,
        fill: true,
        pointBackgroundColor: KB_COLORS.primary,
        pointRadius: 4
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false }, ticks: { font: { size: 11, family: 'Inter' } } },
        y: { grid: { color: '#F0EDE7' }, ticks: { font: { size: 11, family: 'Inter' } }, beginAtZero: true }
      }
    }
  });
}

// ─── Notifications ────────────────────────────────────────────────
async function markNotificationsRead() {
  const fd = new FormData();
  fd.append('csrf_token', getCSRF());
  await fetch('/notifications/mark-read', { method: 'POST', headers: { 'X-CSRFToken': getCSRF() }, body: fd });
  document.querySelectorAll('.notif-badge').forEach(b => b.remove());
}

// ─── Auto-dismiss Flash Messages ─────────────────────────────────
function autoFlash(category, message) {
  ToastManager.show(message, category === 'error' ? 'danger' : category);
}

// ─── Init on DOM Ready ────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  ToastManager.init();

  // Mobile sidebar close on outside click
  document.addEventListener('click', e => {
    const sidebar = document.getElementById('sidebar');
    const toggleBtn = document.getElementById('sidebar-toggle');
    if (sidebar && sidebar.classList.contains('open')) {
      if (!sidebar.contains(e.target) && (!toggleBtn || !toggleBtn.contains(e.target))) {
        sidebar.classList.remove('open');
      }
    }
  });

  // Upload zones
  initUploadZone('upload-zone', 'file-input');
  initSearch('table-search', 'main-table');

  // Animate stat cards
  document.querySelectorAll('.stat-info .stat-value').forEach(el => {
    const target = parseInt(el.textContent) || 0;
    if (target === 0) return;
    let current = 0;
    const increment = Math.ceil(target / 30);
    const timer = setInterval(() => {
      current = Math.min(current + increment, target);
      el.textContent = current;
      if (current >= target) clearInterval(timer);
    }, 40);
  });
});
