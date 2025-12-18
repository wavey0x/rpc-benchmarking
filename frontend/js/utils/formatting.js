/**
 * Formatting utilities
 */

export function formatMs(ms) {
    if (ms === null || ms === undefined) return '-';
    if (ms < 1) return '<1ms';
    if (ms < 1000) return `${ms.toFixed(1)}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
}

export function formatPercent(value) {
    if (value === null || value === undefined) return '-';
    return `${(value * 100).toFixed(1)}%`;
}

export function formatNumber(num) {
    if (num === null || num === undefined) return '-';
    return num.toLocaleString();
}

export function formatDate(dateStr) {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleString();
}

export function formatDuration(seconds) {
    if (seconds === null || seconds === undefined) return '-';
    if (seconds < 60) return `${seconds.toFixed(0)}s`;
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}m ${secs}s`;
}

export function truncateAddress(address, chars = 6) {
    if (!address) return '-';
    if (address.length <= chars * 2 + 2) return address;
    return `${address.slice(0, chars + 2)}...${address.slice(-chars)}`;
}

export function getCategoryColor(category) {
    const colors = {
        simple: '#00ba7c',
        medium: '#1d9bf0',
        complex: '#ffad1f',
        load: '#f4212e',
    };
    return colors[category] || '#8b98a5';
}

export function getLabelColor(label) {
    const colors = {
        latest: '#00ba7c',
        archival: '#ffad1f',
    };
    return colors[label] || '#8b98a5';
}

export function getStatusColor(status) {
    const colors = {
        completed: '#00ba7c',
        running: '#1d9bf0',
        failed: '#f4212e',
        cancelled: '#8b98a5',
        pending: '#8b98a5',
    };
    return colors[status] || '#8b98a5';
}
