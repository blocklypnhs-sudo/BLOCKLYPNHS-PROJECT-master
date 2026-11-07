// Custom JavaScript for Blockly Learning Platform

// Utility functions
function showAlert(message, type = 'info', duration = 5000) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
    alertDiv.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;

    document.body.appendChild(alertDiv);

    // Auto remove after duration
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.remove();
        }
    }, duration);
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function formatScore(score) {
    if (score >= 90) return `<span class="text-success">${score}%</span>`;
    if (score >= 70) return `<span class="text-warning">${score}%</span>`;
    return `<span class="text-danger">${score}%</span>`;
}

// Loading states
function showLoading(elementId, text = 'Loading...') {
    const element = document.getElementById(elementId);
    if (element) {
        element.innerHTML = `
            <div class="text-center py-4">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">${text}</span>
                </div>
                <div class="mt-2">${text}</div>
            </div>
        `;
    }
}

function hideLoading(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.innerHTML = '';
    }
}

// Form validation
function validateForm(formId) {
    const form = document.getElementById(formId);
    if (!form) return false;

    const inputs = form.querySelectorAll('input[required], select[required]');
    let isValid = true;

    inputs.forEach(input => {
        if (!input.value.trim()) {
            input.classList.add('is-invalid');
            isValid = false;
        } else {
            input.classList.remove('is-invalid');
        }
    });

    return isValid;
}

// AJAX helper
function makeRequest(url, options = {}) {
    const defaultOptions = {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
        },
    };

    const config = { ...defaultOptions, ...options };

    if (config.body && typeof config.body === 'object') {
        config.body = JSON.stringify(config.body);
    }

    return fetch(url, config)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .catch(error => {
            console.error('Request failed:', error);
            showAlert('Request failed. Please try again.', 'danger');
            throw error;
        });
}

// Export functionality (placeholder)
function exportToCSV(data, filename) {
    if (!data || !data.length) {
        showAlert('No data to export', 'warning');
        return;
    }

    const headers = Object.keys(data[0]);
    const csvContent = [
        headers.join(','),
        ...data.map(row => headers.map(header => `"${row[header] || ''}"`).join(','))
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    link.style.display = 'none';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    showAlert('Data exported successfully!', 'success');
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Add loading states to forms
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Processing...';
            }
        });
    });

    // Auto-hide alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });
});

// Console logging for debugging (only in development)
if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    console.log('Blockly Learning Platform - Development Mode');
    console.log('Available functions: showAlert, makeRequest, exportToCSV, validateForm');
}

// Load shared dashboard data on DOM ready to sync sidebar badges across pages
document.addEventListener('DOMContentLoaded', function() {
    try {
        if (typeof loadSharedDashboardData === 'function') {
            loadSharedDashboardData();
        }
    } catch (e) {
        console.warn('Error initializing shared dashboard data:', e);
    }
});

// Fetch dashboard data (role-aware) and update shared sidebar badges
async function loadSharedDashboardData() {
    try {
        const d = await makeRequest('/get_dashboard_data');
        if (!d || !d.success) return;

        // Ticket badge (handles teacher or student payloads)
        const ticketBadge = document.getElementById('ticketNavBadge');
        const pending = d.pending_tickets || d.pending || 0;
        if (ticketBadge) {
            if (pending > 0) {
                ticketBadge.style.display = 'block';
                ticketBadge.textContent = pending > 9 ? '9+' : pending;
            } else {
                ticketBadge.style.display = 'none';
                ticketBadge.textContent = '';
            }
        }

        // Merge into global dashboard_data if present (pages can read it)
        if (typeof dashboard_data !== 'undefined') {
            Object.assign(dashboard_data, d);
        }
    } catch (err) {
        console.warn('Failed to load shared dashboard data', err);
    }
}