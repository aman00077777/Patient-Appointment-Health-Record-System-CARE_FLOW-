// Patient Appointment & Health Record System - Frontend JS Utilities

document.addEventListener('DOMContentLoaded', () => {
    // 1. Auto-dismiss Bootstrap flash alerts after 4 seconds
    const alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach((alert) => {
        setTimeout(() => {
            // Check if Bootstrap class exists and dismiss gracefully
            if (typeof bootstrap !== 'undefined') {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            } else {
                alert.style.transition = 'opacity 0.5s ease';
                alert.style.opacity = '0';
                setTimeout(() => alert.remove(), 500);
            }
        }, 4000);
    });

    // 2. Cancellation Confirmation Dialog
    const cancelButtons = document.querySelectorAll('.btn-confirm-cancel');
    cancelButtons.forEach((button) => {
        button.addEventListener('click', (e) => {
            const confirmCancel = confirm("Are you sure you want to cancel this scheduled appointment?");
            if (!confirmCancel) {
                e.preventDefault();
            }
        });
    });

    // 3. Dynamic search in list (simple client-side filter helper)
    const searchInput = document.getElementById('search-doctors');
    if (searchInput) {
        searchInput.addEventListener('keyup', () => {
            const query = searchInput.value.toLowerCase();
            const rows = document.querySelectorAll('.doctor-row');
            
            rows.forEach((row) => {
                const text = row.textContent.toLowerCase();
                if (text.includes(query)) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
        });
    }
});
