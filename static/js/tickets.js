// static/js/tickets.js - Ticket Management Functions (shared)
(function(){
    // Escape HTML to prevent XSS
    function escapeHtml(str) {
        if (!str) return '';
        return String(str).replace(/[&<>]/g, function(m) {
            if (m === '&') return '&amp;';
            if (m === '<') return '&lt;';
            if (m === '>') return '&gt;';
            return m;
        });
    }

    // Submit a new ticket
    window.submitTicket = function() {
        const subjectEl = document.getElementById('ticketSubject');
        const messageEl = document.getElementById('ticketMessage');
        const priorityEl = document.getElementById('ticketPriority');
        const categoryEl = document.getElementById('ticketCategory');

        if (!subjectEl || !messageEl || !priorityEl || !categoryEl) return;

        const subject = subjectEl.value.trim();
        const message = messageEl.value.trim();
        const priority = priorityEl.value;
        const category = categoryEl.value;

        if (!subject || !message || !category) {
            if (window.showToast) showToast('Please fill in all fields.', 'error');
            return;
        }

        const submitBtn = document.querySelector('#ticketForm .btn-primary-custom');
        const originalHtml = submitBtn ? submitBtn.innerHTML : null;
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Submitting...';
        }

        fetch('/submit_ticket', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ subject, message, priority, category })
        })
        .then(r => r.json())
        .then(d => {
            if (d.success) {
                if (window.showToast) showToast('Ticket submitted successfully!', 'success');
                subjectEl.value = '';
                messageEl.value = '';
                categoryEl.value = '';
                if (window.loadTickets) window.loadTickets();
            } else {
                if (window.showToast) showToast(d.message || 'Failed to submit ticket.', 'error');
            }
        })
        .catch(() => { if (window.showToast) showToast('Failed to submit ticket.', 'error'); })
        .finally(() => {
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalHtml;
            }
        });
    };

    // Load student's tickets (used on student settings)
    window.loadTickets = function() {
        fetch('/get_tickets')
            .then(r => r.json())
            .then(d => {
                const list = document.getElementById('ticketList');
                const count = document.getElementById('ticketCount');
                if (!list || !count) return;

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
                                        <span class="ticket-priority">${escapeHtml((t.category || 'other').replace('_', ' '))}</span>
                                        <span class="ticket-priority ${priorityClass}">${t.priority || 'medium'}</span>
                                    </div>
                                </div>
                                <div style="font-size:0.75rem;color:var(--stone);margin-top:4px;">
                                    ${escapeHtml(t.message.substring(0, 120))}${t.message.length > 120 ? '...' : ''}
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
                const list = document.getElementById('ticketList');
                if (list) list.innerHTML = `
                    <p style="font-size:0.8rem;padding:0.8rem 0;text-align:center;color:#c2412c;margin:0;">
                        <i class="fas fa-exclamation-circle me-2"></i>Failed to load tickets.
                    </p>
                `;
            });
    };

    // Apply quick templates to ticket form
    window.applyTemplate = function() {
        const template = document.getElementById('ticketTemplate');
        if (!template) return;
        const val = template.value;
        const templates = {
            'activity': {
                subject: 'Activity not showing output',
                message: "Hi teacher, I'm having trouble with the activity. I followed the instructions but when I click RUN CODE, nothing shows up. Can you help me fix this?"
            },
            'login': {
                subject: 'Cannot login to my account',
                message: "Good day! I can't seem to log in to my account. I'm entering my LRN and password correctly but it says \"Invalid LRN or password\". Please help me access my account."
            },
            'bug': {
                subject: 'Blockly blocks not connecting properly',
                message: "Hi Ma'am/Sir, the blocks are not connecting properly. Every time I try to drag them, they don't snap into place. Please check if this is a bug."
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

        if (templates[val]) {
            const s = document.getElementById('ticketSubject');
            const m = document.getElementById('ticketMessage');
            if (s) s.value = templates[val].subject;
            if (m) m.value = templates[val].message;
        } else {
            const s = document.getElementById('ticketSubject');
            const m = document.getElementById('ticketMessage');
            if (s) s.value = '';
            if (m) m.value = '';
        }
    };

    // Expose a minimal helper to refresh ticket stats for teacher page
    window.loadTicketStats = function() {
        return fetch('/get_ticket_count')
            .then(r => r.json())
            .catch(() => ({}));
    };

    // Keep existing student-page call sites working
    window.loadStudentTickets = window.loadTickets;

    // Auto-run loadTickets for pages that include ticket form
    document.addEventListener('DOMContentLoaded', function(){
        if (document.getElementById('ticketForm')) {
            if (window.loadTickets) window.loadTickets();
        }
    });
})();
