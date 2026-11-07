// static/js/tickets.js - Ticket Management Functions

// ============================================================
// TOAST NOTIFICATION (para sa student at teacher)
// ============================================================

function showToast(message, type = 'success') {
    // Remove existing toast
    const existing = document.querySelector('.alert-toast');
    if (existing) existing.remove();
    
    // Create toast element
    const toast = document.createElement('div');
    toast.className = `alert-toast ${type === 'error' ? 'error' : ''}`;
    toast.innerHTML = `
        <i class="fas ${type === 'error' ? 'fa-exclamation-circle' : 'fa-check-circle'}" 
           style="color: ${type === 'error' ? '#c2412c' : '#1c7e54'};"></i>
        <span>${message}</span>
    `;
    
    document.body.appendChild(toast);
    
    // Auto-remove after 3 seconds
    setTimeout(() => {
        if (toast.parentNode) toast.remove();
    }, 3000);
}

// ============================================================
// STUDENT TICKET FUNCTIONS
// ============================================================

// Submit a new ticket (Student)
function submitTicket() {
    const subject = document.getElementById('ticketSubject').value.trim();
    const message = document.getElementById('ticketMessage').value.trim();
    const priority = document.getElementById('ticketPriority').value;

    if (!subject || !message) {
        showToast('Please fill in all fields.', 'error');
        return;
    }

    const submitBtn = document.querySelector('#ticketForm .btn-primary-custom');
    const originalHtml = submitBtn.innerHTML;
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Submitting...';

    fetch('/submit_ticket', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ subject, message, priority })
    })
    .then(r => r.json())
    .then(d => {
        if (d.success) {
            showToast(' Ticket submitted successfully!', 'success');
            document.getElementById('ticketSubject').value = '';
            document.getElementById('ticketMessage').value = '';
            loadStudentTickets();
        } else {
            showToast(d.message || 'Failed to submit ticket.', 'error');
        }
    })
    .catch(() => showToast('Failed to submit ticket. Please try again.', 'error'))
    .finally(() => {
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalHtml;
    });
}

// Load student's tickets (Student view)
function loadStudentTickets() {
    fetch('/get_tickets')
        .then(r => r.json())
        .then(d => {
            const list = document.getElementById('ticketList');
            const count = document.getElementById('ticketCount');
            
            if (d.success && d.tickets && d.tickets.length > 0) {
                count.textContent = d.tickets.length;
                list.innerHTML = d.tickets.map(t => {
                    const statusClass = t.status || 'pending';
                    const priorityClass = t.priority || 'medium';
                    const statusLabel = statusClass.replace('_', ' ').toUpperCase();
                    
                    return `
                        <div style="padding:0.6rem 0;border-bottom:1px solid #eff5f1;">
                            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px;">
                                <span style="font-weight:600;font-size:0.85rem;color:#1a463a;">${escapeHtml(t.subject)}</span>
                                <div style="display:flex;gap:4px;flex-wrap:wrap;">
                                    <span class="ticket-status ${statusClass}">${statusLabel}</span>
                                    <span class="ticket-priority ${priorityClass}">${t.priority || 'medium'}</span>
                                </div>
                            </div>
                            <div style="font-size:0.75rem;color:var(--stone);margin-top:4px;">
                                ${escapeHtml(t.message.substring(0, 120))}${t.message.length > 120 ? '...' : ''}
                            </div>
                            <div style="font-size:0.6rem;color:var(--stone);margin-top:3px;">
                                <i class="far fa-clock me-1"></i>${t.created_at || ''}
                            </div>
                        </div>
                    `;
                }).join('');
            } else {
                count.textContent = '0';
                list.innerHTML = `
                    <p style="font-size:0.8rem;padding:0.8rem 0;text-align:center;color:var(--stone);margin:0;">
                        <i class="fas fa-inbox me-2"></i>No tickets submitted yet.
                    </p>
                `;
            }
        })
        .catch(err => {
            console.error('Error loading tickets:', err);
            document.getElementById('ticketList').innerHTML = `
                <p style="font-size:0.8rem;padding:0.8rem 0;text-align:center;color:#c2412c;margin:0;">
                    <i class="fas fa-exclamation-circle me-2"></i>Failed to load tickets.
                </p>
            `;
        });
}

// ============================================================
// TEACHER TICKET FUNCTIONS
// ============================================================

// Load all tickets (Teacher view)
function loadTeacherTickets(filter = 'all') {
    const url = filter !== 'all' ? `/get_tickets?status=${filter}` : '/get_tickets';
    
    fetch(url)
        .then(r => r.json())
        .then(d => {
            const list = document.getElementById('ticketList');
            
            if (d.success && d.tickets && d.tickets.length > 0) {
                list.innerHTML = d.tickets.map(t => {
                    const statusClass = t.status || 'pending';
                    const priorityClass = t.priority || 'medium';
                    const statusLabel = statusClass.replace('_', ' ').toUpperCase();
                    const highPriority = t.priority === 'high' ? 'high-priority' : '';
                    
                    return `
                        <div class="ticket-card ${highPriority}" onclick="viewTicketDetail(${t.id})">
                            <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:8px;">
                                <div>
                                    <div style="font-weight:600; font-size:0.95rem; color:#1a463a;">
                                        ${escapeHtml(t.subject)}
                                    </div>
                                    <div style="font-size:0.8rem; color:var(--stone); margin-top:4px;">
                                        <i class="fas fa-user me-1"></i>${escapeHtml(t.student_username || t.student_name || 'Student')}
                                    </div>
                                    <div style="font-size:0.75rem; color:var(--stone); margin-top:2px;">
                                        ${escapeHtml(t.message.substring(0, 100))}${t.message.length > 100 ? '...' : ''}
                                    </div>
                                </div>
                                <div style="display:flex; gap:6px; flex-wrap:wrap; flex-shrink:0;">
                                    <span class="ticket-status ${statusClass}">${statusLabel}</span>
                                    <span class="ticket-priority ${priorityClass}">${t.priority || 'medium'}</span>
                                </div>
                            </div>
                        </div>
                    `;
                }).join('');
            } else {
                list.innerHTML = `
                    <p style="font-size:0.85rem; color:var(--stone); text-align:center; padding:2rem 0;">
                        <i class="fas fa-inbox me-2"></i>No tickets found.
                    </p>
                `;
            }
        })
        .catch(err => {
            console.error('Error loading tickets:', err);
            document.getElementById('ticketList').innerHTML = `
                <p style="font-size:0.85rem; color:#c2412c; text-align:center; padding:2rem 0;">
                    <i class="fas fa-exclamation-circle me-2"></i>Failed to load tickets.
                </p>
            `;
        });
}

// View ticket detail (Teacher)
function viewTicketDetail(ticketId) {
    // Find ticket from allTickets (global variable)
    const ticket = window.allTickets ? window.allTickets.find(t => t.id === ticketId) : null;
    if (!ticket) {
        // If not found, fetch it
        fetch(`/get_tickets`)
            .then(r => r.json())
            .then(d => {
                if (d.success) {
                    window.allTickets = d.tickets || [];
                    const found = window.allTickets.find(t => t.id === ticketId);
                    if (found) renderTicketModal(found);
                }
            });
        return;
    }
    renderTicketModal(ticket);
}

function renderTicketModal(ticket) {
    const statusClass = ticket.status || 'pending';
    const priorityClass = ticket.priority || 'medium';
    const statusLabel = statusClass.replace('_', ' ').toUpperCase();

    const content = document.getElementById('ticketDetailContent');
    content.innerHTML = `
        <div style="margin-bottom:1.2rem;">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
                <h5 style="font-weight:700; color:#1a463a; margin:0;">${escapeHtml(ticket.subject)}</h5>
                <div style="display:flex; gap:6px;">
                    <span class="ticket-status ${statusClass}">${statusLabel}</span>
                    <span class="ticket-priority ${priorityClass}">${ticket.priority || 'medium'}</span>
                </div>
            </div>
            <div style="font-size:0.8rem; color:var(--stone); margin-top:6px;">
                <i class="fas fa-user me-1"></i>${escapeHtml(ticket.student_username || ticket.student_name || 'Student')}
            </div>
        </div>

        <div style="background:var(--green-soft); border-radius:12px; padding:1rem; margin-bottom:1.2rem;">
            <div style="font-weight:600; font-size:0.85rem; color:#1a463a; margin-bottom:4px;">Message:</div>
            <div style="font-size:0.9rem; color:#1a463a; white-space:pre-wrap;">${escapeHtml(ticket.message)}</div>
        </div>

        <hr style="border-color:var(--border-fresh);">

        <form id="ticketResponseForm">
            <div class="mb-3">
                <label style="font-weight:600; font-size:0.8rem; color:#425145; display:block; margin-bottom:4px;">Update Status</label>
                <select class="form-control-custom" id="ticketStatusSelect">
                    <option value="pending" ${ticket.status === 'pending' ? 'selected' : ''}>Pending</option>
                    <option value="in_progress" ${ticket.status === 'in_progress' ? 'selected' : ''}>In Progress</option>
                    <option value="resolved" ${ticket.status === 'resolved' ? 'selected' : ''}>Resolved</option>
                    <option value="closed" ${ticket.status === 'closed' ? 'selected' : ''}>Closed</option>
                </select>
            </div>
            <div style="display:flex; gap:10px; flex-wrap:wrap;">
                <button type="button" class="btn-primary-custom" onclick="updateTicketStatus(${ticket.id})">
                    <i class="fas fa-save me-2"></i>Update Ticket
                </button>
                <button type="button" class="btn-outline-custom" data-bs-dismiss="modal">
                    Close
                </button>
            </div>
        </form>
    `;

    const modal = new bootstrap.Modal(document.getElementById('ticketModal'));
    modal.show();
}

// Update ticket status (Teacher)
function updateTicketStatus(ticketId) {
    const status = document.getElementById('ticketStatusSelect').value;

    fetch('/update_ticket', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticket_id: ticketId, status })
    })
    .then(r => r.json())
    .then(d => {
        if (d.success) {
            showToast(' Ticket updated successfully!', 'success');
            const modal = bootstrap.Modal.getInstance(document.getElementById('ticketModal'));
            if (modal) modal.hide();
            loadTeacherTickets(currentFilter || 'all');
            loadTicketStats();
        } else {
            showToast('Error: ' + (d.message || 'Failed to update'), 'error');
        }
    })
    .catch(() => showToast('Error updating ticket.', 'error'));
}

// Load ticket statistics (Teacher)
function loadTicketStats() {
    fetch('/get_ticket_count')
        .then(r => r.json())
        .then(d => {
            if (d.success) {
                document.getElementById('statPending').textContent = d.pending || 0;
                document.getElementById('statInProgress').textContent = d.in_progress || 0;
                document.getElementById('statResolved').textContent = d.resolved || 0;
                document.getElementById('statTotal').textContent = d.total || 0;
            }
        })
        .catch(err => console.error('Error loading stats:', err));
}

// Filter tickets (Teacher)
function filterTickets(filter) {
    currentFilter = filter;
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.filter === filter);
    });
    loadTeacherTickets(filter);
}

// ============================================================
// TEMPLATE FUNCTIONS (Student)
// ============================================================

// Apply template to ticket form
function applyTemplate() {
    const template = document.getElementById('ticketTemplate').value;
    const templates = {
        'activity': {
            subject: 'Activity not showing output',
            message: 'Hi teacher, I\'m having trouble with the activity. I followed the instructions but when I click RUN CODE, nothing shows up. Can you help me fix this?'
        },
        'login': {
            subject: 'Cannot login to my account',
            message: 'Good day! I can\'t seem to log in to my account. I\'m entering my LRN and password correctly but it says "Invalid LRN or password". Please help me access my account.'
        },
        'bug': {
            subject: 'Blockly blocks not connecting properly',
            message: 'Hi Ma\'am/Sir, the blocks are not connecting properly. Every time I try to drag them, they don\'t snap into place. Please check if this is a bug.'
        },
        'score': {
            subject: 'My activity score is not saving',
            message: 'Good day! I completed the activity but my score is not being recorded. I already clicked SAVE PRACTICE but it shows 0%. Can you please check my account?'
        },
        'question': {
            subject: 'Question about activities',
            message: 'Hi Teacher! I have a question about the activities. Can you please guide me on how to proceed? Thank you!'
        }
    };
    
    if (templates[template]) {
        document.getElementById('ticketSubject').value = templates[template].subject;
        document.getElementById('ticketMessage').value = templates[template].message;
    } else {
        document.getElementById('ticketSubject').value = '';
        document.getElementById('ticketMessage').value = '';
    }
}

// ============================================================
// UTILITY FUNCTIONS
// ============================================================

// Escape HTML to prevent XSS attacks
function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/[&<>]/g, function(m) {
        if (m === '&') return '&amp;';
        if (m === '<') return '&lt;';
        if (m === '>') return '&gt;';
        return m;
    });
}

// ============================================================
// GLOBAL VARIABLES
// ============================================================

let currentFilter = 'all';
let allTickets = [];

// ============================================================
// INITIALIZATION - DETECT WHICH PAGE WE'RE ON
// ============================================================

document.addEventListener('DOMContentLoaded', function() {
    // Check if we're on student settings page
    if (document.getElementById('ticketList') && document.getElementById('ticketCount')) {
        // Student page - load student tickets
        setTimeout(loadStudentTickets, 500);
    }
    
    // Check if we're on teacher tickets page
    if (document.getElementById('statPending')) {
        // Teacher page - load all tickets and stats
        loadTicketStats();
        loadTeacherTickets('all');
        setInterval(loadTicketStats, 30000);
    }
});