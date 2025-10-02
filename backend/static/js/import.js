// Excel import functionality

async function importExcel() {
    const fileInput = document.getElementById('excel-file-input');
    const file = fileInput.files[0];

    if (!file) {
        showToast('Please select a file first', 'error');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
        const resultDiv = document.getElementById('import-result');
        resultDiv.innerHTML = '<div class="flex items-center justify-center py-4"><div class="spinner"></div><span class="ml-2">Importing...</span></div>';

        const response = await fetch('/api/products/import', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.error || 'Import failed');
        }

        // Show success message
        resultDiv.innerHTML = `
            <div class="bg-green-50 border-l-4 border-green-500 p-4">
                <div class="flex">
                    <i class="fas fa-check-circle text-green-500 mr-2 mt-1"></i>
                    <div>
                        <p class="font-medium text-green-800">${result.message}</p>
                        ${result.details.errors.length > 0 ? `
                            <details class="mt-2">
                                <summary class="cursor-pointer text-sm text-green-700">Show errors (${result.details.errors.length})</summary>
                                <ul class="mt-2 text-sm text-gray-600 list-disc list-inside">
                                    ${result.details.errors.map(err => `<li>${err}</li>`).join('')}
                                </ul>
                            </details>
                        ` : ''}
                    </div>
                </div>
            </div>
        `;

        showToast('Products imported successfully', 'success');

        // Clear file input
        fileInput.value = '';

        // Reload products if we're on the products view
        if (!document.getElementById('products-view').classList.contains('hidden')) {
            loadProducts();
        }
    } catch (error) {
        const resultDiv = document.getElementById('import-result');
        resultDiv.innerHTML = `
            <div class="bg-red-50 border-l-4 border-red-500 p-4">
                <div class="flex">
                    <i class="fas fa-exclamation-circle text-red-500 mr-2 mt-1"></i>
                    <div>
                        <p class="font-medium text-red-800">Import failed</p>
                        <p class="text-sm text-red-700">${error.message}</p>
                    </div>
                </div>
            </div>
        `;
        showToast('Import failed: ' + error.message, 'error');
    }
}
