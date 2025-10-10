// Reports Module
// Manages SC Sales report functionality

// State
let currentReportData = null;
let currentSortColumn = 'quantity_sold';
let currentSortDirection = 'desc';

/**
 * Format currency with comma thousands separator
 */
function formatCurrency(amount) {
  if (amount === null || amount === undefined || isNaN(amount)) {
    return '0.00';
  }

  const num = parseFloat(amount);
  return num.toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });
}

/**
 * Load SC Sales report
 */
async function loadSCScalesReport() {
  const fromDate = document.getElementById('report-from-date').value;
  const toDate = document.getElementById('report-to-date').value;

  if (!fromDate || !toDate) {
    showToast('Please select both start and end dates', 'error');
    return;
  }

  if (new Date(fromDate) > new Date(toDate)) {
    showToast('Start date must be before or equal to end date', 'error');
    return;
  }

  // Show loading state
  const loadButton = document.getElementById('load-report-btn');
  const exportButton = document.getElementById('export-report-btn');
  const reportResults = document.getElementById('report-results');
  const reportLoading = document.getElementById('report-loading');
  const reportContent = document.getElementById('report-content');

  loadButton.disabled = true;
  loadButton.innerHTML = '<i class="spinner"></i> Loading...';
  exportButton.style.display = 'none';
  reportResults.style.display = 'block';
  reportLoading.style.display = 'flex';
  reportContent.style.display = 'none';

  try {
    const response = await apiRequest(`/api/reports/sc-sales?from_date=${fromDate}&to_date=${toDate}`);

    if (response.error) {
      showToast(response.error, 'error');
      reportLoading.style.display = 'none';
      return;
    }

    currentReportData = response;

    // Update summary
    document.getElementById('report-total-products').textContent = response.summary.total_products;
    document.getElementById('report-products-with-sales').textContent = response.summary.products_with_sales;
    document.getElementById('report-total-items-sold').textContent = response.summary.total_items_sold.toLocaleString();
    document.getElementById('report-total-sales-value').textContent = '$' + formatCurrency(response.summary.total_sales_value || 0);
    document.getElementById('report-stores-processed').textContent = response.stores_info.stores_processed;
    document.getElementById('report-date-range').textContent = `${response.date_range.from} to ${response.date_range.to}`;
    document.getElementById('report-tag-used').textContent = response.stores_info.tag_used || 'N/A';

    // Show failed stores if any
    const failedStoresSection = document.getElementById('failed-stores-section');
    const failedStoresList = document.getElementById('failed-stores-list');

    if (response.stores_info.stores_failed && response.stores_info.stores_failed.length > 0) {
      failedStoresList.innerHTML = response.stores_info.stores_failed
        .map(failed => `
          <div style="padding: 0.5rem; background: rgba(239, 68, 68, 0.1); border-radius: 0.375rem; font-size: 0.875rem;">
            <span style="font-weight: 600; color: var(--accent-danger);">${failed.store}:</span>
            <span style="color: var(--text-secondary);">${failed.error}</span>
          </div>
        `)
        .join('');
      failedStoresSection.style.display = 'block';
    } else {
      failedStoresSection.style.display = 'none';
    }

    // Render report table
    renderReportTable(response.products);

    // Show results
    reportLoading.style.display = 'none';
    reportContent.style.display = 'block';
    exportButton.style.display = 'inline-flex';
    showToast('Report loaded successfully', 'success');
  } catch (error) {
    console.error('Error loading report:', error);
    showToast('Failed to load report', 'error');
    reportLoading.style.display = 'none';
  } finally {
    loadButton.disabled = false;
    loadButton.innerHTML = '<i class="fas fa-chart-bar"></i> Load Report';
  }
}

/**
 * Render report table
 */
function renderReportTable(products) {
  const tbody = document.getElementById('report-table-body');

  if (!products || products.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="8" style="text-align: center; padding: 2rem; color: var(--text-tertiary);">
          No products found for the selected date range
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = products
    .map((product, index) => `
      <tr style="border-bottom: 1px solid var(--border-color);">
        <td style="padding: 0.75rem; text-align: center; color: var(--text-tertiary);">${index + 1}</td>
        <td style="padding: 0.75rem; color: var(--text-primary); font-weight: 500;">${product.product_name || 'N/A'}</td>
        <td style="padding: 0.75rem; color: var(--text-secondary); font-family: monospace;">${product.upc_barcode || 'N/A'}</td>
        <td style="padding: 0.75rem; text-align: center; color: var(--text-primary); font-weight: 600; ${product.quantity_sold > 0 ? 'color: var(--accent-primary);' : ''}">${product.quantity_sold || 0}</td>
        <td style="padding: 0.75rem; text-align: center; color: var(--text-secondary);">${product.quantity_per_case || 'N/A'}</td>
        <td style="padding: 0.75rem; text-align: right; color: var(--text-secondary);">$${formatCurrency(product.price)}</td>
        <td style="padding: 0.75rem; text-align: right; color: var(--accent-primary); font-weight: 600;">$${formatCurrency(product.estimated_total)}</td>
        <td style="padding: 0.75rem; text-align: center; color: var(--text-secondary);">${product.available_quantity !== null && product.available_quantity !== undefined ? product.available_quantity : 'N/A'}</td>
      </tr>
    `)
    .join('');
}

/**
 * Sort report table
 */
function sortReportTable(column) {
  if (!currentReportData || !currentReportData.products) {
    return;
  }

  // Toggle direction if clicking same column
  if (currentSortColumn === column) {
    currentSortDirection = currentSortDirection === 'asc' ? 'desc' : 'asc';
  } else {
    currentSortColumn = column;
    currentSortDirection = 'desc';
  }

  // Sort products
  const sorted = [...currentReportData.products].sort((a, b) => {
    let aVal = a[column];
    let bVal = b[column];

    // Handle null/undefined values
    if (aVal === null || aVal === undefined) aVal = '';
    if (bVal === null || bVal === undefined) bVal = '';

    // Numeric sort
    if (typeof aVal === 'number' && typeof bVal === 'number') {
      return currentSortDirection === 'asc' ? aVal - bVal : bVal - aVal;
    }

    // String sort
    const aStr = String(aVal).toLowerCase();
    const bStr = String(bVal).toLowerCase();
    if (currentSortDirection === 'asc') {
      return aStr < bStr ? -1 : aStr > bStr ? 1 : 0;
    } else {
      return bStr < aStr ? -1 : bStr > aStr ? 1 : 0;
    }
  });

  // Update icons
  updateReportSortIcons();

  // Re-render table
  renderReportTable(sorted);
}

/**
 * Update sort column icons
 */
function updateReportSortIcons() {
  // Reset all icons
  const allIcons = document.querySelectorAll('[id^="report-sort-icon-"]');
  allIcons.forEach(icon => {
    icon.className = 'fas fa-sort';
  });

  // Set active icon
  const activeIcon = document.getElementById(`report-sort-icon-${currentSortColumn}`);
  if (activeIcon) {
    activeIcon.className = currentSortDirection === 'asc' ? 'fas fa-sort-up' : 'fas fa-sort-down';
  }
}

/**
 * Export report to Excel
 */
async function exportReport() {
  const fromDate = document.getElementById('report-from-date').value;
  const toDate = document.getElementById('report-to-date').value;

  if (!fromDate || !toDate) {
    showToast('Please select both start and end dates', 'error');
    return;
  }

  const exportButton = document.getElementById('export-report-btn');
  exportButton.disabled = true;
  exportButton.innerHTML = '<i class="spinner"></i> Exporting...';

  try {
    const response = await fetch('/api/reports/sc-sales/export', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        from_date: fromDate,
        to_date: toDate,
      }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Export failed');
    }

    // Get filename from response headers or use default
    const contentDisposition = response.headers.get('Content-Disposition');
    let filename = `sc_sales_report_${fromDate}_to_${toDate}.xlsx`;
    if (contentDisposition) {
      const filenameMatch = contentDisposition.match(/filename="?(.+)"?/);
      if (filenameMatch) {
        filename = filenameMatch[1];
      }
    }

    // Download file
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);

    showToast('Report exported successfully', 'success');
  } catch (error) {
    console.error('Export error:', error);
    showToast(error.message || 'Failed to export report', 'error');
  } finally {
    exportButton.disabled = false;
    exportButton.innerHTML = '<i class="fas fa-file-download"></i> Export to Excel';
  }
}

/**
 * Set date range to last 30 days
 */
function setLast30Days() {
  const today = new Date();
  const thirtyDaysAgo = new Date();
  thirtyDaysAgo.setDate(today.getDate() - 30);

  document.getElementById('report-to-date').valueAsDate = today;
  document.getElementById('report-from-date').valueAsDate = thirtyDaysAgo;
}

/**
 * Set date range to last 7 days
 */
function setLast7Days() {
  const today = new Date();
  const sevenDaysAgo = new Date();
  sevenDaysAgo.setDate(today.getDate() - 7);

  document.getElementById('report-to-date').valueAsDate = today;
  document.getElementById('report-from-date').valueAsDate = sevenDaysAgo;
}

/**
 * Set date range to this month
 */
function setThisMonth() {
  const today = new Date();
  const firstDayOfMonth = new Date(today.getFullYear(), today.getMonth(), 1);

  document.getElementById('report-from-date').valueAsDate = firstDayOfMonth;
  document.getElementById('report-to-date').valueAsDate = today;
}
