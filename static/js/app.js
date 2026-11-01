// ============================================
// KnowBridge AI - Main JavaScript
// Shared utility functions and API helper
// ============================================

// ============================================
// API Helper
// ============================================
const API = {
    async request(url, options = {}) {
        try {
            const defaultOptions = {
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin'
            };
            // Don't set Content-Type for FormData (browser sets it with boundary)
            if (options.body instanceof FormData) {
                delete defaultOptions.headers['Content-Type'];
            }
            const response = await fetch(url, { ...defaultOptions, ...options });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || data.message || `HTTP ${response.status}`);
            }
            return data;
        } catch (error) {
            console.error('API Error:', error);
            throw error;
        }
    },

    get(url) {
        return this.request(url);
    },

    post(url, body) {
        if (body instanceof FormData) {
            return this.request(url, { method: 'POST', body });
        }
        return this.request(url, { method: 'POST', body: JSON.stringify(body) });
    },

    put(url, body) {
        return this.request(url, { method: 'PUT', body: JSON.stringify(body) });
    },

    delete(url) {
        return this.request(url, { method: 'DELETE' });
    }
};

// ============================================
// Toast Notifications
// ============================================
function showToast(message, type = 'success') {
    // Create toast container if not exists
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    const icons = {
        success: 'fa-check-circle',
        error: 'fa-exclamation-circle',
        warning: 'fa-exclamation-triangle',
        info: 'fa-info-circle'
    };

    const colors = {
        success: '#43BFA5',
        error: '#E74C6F',
        warning: '#F5A623',
        info: '#4F7DF3'
    };

    const toast = document.createElement('div');
    toast.className = 'custom-toast slide-up';
    toast.style.borderLeftColor = colors[type] || colors.info;
    toast.innerHTML = `
        <div class="d-flex align-items-center">
            <i class="fas ${icons[type] || icons.info} me-3" style="color: ${colors[type] || colors.info}; font-size: 20px;"></i>
            <span>${message}</span>
            <button class="btn-close ms-auto" onclick="this.parentElement.parentElement.remove()"></button>
        </div>
    `;
    container.appendChild(toast);

    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (toast.parentElement) {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(100%)';
            toast.style.transition = 'all 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }
    }, 5000);
}

// ============================================
// Date & Time Formatting
// ============================================
function formatDate(dateStr) {
    if (!dateStr) return 'N/A';
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return 'N/A';
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

function formatDateTime(dateStr) {
    if (!dateStr) return 'N/A';
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return 'N/A';
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function timeAgo(dateStr) {
    if (!dateStr) return 'N/A';
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return 'N/A';
    const now = new Date();
    const seconds = Math.floor((now - date) / 1000);

    if (seconds < 60) return 'Just now';
    if (seconds < 3600) return Math.floor(seconds / 60) + 'm ago';
    if (seconds < 86400) return Math.floor(seconds / 3600) + 'h ago';
    if (seconds < 604800) return Math.floor(seconds / 86400) + 'd ago';
    return formatDate(dateStr);
}

// ============================================
// File Size Formatting
// ============================================
function formatFileSize(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return (bytes / Math.pow(1024, i)).toFixed(1) + ' ' + sizes[i];
}

// ============================================
// Text Utilities
// ============================================
function truncateText(text, maxLength = 100) {
    if (!text) return '';
    return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function capitalizeFirst(str) {
    if (!str) return '';
    return str.charAt(0).toUpperCase() + str.slice(1).replace(/_/g, ' ');
}

// ============================================
// Status / Badge Class Helpers
// ============================================
function getStatusBadgeClass(status) {
    const classes = {
        'unverified': 'badge-unverified',
        'approved': 'badge-approved',
        'rejected': 'badge-rejected',
        'needs_review': 'badge-needs-review',
        'pending': 'badge-needs-review',
        'completed': 'badge-approved',
        'processing': 'badge-needs-review',
        'failed': 'badge-rejected',
        'active': 'badge-approved',
        'archived': 'badge-unverified',
        'not_started': 'badge-unverified',
        'in_progress': 'badge-needs-review',
        'blocked': 'badge-rejected',
        'draft': 'badge-unverified',
        'final': 'badge-approved',
        'acknowledged': 'badge-approved'
    };
    return classes[status] || 'badge-unverified';
}

function getConfidenceBadgeClass(confidence) {
    const classes = {
        'high': 'badge-approved',
        'medium': 'badge-needs-review',
        'low': 'badge-rejected'
    };
    return classes[confidence] || 'badge-unverified';
}

function getSeverityBadgeClass(severity) {
    const classes = {
        'critical': 'badge-critical',
        'high': 'badge-rejected',
        'medium': 'badge-needs-review',
        'low': 'badge-approved'
    };
    return classes[severity] || 'badge-unverified';
}

function getPriorityColor(priority) {
    const colors = {
        'high': '#E74C6F',
        'medium': '#F5A623',
        'low': '#43BFA5'
    };
    return colors[priority] || '#6B7A99';
}

function getFileIcon(type) {
    const icons = {
        'pdf': 'fa-file-pdf text-danger',
        'docx': 'fa-file-word text-primary',
        'doc': 'fa-file-word text-primary',
        'txt': 'fa-file-lines text-muted',
        'csv': 'fa-file-csv text-success',
        'xlsx': 'fa-file-excel text-success',
        'xls': 'fa-file-excel text-success'
    };
    return icons[type] || 'fa-file';
}

// ============================================
// Avatar Helper
// ============================================
function createAvatarCircle(name) {
    const initials = name
        ? name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase()
        : '?';
    const colors = ['#4F7DF3', '#43BFA5', '#F5A623', '#E74C6F', '#9B59B6', '#1ABC9C'];
    const colorIndex = name ? name.charCodeAt(0) % colors.length : 0;
    const bg = colors[colorIndex];
    return `<div class="avatar-circle" style="background: ${bg}20; color: ${bg}">${initials}</div>`;
}

// ============================================
// Loading & Empty States
// ============================================
function showLoading(container) {
    if (typeof container === 'string') container = document.getElementById(container);
    if (container) {
        container.innerHTML = `
            <div class="text-center py-5">
                <div class="loading-spinner mb-3"></div>
                <p class="text-muted">Loading...</p>
            </div>
        `;
    }
}

function showEmptyState(container, message = 'No data found', icon = 'fa-inbox') {
    if (typeof container === 'string') container = document.getElementById(container);
    if (container) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="fas ${icon}"></i>
                <h5>${message}</h5>
                <p class="text-muted">Get started by adding new items</p>
            </div>
        `;
    }
}

function showError(container, message = 'An error occurred') {
    if (typeof container === 'string') container = document.getElementById(container);
    if (container) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-exclamation-triangle" style="color: #E74C6F;"></i>
                <h5>${message}</h5>
                <p class="text-muted">Please try again or contact support</p>
            </div>
        `;
    }
}

// ============================================
// Sidebar Toggle (Mobile)
// ============================================
document.addEventListener('DOMContentLoaded', function () {
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');

    if (sidebarToggle && sidebar) {
        sidebarToggle.addEventListener('click', function () {
            sidebar.classList.toggle('show');
            if (overlay) overlay.classList.toggle('show');
        });
    }

    if (overlay) {
        overlay.addEventListener('click', function () {
            if (sidebar) sidebar.classList.remove('show');
            overlay.classList.remove('show');
        });
    }

    // Close sidebar on escape key
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && sidebar && sidebar.classList.contains('show')) {
            sidebar.classList.remove('show');
            if (overlay) overlay.classList.remove('show');
        }
    });

    // Check AI Status on page load
    checkAIStatus();

    // Initialize tooltips if Bootstrap is available
    if (typeof bootstrap !== 'undefined') {
        const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
        tooltipTriggerList.forEach(function (tooltipTriggerEl) {
            new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }
});

// ============================================
// AI Status Check
// ============================================
async function checkAIStatus() {
    try {
        const data = await API.get('/api/ai/status');
        const statusDot = document.getElementById('aiStatusDot');
        const statusText = document.getElementById('aiStatusText');
        if (statusDot && statusText) {
            if (data.connected) {
                statusDot.className = 'status-dot bg-success pulse';
                statusText.textContent = 'AI: ' + (data.provider || 'Connected');
            } else {
                statusDot.className = 'status-dot bg-warning pulse';
                statusText.textContent = 'AI: Fallback Mode';
            }
        }
    } catch (e) {
        const statusDot = document.getElementById('aiStatusDot');
        const statusText = document.getElementById('aiStatusText');
        if (statusDot && statusText) {
            statusDot.className = 'status-dot bg-danger';
            statusText.textContent = 'AI: Offline';
        }
    }
}

// ============================================
// Chart Color Schemes
// ============================================
const chartColors = {
    primary: '#4F7DF3',
    accent: '#43BFA5',
    warning: '#F5A623',
    danger: '#E74C6F',
    purple: '#9B59B6',
    info: '#3498DB',

    taskStatus: {
        not_started: '#E7ECF3',
        in_progress: '#4F7DF3',
        completed: '#43BFA5',
        blocked: '#E74C6F'
    },

    riskSeverity: {
        critical: '#D63B65',
        high: '#E74C6F',
        medium: '#F5A623',
        low: '#43BFA5'
    },

    decisionStatus: {
        unverified: '#E7ECF3',
        approved: '#43BFA5',
        rejected: '#E74C6F',
        needs_review: '#F5A623'
    },

    palette: [
        '#4F7DF3', '#43BFA5', '#F5A623', '#E74C6F',
        '#9B59B6', '#3498DB', '#1ABC9C', '#E67E22',
        '#2ECC71', '#E74C3C', '#34495E', '#16A085'
    ]
};

// Global Chart.js defaults
if (typeof Chart !== 'undefined') {
    Chart.defaults.font.family = "'Inter', sans-serif";
    Chart.defaults.font.size = 12;
    Chart.defaults.color = '#6B7A99';
    Chart.defaults.plugins.legend.labels.usePointStyle = true;
    Chart.defaults.plugins.legend.labels.padding = 15;
    Chart.defaults.plugins.legend.labels.font = { size: 12, family: "'Inter', sans-serif" };
    Chart.defaults.plugins.tooltip.backgroundColor = '#24324A';
    Chart.defaults.plugins.tooltip.cornerRadius = 8;
    Chart.defaults.plugins.tooltip.padding = 10;
    Chart.defaults.plugins.tooltip.titleFont = { size: 13, family: "'Inter', sans-serif", weight: '600' };
    Chart.defaults.plugins.tooltip.bodyFont = { size: 12, family: "'Inter', sans-serif" };
    Chart.defaults.elements.arc.borderWidth = 0;
    Chart.defaults.scale.grid = { color: '#E7ECF3', drawBorder: false };
    Chart.defaults.scale.ticks = { padding: 8 };
}

// ============================================
// Confirm Dialog
// ============================================
function confirmAction(message) {
    return new Promise(function (resolve) {
        if (confirm(message)) {
            resolve(true);
        } else {
            resolve(false);
        }
    });
}

// ============================================
// Evidence Modal Helper
// ============================================
async function showEvidenceModal(itemType, itemId) {
    try {
        const data = await API.get('/api/evidence/' + itemType + '/' + itemId);
        const modal = document.getElementById('evidenceModal');
        const body = document.getElementById('evidenceModalBody');

        if (!modal || !body) {
            console.error('Evidence modal elements not found');
            return;
        }

        if (!data.evidence || data.evidence.length === 0) {
            body.innerHTML = `
                <div class="text-center py-4">
                    <i class="fas fa-search text-muted" style="font-size: 48px;"></i>
                    <p class="mt-3 text-muted">No evidence found for this item</p>
                </div>
            `;
        } else {
            body.innerHTML = data.evidence.map(function (e) {
                return `
                    <div class="card mb-3">
                        <div class="card-body">
                            <div class="d-flex align-items-center mb-2">
                                <i class="fas fa-file-lines text-primary me-2"></i>
                                <strong>${escapeHtml(e.document_name || 'Unknown Document')}</strong>
                                ${e.page_number ? '<span class="badge badge-unverified ms-2">Page ' + e.page_number + '</span>' : ''}
                                ${e.section ? '<span class="badge badge-unverified ms-2">' + escapeHtml(e.section) + '</span>' : ''}
                            </div>
                            <blockquote class="border-start border-primary border-3 ps-3 mb-0" style="background: #F8FAFC; padding: 12px; border-radius: 0 8px 8px 0;">
                                <p class="mb-0" style="font-style: italic; color: #6B7A99;">"${escapeHtml(e.excerpt)}"</p>
                            </blockquote>
                        </div>
                    </div>
                `;
            }).join('');
        }

        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();
    } catch (error) {
        showToast('Failed to load evidence: ' + error.message, 'error');
    }
}

// ============================================
// Review Helper
// ============================================
async function submitReview(itemType, itemId, action, comment) {
    comment = comment || '';
    try {
        const url = '/api/' + itemType + 's/' + itemId + '/review';
        await API.post(url, { action: action, comment: comment });
        showToast('Item ' + action + ' successfully', 'success');
        return true;
    } catch (error) {
        showToast('Review failed: ' + error.message, 'error');
        return false;
    }
}

// ============================================
// Drag and Drop Upload Helper
// ============================================
function initUploadZone(zoneSelector, fileInputSelector, options) {
    options = options || {};
    var maxFiles = options.maxFiles || 10;
    var maxSizeMB = options.maxSizeMB || 50;
    var allowedTypes = options.allowedTypes || ['pdf', 'docx', 'txt', 'csv'];
    var onFilesSelected = options.onFilesSelected || function () {};

    var zone = document.querySelector(zoneSelector);
    var fileInput = document.querySelector(fileInputSelector);

    if (!zone || !fileInput) return;

    // Prevent default drag behaviors
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(function (eventName) {
        zone.addEventListener(eventName, function (e) {
            e.preventDefault();
            e.stopPropagation();
        });
    });

    // Highlight on drag
    ['dragenter', 'dragover'].forEach(function (eventName) {
        zone.addEventListener(eventName, function () {
            zone.classList.add('dragover');
        });
    });

    ['dragleave', 'drop'].forEach(function (eventName) {
        zone.addEventListener(eventName, function () {
            zone.classList.remove('dragover');
        });
    });

    // Handle dropped files
    zone.addEventListener('drop', function (e) {
        var files = e.dataTransfer.files;
        handleFiles(files);
    });

    // Handle file input change
    fileInput.addEventListener('change', function () {
        handleFiles(fileInput.files);
    });

    // Click zone to open file dialog
    zone.addEventListener('click', function () {
        fileInput.click();
    });

    function handleFiles(files) {
        var validFiles = [];
        Array.from(files).forEach(function (file) {
            var ext = file.name.split('.').pop().toLowerCase();
            if (!allowedTypes.includes(ext)) {
                showToast('File type .' + ext + ' is not supported', 'warning');
                return;
            }
            if (file.size > maxSizeMB * 1024 * 1024) {
                showToast(file.name + ' exceeds ' + maxSizeMB + 'MB limit', 'warning');
                return;
            }
            if (validFiles.length >= maxFiles) {
                showToast('Maximum ' + maxFiles + ' files allowed', 'warning');
                return;
            }
            validFiles.push(file);
        });
        if (validFiles.length > 0) {
            onFilesSelected(validFiles);
        }
    }
}

// ============================================
// Debounce Utility
// ============================================
function debounce(func, wait) {
    var timeout;
    return function () {
        var context = this;
        var args = arguments;
        clearTimeout(timeout);
        timeout = setTimeout(function () {
            func.apply(context, args);
        }, wait);
    };
}

// ============================================
// Copy to Clipboard
// ============================================
async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        showToast('Copied to clipboard', 'success');
    } catch (err) {
        // Fallback for older browsers
        var textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.select();
        try {
            document.execCommand('copy');
            showToast('Copied to clipboard', 'success');
        } catch (e) {
            showToast('Failed to copy', 'error');
        }
        document.body.removeChild(textarea);
    }
}

// ============================================
// Local Storage Helpers
// ============================================
const Storage = {
    get(key, defaultValue) {
        try {
            const value = localStorage.getItem('kb_' + key);
            return value ? JSON.parse(value) : defaultValue;
        } catch (e) {
            return defaultValue;
        }
    },

    set(key, value) {
        try {
            localStorage.setItem('kb_' + key, JSON.stringify(value));
        } catch (e) {
            console.error('Failed to save to localStorage:', e);
        }
    },

    remove(key) {
        try {
            localStorage.removeItem('kb_' + key);
        } catch (e) {
            console.error('Failed to remove from localStorage:', e);
        }
    }
};

// ============================================
// Number Formatting
// ============================================
function formatNumber(num) {
    if (num === null || num === undefined) return '0';
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toString();
}

function formatPercentage(value, decimals) {
    decimals = decimals !== undefined ? decimals : 1;
    if (value === null || value === undefined) return '0%';
    return parseFloat(value).toFixed(decimals) + '%';
}

// ============================================
// URL Query Parameter Helpers
// ============================================
function getQueryParam(name) {
    var params = new URLSearchParams(window.location.search);
    return params.get(name);
}

function setQueryParam(name, value) {
    var params = new URLSearchParams(window.location.search);
    if (value === null || value === undefined || value === '') {
        params.delete(name);
    } else {
        params.set(name, value);
    }
    var newUrl = window.location.pathname;
    var paramStr = params.toString();
    if (paramStr) newUrl += '?' + paramStr;
    window.history.replaceState({}, '', newUrl);
}

// ============================================
// Form Validation Helper
// ============================================
function validateForm(formEl) {
    if (typeof formEl === 'string') formEl = document.getElementById(formEl);
    if (!formEl) return false;

    formEl.classList.add('was-validated');
    return formEl.checkValidity();
}

function clearFormValidation(formEl) {
    if (typeof formEl === 'string') formEl = document.getElementById(formEl);
    if (!formEl) return;

    formEl.classList.remove('was-validated');
    formEl.querySelectorAll('.is-invalid').forEach(function (el) {
        el.classList.remove('is-invalid');
    });
}

// ============================================
// Keyboard Shortcuts
// ============================================
document.addEventListener('keydown', function (e) {
    // Ctrl+K or Cmd+K for search focus
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        var searchInput = document.querySelector('.search-input input, #searchInput');
        if (searchInput) searchInput.focus();
    }
});
