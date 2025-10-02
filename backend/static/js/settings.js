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
        mssql_server: mssqlForm.querySelector('[name="mssql_server"]').value,
        mssql_database: mssqlForm.querySelector('[name="mssql_database"]').value,
        mssql_username: mssqlForm.querySelector('[name="mssql_username"]').value,
        mssql_password: mssqlForm.querySelector('[name="mssql_password"]').value,
        mssql_port: parseInt(mssqlForm.querySelector('[name="mssql_port"]').value) || 1433
    };

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
async function loadShopifyLocations() {
    try {
        const shopifyForm = document.getElementById('shopify-settings-form');
        const storeUrl = shopifyForm.querySelector('[name="shopify_store_url"]').value;
        const accessToken = shopifyForm.querySelector('[name="shopify_access_token"]').value;

        if (!storeUrl || !accessToken) {
            showToast('Please enter Store URL and Access Token first', 'error');
            return;
        }

        showToast('Loading locations from Shopify...', 'info');

        const locations = await apiRequest('/api/shopify/locations', {
            method: 'POST',
            body: JSON.stringify({
                shopify_store_url: storeUrl,
                shopify_access_token: accessToken
            })
        });

        if (locations && locations.length > 0) {
            const locationSelect = shopifyForm.querySelector('[name="shopify_location_id"]');

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
