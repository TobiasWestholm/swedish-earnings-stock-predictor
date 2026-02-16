// Svea Surveillance - Dashboard JavaScript

// Auto-refresh functionality (for Phase 3+ when live monitoring is active)
let autoRefreshInterval = null;

// Initialize dashboard on page load
document.addEventListener('DOMContentLoaded', function() {
    console.log('Svea Surveillance Dashboard Loaded');

    // Check if we're on a page that needs auto-refresh
    const currentPage = window.location.pathname;

    if (currentPage === '/signals' || currentPage === '/') {
        // Auto-refresh every 5 seconds (will be useful in Phase 3+)
        // Disabled for Phase 1 since there's no live data yet
        // startAutoRefresh(5000);
    }

    // Add active class to current nav link
    highlightCurrentNav();
});

/**
 * Start auto-refresh of page data
 * @param {number} interval - Refresh interval in milliseconds
 */
function startAutoRefresh(interval) {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
    }

    autoRefreshInterval = setInterval(() => {
        refreshPageData();
    }, interval);

    console.log(`Auto-refresh started (${interval}ms)`);
}

/**
 * Stop auto-refresh
 */
function stopAutoRefresh() {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
        autoRefreshInterval = null;
        console.log('Auto-refresh stopped');
    }
}

/**
 * Refresh page data via API without full page reload
 */
function refreshPageData() {
    const currentPage = window.location.pathname;

    if (currentPage === '/signals') {
        fetchSignals();
    } else if (currentPage === '/') {
        fetchDashboardStats();
    }
}

/**
 * Fetch latest signals from API
 */
function fetchSignals() {
    fetch('/api/signals')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Update signals display (Phase 4 feature)
                console.log(`Fetched ${data.count} signals`);
                // TODO: Update DOM with new signals
            }
        })
        .catch(error => {
            console.error('Error fetching signals:', error);
        });
}

/**
 * Fetch dashboard stats from API
 */
function fetchDashboardStats() {
    fetch('/api/watchlist')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log(`Watchlist: ${data.count} stocks`);
                // TODO: Update DOM with stats
            }
        })
        .catch(error => {
            console.error('Error fetching dashboard stats:', error);
        });
}

/**
 * Highlight current navigation link
 */
function highlightCurrentNav() {
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('.nav-link');

    navLinks.forEach(link => {
        const href = link.getAttribute('href');
        if (href === currentPath || (href === '/' && currentPath === '/')) {
            link.style.color = 'var(--primary-color)';
            link.style.fontWeight = '700';
        }
    });
}

/**
 * Format number as percentage
 * @param {number} value - Decimal value
 * @returns {string} Formatted percentage
 */
function formatPercent(value) {
    if (value === null || value === undefined) return 'N/A';
    const sign = value >= 0 ? '+' : '';
    return `${sign}${(value * 100).toFixed(1)}%`;
}

/**
 * Format number as currency (SEK)
 * @param {number} value - Number value
 * @returns {string} Formatted currency
 */
function formatCurrency(value) {
    if (value === null || value === undefined) return 'N/A';
    return `${value.toFixed(2)} SEK`;
}

/**
 * Format timestamp
 * @param {string} timestamp - ISO timestamp
 * @returns {string} Formatted time
 */
function formatTime(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('sv-SE', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
}

/**
 * Show notification (simple alert for Phase 1, can be enhanced later)
 * @param {string} message - Message to display
 * @param {string} type - Notification type (success, error, info)
 */
function showNotification(message, type = 'info') {
    // Simple implementation for Phase 1
    // In Phase 3+, this could be replaced with a nicer toast notification
    if (type === 'error') {
        alert(`Error: ${message}`);
    } else if (type === 'success') {
        alert(`Success: ${message}`);
    } else {
        alert(message);
    }
}

/**
 * Copy text to clipboard
 * @param {string} text - Text to copy
 */
function copyToClipboard(text) {
    if (navigator.clipboard) {
        navigator.clipboard.writeText(text)
            .then(() => {
                showNotification(`Copied: ${text}`, 'success');
            })
            .catch(err => {
                console.error('Failed to copy:', err);
            });
    } else {
        // Fallback for older browsers
        const textarea = document.createElement('textarea');
        textarea.value = text;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
        showNotification(`Copied: ${text}`, 'success');
    }
}

// Export functions for use in HTML onclick handlers
window.startAutoRefresh = startAutoRefresh;
window.stopAutoRefresh = stopAutoRefresh;
window.copyToClipboard = copyToClipboard;
window.showNotification = showNotification;
