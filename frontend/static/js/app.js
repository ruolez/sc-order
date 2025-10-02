// Main application logic

const API_BASE_URL = '';

// Initialize app on page load
document.addEventListener('DOMContentLoaded', () => {
    showView('products');
    loadProducts();
    loadSettings();
});

// View management
function showView(viewName) {
    // Hide all views
    document.querySelectorAll('.view-container').forEach(view => {
        view.classList.add('hidden');
    });

    // Show selected view
    const viewElement = document.getElementById(`${viewName}-view`);
    if (viewElement) {
        viewElement.classList.remove('hidden');
    }

    // Update active state for top bar navigation buttons
    const navButtons = ['products', 'settings', 'import'];
    navButtons.forEach(view => {
        const btn = document.getElementById(`nav-${view}-btn`);
        if (btn) {
            if (view === viewName) {
                btn.classList.remove('btn-ghost');
                btn.classList.add('btn-primary');
            } else {
                btn.classList.remove('btn-primary');
                btn.classList.add('btn-ghost');
            }
        }
    });

    // Load data for specific views
    if (viewName === 'products') {
        loadProducts();
    } else if (viewName === 'settings') {
        loadSettings();
    }
}

// Toast notifications
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <div class="flex items-center">
            <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'} mr-2"></i>
            <span>${message}</span>
        </div>
    `;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'slideIn 0.3s ease-out reverse';
        setTimeout(() => {
            document.body.removeChild(toast);
        }, 300);
    }, 3000);
}

// API helper functions
async function apiRequest(endpoint, options = {}) {
    try {
        const response = await fetch(`${API_BASE_URL}${endpoint}`, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Request failed');
        }

        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

// Format currency
function formatCurrency(value) {
    if (value === null || value === undefined) return '-';
    return `$${parseFloat(value).toFixed(2)}`;
}

// Format number
function formatNumber(value) {
    if (value === null || value === undefined) return '-';
    return value.toString();
}
