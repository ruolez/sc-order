// Settings management

let currentSettings = {};

// Load settings
async function loadSettings() {
    try {
        const settings = await apiRequest('/api/settings');
        currentSettings = settings;
        populateSettingsForm(settings);
    } catch (error) {
        showToast('Failed to load settings: ' + error.message, 'error');
    }
}

// Populate settings form
function populateSettingsForm(settings) {
    // Shopify settings
    const shopifyForm = document.getElementById('shopify-settings-form');
    if (shopifyForm) {
        shopifyForm.querySelector('[name="shopify_store_url"]').value = settings.shopify_store_url || '';
        shopifyForm.querySelector('[name="shopify_access_token"]').value = settings.shopify_access_token || '';

        // Set location ID if available
        const locationSelect = shopifyForm.querySelector('[name="shopify_location_id"]');
        if (settings.shopify_location_id && locationSelect) {
            // Check if this location exists as an option
            const existingOption = Array.from(locationSelect.options).find(
                opt => opt.value === settings.shopify_location_id
            );

            if (existingOption) {
                locationSelect.value = settings.shopify_location_id;
            } else {
                // Add it as an option if not present
                const option = document.createElement('option');
                option.value = settings.shopify_location_id;
                option.textContent = settings.shopify_location_id;
                option.selected = true;
                locationSelect.appendChild(option);
            }
        }

        // Set excluded SKUs
        const excludedSkusField = shopifyForm.querySelector('[name="excluded_skus"]');
        if (excludedSkusField) {
            excludedSkusField.value = settings.excluded_skus || '';
        }
    }

    // Additional Shopify stores (2-5)
    for (let i = 2; i <= 5; i++) {
        const urlField = document.querySelector(`[name="shopify_store_${i}_url"]`);
        const tokenField = document.querySelector(`[name="shopify_store_${i}_token"]`);
        const locationSelect = document.querySelector(`[name="shopify_store_${i}_location_id"]`);

        if (urlField) {
            urlField.value = settings[`shopify_store_${i}_url`] || '';
        }
        if (tokenField) {
            tokenField.value = settings[`shopify_store_${i}_token`] || '';
        }

        // Set location ID if available
        if (locationSelect && settings[`shopify_store_${i}_location_id`]) {
            const locationId = settings[`shopify_store_${i}_location_id`];
            // Check if this location exists as an option
            const existingOption = Array.from(locationSelect.options).find(
                opt => opt.value === locationId
            );

            if (existingOption) {
                locationSelect.value = locationId;
            } else {
                // Add it as an option if not present
                const option = document.createElement('option');
                option.value = locationId;
                option.textContent = locationId;
                option.selected = true;
                locationSelect.appendChild(option);
            }
        }
    }

    // MS SQL settings
    const mssqlForm = document.getElementById('mssql-settings-form');
    if (mssqlForm) {
        mssqlForm.querySelector('[name="mssql_server"]').value = settings.mssql_server || '';
        mssqlForm.querySelector('[name="mssql_database"]').value = settings.mssql_database || '';
        mssqlForm.querySelector('[name="mssql_username"]').value = settings.mssql_username || '';
        mssqlForm.querySelector('[name="mssql_password"]').value = settings.mssql_password || '';
        mssqlForm.querySelector('[name="mssql_port"]').value = settings.mssql_port || 1433;
    }

    // Sales sync settings
    const salesOrderTagField = document.querySelector('[name="sales_order_tag"]');
    if (salesOrderTagField) {
        salesOrderTagField.value = settings.sales_order_tag || '';
    }

    const salesSyncDaysField = document.querySelector('[name="sales_sync_days"]');
    if (salesSyncDaysField) {
        salesSyncDaysField.value = settings.sales_sync_days || 30;
    }

    // Update store name in header
    if (settings.shopify_store_url) {
        document.getElementById('store-name').textContent = settings.shopify_store_url;
    }
}

// Save all settings
async function saveSettings() {
    const shopifyForm = document.getElementById('shopify-settings-form');
    const mssqlForm = document.getElementById('mssql-settings-form');

    const settings = {
        shopify_store_url: shopifyForm.querySelector('[name="shopify_store_url"]').value,
        shopify_access_token: shopifyForm.querySelector('[name="shopify_access_token"]').value,
        shopify_location_id: shopifyForm.querySelector('[name="shopify_location_id"]').value,
        excluded_skus: shopifyForm.querySelector('[name="excluded_skus"]').value,
        mssql_server: mssqlForm.querySelector('[name="mssql_server"]').value,
        mssql_database: mssqlForm.querySelector('[name="mssql_database"]').value,
        mssql_username: mssqlForm.querySelector('[name="mssql_username"]').value,
        mssql_password: mssqlForm.querySelector('[name="mssql_password"]').value,
        mssql_port: parseInt(mssqlForm.querySelector('[name="mssql_port"]').value) || 1433,
        sales_order_tag: document.querySelector('[name="sales_order_tag"]').value,
        sales_sync_days: parseInt(document.querySelector('[name="sales_sync_days"]').value) || 30
    };

    // Add additional Shopify stores (2-5)
    for (let i = 2; i <= 5; i++) {
        const urlField = document.querySelector(`[name="shopify_store_${i}_url"]`);
        const tokenField = document.querySelector(`[name="shopify_store_${i}_token"]`);
        const locationSelect = document.querySelector(`[name="shopify_store_${i}_location_id"]`);

        if (urlField) {
            settings[`shopify_store_${i}_url`] = urlField.value;
        }
        if (tokenField) {
            settings[`shopify_store_${i}_token`] = tokenField.value;
        }
        if (locationSelect) {
            settings[`shopify_store_${i}_location_id`] = locationSelect.value;
        }
    }

    try {
        await apiRequest('/api/settings', {
            method: 'POST',
            body: JSON.stringify(settings)
        });
        showToast('Settings saved successfully', 'success');
        currentSettings = settings;

        // Update store name in header
        if (settings.shopify_store_url) {
            document.getElementById('store-name').textContent = settings.shopify_store_url;
        }
    } catch (error) {
        showToast('Failed to save settings: ' + error.message, 'error');
    }
}

// Test Shopify connection
async function testShopifyConnection() {
    try {
        const shopifyForm = document.getElementById('shopify-settings-form');
        const storeUrl = shopifyForm.querySelector('[name="shopify_store_url"]').value;
        const accessToken = shopifyForm.querySelector('[name="shopify_access_token"]').value;

        if (!storeUrl || !accessToken) {
            showToast('Please enter Store URL and Access Token', 'error');
            return;
        }

        showToast('Testing Shopify connection...', 'info');

        const result = await apiRequest('/api/shopify/test', {
            method: 'POST',
            body: JSON.stringify({
                shopify_store_url: storeUrl,
                shopify_access_token: accessToken
            })
        });

        if (result.success) {
            const shop = result.shop;
            showToast(`✓ Connected to ${shop.name}`, 'success');
        }
    } catch (error) {
        showToast('Shopify connection failed: ' + error.message, 'error');
    }
}

// Load Shopify locations
async function loadShopifyLocations(storeNumber = 1) {
    try {
        let storeUrl, accessToken, locationSelect;

        if (storeNumber === 1) {
            // Main store
            const shopifyForm = document.getElementById('shopify-settings-form');
            storeUrl = shopifyForm.querySelector('[name="shopify_store_url"]').value;
            accessToken = shopifyForm.querySelector('[name="shopify_access_token"]').value;
            locationSelect = shopifyForm.querySelector('[name="shopify_location_id"]');
        } else {
            // Additional stores (2-5)
            storeUrl = document.querySelector(`[name="shopify_store_${storeNumber}_url"]`).value;
            accessToken = document.querySelector(`[name="shopify_store_${storeNumber}_token"]`).value;
            locationSelect = document.querySelector(`[name="shopify_store_${storeNumber}_location_id"]`);
        }

        if (!storeUrl || !accessToken) {
            showToast(`Please enter Store URL and Access Token for Store ${storeNumber} first`, 'error');
            return;
        }

        showToast(`Loading locations from Store ${storeNumber}...`, 'info');

        const locations = await apiRequest('/api/shopify/locations', {
            method: 'POST',
            body: JSON.stringify({
                shopify_store_url: storeUrl,
                shopify_access_token: accessToken
            })
        });

        if (locations && locations.length > 0) {

            // Clear existing options except the first one
            locationSelect.innerHTML = '<option value="">-- Select a location --</option>';

            // Add location options
            locations.forEach(location => {
                const option = document.createElement('option');
                option.value = location.id;

                // Format location name with address if available
                let locationText = location.name;
                if (location.address && location.address.city) {
                    locationText += ` (${location.address.city}`;
                    if (location.address.province) {
                        locationText += `, ${location.address.province}`;
                    }
                    locationText += ')';
                }

                option.textContent = locationText;
                locationSelect.appendChild(option);
            });

            showToast(`Loaded ${locations.length} location(s)`, 'success');
        } else {
            showToast('No locations found', 'warning');
        }
    } catch (error) {
        showToast('Failed to load locations: ' + error.message, 'error');
    }
}

// Test MS SQL connection
async function testMSSQLConnection() {
    try {
        showToast('Testing MS SQL connection...', 'info');

        const result = await apiRequest('/api/mssql/test', {
            method: 'POST'
        });

        if (result.success) {
            const info = result.info;
            showToast(`✓ Connected to ${info.database} on ${info.server}`, 'success');
        }
    } catch (error) {
        showToast('MS SQL connection failed: ' + error.message, 'error');
    }
}

// Clear column data for all products
async function clearColumnData(columnName, displayName) {
    try {
        // Get product count first
        const products = await apiRequest('/api/products');
        const productCount = products.length;

        if (productCount === 0) {
            showToast('No products to update', 'info');
            return;
        }

        // Confirmation dialog
        if (!confirm(`Are you sure you want to clear ${displayName} for all ${productCount} product(s)?\n\nThis will set all values to empty and cannot be undone.`)) {
            return;
        }

        showToast(`Clearing ${displayName}...`, 'info');

        const result = await apiRequest('/api/products/clear-column', {
            method: 'POST',
            body: JSON.stringify({ column: columnName })
        });

        if (result.success) {
            showToast(`✓ ${result.message}`, 'success');

            // Reload products if user is on products view
            if (typeof loadProducts === 'function') {
                loadProducts();
            }
        }
    } catch (error) {
        showToast(`Failed to clear ${displayName}: ${error.message}`, 'error');
    }
}
