// Products management

let currentProducts = [];
let filteredProducts = [];
let editingProductId = null;

// Load products
async function loadProducts(includeInventory = false) {
    try {
        let url = '/api/products';
        if (includeInventory) {
            url = '/api/products/sync';
            showToast('Syncing with Shopify and MS SQL...', 'info');
        }

        const products = await apiRequest(url);
        currentProducts = products;
        filteredProducts = products;
        renderProducts(filteredProducts);

        if (includeInventory) {
            showToast('Inventory synced successfully', 'success');
        }
    } catch (error) {
        showToast('Failed to load products: ' + error.message, 'error');
    }
}

// Filter products based on search input
function filterProducts() {
    const searchTerm = document.getElementById('product-search').value.toLowerCase().trim();

    if (searchTerm === '') {
        filteredProducts = currentProducts;
        document.getElementById('filtered-count').classList.add('hidden');
    } else {
        filteredProducts = currentProducts.filter(product => {
            const productName = product.product_name ? product.product_name.toLowerCase() : '';
            const upcBarcode = product.upc_barcode ? product.upc_barcode.toLowerCase() : '';

            return productName.includes(searchTerm) || upcBarcode.includes(searchTerm);
        });

        // Show filtered count
        const filteredCountEl = document.getElementById('filtered-count');
        const filteredCountNumber = document.getElementById('filtered-count-number');
        filteredCountNumber.textContent = filteredProducts.length;
        filteredCountEl.classList.remove('hidden');
    }

    renderProducts(filteredProducts);
}

// Sync with Shopify inventory
async function syncInventory() {
    await loadProducts(true);
}

// Render products table
function renderProducts(products) {
    const tbody = document.getElementById('products-table-body');
    const countElement = document.getElementById('product-count');

    // Update product count
    if (countElement) {
        countElement.textContent = products.length;
    }

    if (products.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="8" class="px-6 py-8 text-center text-gray-500">
                    <i class="fas fa-box-open text-4xl mb-2"></i>
                    <p>No products found. Add products manually or import from Excel.</p>
                </td>
            </tr>
        `;
        return;
    }

    // Check if any products have Shopify data
    const hasShopifyData = products.some(p => p.shopify_matched);

    tbody.innerHTML = products.map((product, index) => {
        const shopifyQty = product.shopify_available !== undefined && product.shopify_available !== null
            ? product.shopify_available
            : '-';

        const shopifyStatus = product.shopify_matched
            ? '<span class="text-green-600"><i class="fas fa-check-circle"></i></span>'
            : '<span class="text-gray-400"><i class="fas fa-times-circle"></i></span>';

        const needsReorder = product.threshold_quantity && product.shopify_available !== null && product.shopify_available <= product.threshold_quantity
            ? '<span class="px-2 py-1 text-xs font-semibold text-white bg-red-500 rounded">Reorder</span>'
            : '';

        return `
        <tr class="hover:bg-gray-50">
            <td class="px-4 py-4 whitespace-nowrap text-sm text-gray-500 font-medium">${index + 1}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${product.product_name}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-600 font-mono">${product.upc_barcode}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${formatNumber(product.threshold_quantity)}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${formatNumber(product.quantity_per_case)}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${formatCurrency(product.price)}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-center ${product.shopify_matched ? 'text-gray-900' : 'text-gray-400'}">${shopifyQty}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-center">${shopifyStatus} ${needsReorder}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium space-x-2">
                <button onclick="editProduct(${product.id})" class="text-blue-600 hover:text-blue-900">
                    <i class="fas fa-edit"></i>
                </button>
                <button onclick="deleteProduct(${product.id})" class="text-red-600 hover:text-red-900">
                    <i class="fas fa-trash"></i>
                </button>
            </td>
        </tr>
        `;
    }).join('');
}

// Open product modal
function openProductModal(productId = null) {
    const modal = document.getElementById('product-modal');
    const form = document.getElementById('product-form');
    const title = document.getElementById('modal-title');

    // Reset form
    form.reset();
    editingProductId = productId;

    if (productId) {
        // Edit mode
        title.textContent = 'Edit Product';
        const product = currentProducts.find(p => p.id === productId);
        if (product) {
            document.getElementById('product-id').value = product.id;
            document.getElementById('product-name').value = product.product_name;
            document.getElementById('product-barcode').value = product.upc_barcode;
            document.getElementById('product-threshold').value = product.threshold_quantity || '';
            document.getElementById('product-qty-case').value = product.quantity_per_case || '';
            document.getElementById('product-price').value = product.price || '';
        }
    } else {
        // Add mode
        title.textContent = 'Add Product';
    }

    modal.classList.remove('hidden');
    modal.classList.add('flex');
}

// Close product modal
function closeProductModal() {
    const modal = document.getElementById('product-modal');
    modal.classList.remove('flex');
    modal.classList.add('hidden');
    editingProductId = null;
}

// Product form submit handler
document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('product-form');
    if (form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();

            const productData = {
                product_name: document.getElementById('product-name').value,
                upc_barcode: document.getElementById('product-barcode').value,
                threshold_quantity: parseInt(document.getElementById('product-threshold').value) || null,
                quantity_per_case: parseInt(document.getElementById('product-qty-case').value) || null,
                price: parseFloat(document.getElementById('product-price').value) || null
            };

            try {
                if (editingProductId) {
                    // Update
                    await apiRequest(`/api/products/${editingProductId}`, {
                        method: 'PUT',
                        body: JSON.stringify(productData)
                    });
                    showToast('Product updated successfully', 'success');
                } else {
                    // Create
                    await apiRequest('/api/products', {
                        method: 'POST',
                        body: JSON.stringify(productData)
                    });
                    showToast('Product created successfully', 'success');
                }

                closeProductModal();
                loadProducts();
            } catch (error) {
                showToast('Failed to save product: ' + error.message, 'error');
            }
        });
    }
});

// Edit product
function editProduct(productId) {
    openProductModal(productId);
}

// Delete product
async function deleteProduct(productId) {
    if (!confirm('Are you sure you want to delete this product?')) {
        return;
    }

    try {
        await apiRequest(`/api/products/${productId}`, {
            method: 'DELETE'
        });
        showToast('Product deleted successfully', 'success');
        loadProducts();
    } catch (error) {
        showToast('Failed to delete product: ' + error.message, 'error');
    }
}

// Clear all products
async function clearAllProducts() {
    const productCount = currentProducts.length;

    if (productCount === 0) {
        showToast('No products to delete', 'info');
        return;
    }

    if (!confirm(`Are you sure you want to delete ALL ${productCount} product(s)? This action cannot be undone!`)) {
        return;
    }

    // Double confirmation for safety
    if (!confirm('This will permanently delete all products. Are you absolutely sure?')) {
        return;
    }

    try {
        const result = await apiRequest('/api/products/batch', {
            method: 'DELETE'
        });
        showToast(`Successfully deleted ${result.count} product(s)`, 'success');
        loadProducts();
    } catch (error) {
        showToast('Failed to delete products: ' + error.message, 'error');
    }
}
