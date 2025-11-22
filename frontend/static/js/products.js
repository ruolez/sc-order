// Products management

let currentProducts = [];
let filteredProducts = [];
let editingProductId = null;
let sortColumn = null;
let sortDirection = "asc";
let orderFilterActive = false;

// Load products
async function loadProducts() {
  try {
    // Capture current state before reload
    const selectedProductIds = [];
    const productCheckboxes = document.querySelectorAll(".product-checkbox");
    productCheckboxes.forEach((checkbox) => {
      if (checkbox.checked) {
        selectedProductIds.push(parseInt(checkbox.dataset.productId));
      }
    });

    // Fetch fresh data
    const products = await apiRequest("/api/products");
    currentProducts = products;

    // Reapply filters and search
    applyFilters();

    // Reapply sort if active
    if (sortColumn) {
      filteredProducts.sort((a, b) => {
        let aValue = a[sortColumn];
        let bValue = b[sortColumn];

        // Handle null/undefined values
        if (aValue === null || aValue === undefined) aValue = "";
        if (bValue === null || bValue === undefined) bValue = "";

        // Convert to appropriate types for comparison
        if (typeof aValue === "string") aValue = aValue.toLowerCase();
        if (typeof bValue === "string") bValue = bValue.toLowerCase();

        if (aValue < bValue) return sortDirection === "asc" ? -1 : 1;
        if (aValue > bValue) return sortDirection === "asc" ? 1 : -1;
        return 0;
      });
    }

    // Render with current state
    renderProducts(filteredProducts);

    // Restore checkbox selections
    restoreCheckboxSelections(selectedProductIds);

    // Restore sort icons
    updateSortIcons();

    // Update low stock count
    updateLowStockCount();
  } catch (error) {
    showToast("Failed to load products: " + error.message, "error");
  }
}

// Toggle order filter (show only products that need to be ordered)
function toggleOrderFilter() {
  if (orderFilterActive) return; // Already active, use "All" button to clear

  orderFilterActive = true;
  const btn = document.getElementById("order-filter-btn");
  const allBtn = document.getElementById("all-filter-btn");

  btn.classList.add("active");
  allBtn.classList.remove("active");

  applyFilters();
}

// Clear order filter
function clearOrderFilter() {
  if (orderFilterActive) {
    orderFilterActive = false;
    const btn = document.getElementById("order-filter-btn");
    const allBtn = document.getElementById("all-filter-btn");
    btn.classList.remove("active");
    allBtn.classList.add("active");
    applyFilters();
  }
}

// Update low stock count
function updateLowStockCount() {
  const lowStockCount = currentProducts.filter((product) => {
    const availableQty =
      product.available_quantity !== undefined &&
      product.available_quantity !== null
        ? product.available_quantity
        : 0;
    const thresholdQty = product.threshold_quantity || 0;
    return availableQty <= thresholdQty;
  }).length;

  const lowStockElement = document.getElementById("low-stock-count");
  if (lowStockElement) {
    lowStockElement.textContent = lowStockCount;
  }
}

// Apply all filters (search + order filter)
function applyFilters() {
  const searchTerm = document
    .getElementById("product-search")
    .value.toLowerCase()
    .trim();
  let products = currentProducts;

  // Apply order filter first (products that need reordering)
  if (orderFilterActive) {
    products = products.filter((product) => {
      const availableQty =
        product.available_quantity !== undefined &&
        product.available_quantity !== null
          ? product.available_quantity
          : 0;
      const thresholdQty = product.threshold_quantity || 0;
      return availableQty <= thresholdQty;
    });
  }

  // Apply search filter
  if (searchTerm !== "") {
    products = products.filter((product) => {
      const productName = product.product_name
        ? product.product_name.toLowerCase()
        : "";
      const upcBarcode = product.upc_barcode
        ? product.upc_barcode.toLowerCase()
        : "";
      return (
        productName.includes(searchTerm) || upcBarcode.includes(searchTerm)
      );
    });
  }

  // Update filtered products
  filteredProducts = products;

  // Update filtered count display
  if (searchTerm !== "" || orderFilterActive) {
    const filteredCountEl = document.getElementById("filtered-count");
    const filteredCountNumber = document.getElementById(
      "filtered-count-number",
    );
    filteredCountNumber.textContent = filteredProducts.length;
    filteredCountEl.classList.remove("hidden");
  } else {
    document.getElementById("filtered-count").classList.add("hidden");
  }

  renderProducts(filteredProducts);
}

// Filter products based on search input
function filterProducts() {
  applyFilters();
}

// Sync with Shopify inventory with progress tracking
async function syncInventory() {
  // Show progress modal
  const modal = document.getElementById("sync-progress-modal");
  modal.classList.remove("hidden");
  modal.classList.add("flex");

  // Update modal title for inventory sync
  modal.querySelector("h3").textContent = "Syncing Inventory";
  modal.querySelector("p").textContent = "Syncing products with Shopify...";

  // Reset progress UI
  document.getElementById("sync-progress-bar").style.width = "0%";
  document.getElementById("sync-progress-text").textContent = "Starting...";
  document.getElementById("sync-progress-percentage").textContent = "0%";
  document.getElementById("sync-current-product").textContent =
    "Preparing sync...";
  document.getElementById("sync-synced-count").textContent = "0";
  document.getElementById("sync-notfound-count").textContent = "0";
  document.getElementById("sync-error-count").textContent = "0";
  const closeBtn = document.getElementById("sync-close-button");
  closeBtn.disabled = true;
  closeBtn.style.opacity = "0.5";
  closeBtn.style.cursor = "not-allowed";

  // Hide not found section
  document.getElementById("sync-notfound-section").classList.add("hidden");
  document.getElementById("sync-notfound-list").classList.add("hidden");

  let syncedCount = 0;
  let notFoundCount = 0;
  let errorCount = 0;

  try {
    // Create EventSource for Server-Sent Events
    const eventSource = new EventSource("/api/products/sync");

    eventSource.onmessage = function (event) {
      const data = JSON.parse(event.data);

      if (data.type === "start") {
        document.getElementById("sync-progress-text").textContent =
          `Syncing 0 of ${data.total} products`;
      } else if (data.type === "progress") {
        const percentage = Math.round((data.current / data.total) * 100);
        document.getElementById("sync-progress-bar").style.width =
          `${percentage}%`;
        document.getElementById("sync-progress-percentage").textContent =
          `${percentage}%`;
        document.getElementById("sync-progress-text").textContent =
          `Syncing ${data.current} of ${data.total} products`;

        // Update current product status
        let statusText = "";
        if (data.status === "synced") {
          statusText = `✓ ${data.product_name} - Qty: ${data.quantity}`;
          syncedCount++;
          document.getElementById("sync-synced-count").textContent =
            syncedCount;
        } else if (data.status === "not_found") {
          statusText = `⚠ ${data.product_name} - Not found`;
          notFoundCount++;
          document.getElementById("sync-notfound-count").textContent =
            notFoundCount;
        } else if (data.status === "error") {
          statusText = `✗ ${data.product_name} - Error`;
          errorCount++;
          document.getElementById("sync-error-count").textContent = errorCount;
        } else if (data.status === "skipped") {
          statusText = `⊘ ${data.product_name} - Skipped`;
        }

        document.getElementById("sync-current-product").textContent =
          statusText;
      } else if (data.type === "complete") {
        eventSource.close();
        document.getElementById("sync-progress-bar").style.width = "100%";
        document.getElementById("sync-progress-percentage").textContent =
          "100%";
        document.getElementById("sync-progress-text").textContent =
          "Sync complete!";
        document.getElementById("sync-current-product").textContent =
          `✓ Synced ${data.synced} of ${data.total} products`;

        // Show not found products if any
        if (data.not_found_products && data.not_found_products.length > 0) {
          const notFoundSection = document.getElementById(
            "sync-notfound-section",
          );
          const notFoundListContainer =
            document.getElementById("sync-notfound-list");
          const notFoundList = notFoundListContainer.querySelector("div");
          const notFoundSectionCount = document.getElementById(
            "sync-notfound-section-count",
          );

          notFoundSectionCount.textContent = data.not_found_products.length;
          notFoundSection.style.display = "block";
          notFoundSection.classList.remove("hidden");

          // Clear previous list
          notFoundList.innerHTML = "";

          // Add each not found product
          data.not_found_products.forEach((product) => {
            const productEl = document.createElement("div");
            productEl.style.cssText =
              "font-size: 0.75rem; color: var(--text-secondary); padding: 0.5rem; background: rgba(245, 158, 11, 0.1); border-radius: 0.375rem; border: 1px solid rgba(245, 158, 11, 0.2);";
            productEl.innerHTML = `<strong style="color: var(--text-primary);">${product.product_name}</strong><br>SKU: ${product.upc_barcode}`;
            notFoundList.appendChild(productEl);
          });
        }

        // Enable close button
        const closeBtn = document.getElementById("sync-close-button");
        closeBtn.disabled = false;
        closeBtn.style.opacity = "1";
        closeBtn.style.cursor = "pointer";

        // Show success message
        showToast(
          `Sync complete! ${data.synced} products synced, ${data.not_found} not found`,
          "success",
        );

        // Reload products to show updated quantities and low stock count
        setTimeout(() => {
          loadProducts();
        }, 1000);
      } else if (data.type === "error") {
        eventSource.close();
        document.getElementById("sync-current-product").textContent =
          `✗ Error: ${data.message}`;
        document.getElementById("sync-close-button").disabled = false;
        document
          .getElementById("sync-close-button")
          .classList.remove("cursor-not-allowed", "bg-gray-300");
        document
          .getElementById("sync-close-button")
          .classList.add("bg-blue-600", "hover:bg-blue-700", "text-white");
        showToast("Sync failed: " + data.message, "error");
      }
    };

    eventSource.onerror = function (error) {
      console.error("EventSource error:", error);
      eventSource.close();
      document.getElementById("sync-current-product").textContent =
        "✗ Connection error";
      const closeBtn = document.getElementById("sync-close-button");
      closeBtn.disabled = false;
      closeBtn.style.opacity = "1";
      closeBtn.style.cursor = "pointer";
      showToast("Sync connection failed", "error");
    };
  } catch (error) {
    console.error("Sync error:", error);
    showToast("Failed to start sync: " + error.message, "error");
    const closeBtn = document.getElementById("sync-close-button");
    closeBtn.disabled = false;
    closeBtn.style.opacity = "1";
    closeBtn.style.cursor = "pointer";
  }
}

// Sync prices from MS SQL Server
async function syncPrice() {
  // Show progress modal
  const modal = document.getElementById("sync-progress-modal");
  modal.classList.remove("hidden");
  modal.classList.add("flex");

  // Update modal title for price sync
  modal.querySelector("h3").textContent = "Syncing Prices";
  modal.querySelector("p").textContent =
    "Syncing product prices from MS SQL Server...";

  // Reset progress UI
  document.getElementById("sync-progress-bar").style.width = "0%";
  document.getElementById("sync-progress-text").textContent =
    "Starting price sync...";
  document.getElementById("sync-progress-percentage").textContent = "0%";
  document.getElementById("sync-current-product").textContent =
    "Preparing sync...";
  document.getElementById("sync-synced-count").textContent = "0";
  document.getElementById("sync-notfound-count").textContent = "0";
  document.getElementById("sync-error-count").textContent = "0";
  const closeBtn = document.getElementById("sync-close-button");
  closeBtn.disabled = true;
  closeBtn.style.opacity = "0.5";
  closeBtn.style.cursor = "not-allowed";

  // Hide not found section and clear previous content
  const notFoundSection = document.getElementById("sync-notfound-section");
  const notFoundList = document.getElementById("sync-notfound-list");
  notFoundSection.classList.add("hidden");
  notFoundSection.style.display = "none";
  notFoundList.classList.add("hidden");
  notFoundList.style.display = "none";

  // Clear previous not found products
  const notFoundListContainer = notFoundList.querySelector("div");
  if (notFoundListContainer) {
    notFoundListContainer.innerHTML = "";
  }

  let syncedCount = 0;
  let notFoundCount = 0;
  let errorCount = 0;

  try {
    // Create EventSource for Server-Sent Events
    const eventSource = new EventSource("/api/products/sync-price");

    eventSource.onmessage = function (event) {
      const data = JSON.parse(event.data);

      if (data.type === "start") {
        document.getElementById("sync-progress-text").textContent =
          `Syncing prices for 0 of ${data.total} products`;
      } else if (data.type === "progress") {
        const percentage = Math.round((data.current / data.total) * 100);
        document.getElementById("sync-progress-bar").style.width =
          `${percentage}%`;
        document.getElementById("sync-progress-percentage").textContent =
          `${percentage}%`;
        document.getElementById("sync-progress-text").textContent =
          `Syncing prices for ${data.current} of ${data.total} products`;

        // Update current product status
        let statusText = "";
        if (data.status === "synced") {
          statusText = `✓ ${data.product_name} - Price: $${data.price.toFixed(2)}`;
          syncedCount++;
          document.getElementById("sync-synced-count").textContent =
            syncedCount;
        } else if (data.status === "not_found") {
          statusText = `⚠ ${data.product_name} - Not found`;
          notFoundCount++;
          document.getElementById("sync-notfound-count").textContent =
            notFoundCount;
        } else if (data.status === "error") {
          statusText = `✗ ${data.product_name} - Error`;
          errorCount++;
          document.getElementById("sync-error-count").textContent = errorCount;
        } else if (data.status === "skipped") {
          statusText = `⊘ ${data.product_name} - Skipped`;
        }

        document.getElementById("sync-current-product").textContent =
          statusText;
      } else if (data.type === "complete") {
        eventSource.close();
        document.getElementById("sync-progress-bar").style.width = "100%";
        document.getElementById("sync-progress-percentage").textContent =
          "100%";
        document.getElementById("sync-progress-text").textContent =
          "Price sync complete!";
        document.getElementById("sync-current-product").textContent =
          `✓ Synced prices for ${data.synced} of ${data.total} products`;

        // Show not found products if any
        if (data.not_found_products && data.not_found_products.length > 0) {
          const notFoundSection = document.getElementById(
            "sync-notfound-section",
          );
          const notFoundListContainer =
            document.getElementById("sync-notfound-list");
          const notFoundList = notFoundListContainer.querySelector("div");
          const notFoundSectionCount = document.getElementById(
            "sync-notfound-section-count",
          );

          notFoundSectionCount.textContent = data.not_found_products.length;
          notFoundSection.style.display = "block";
          notFoundSection.classList.remove("hidden");

          // Clear previous list
          notFoundList.innerHTML = "";

          // Add each not found product
          data.not_found_products.forEach((product) => {
            const productEl = document.createElement("div");
            productEl.style.cssText =
              "font-size: 0.75rem; color: var(--text-secondary); padding: 0.5rem; background: rgba(245, 158, 11, 0.1); border-radius: 0.375rem; border: 1px solid rgba(245, 158, 11, 0.2);";
            productEl.innerHTML = `<strong style="color: var(--text-primary);">${product.product_name}</strong><br>SKU: ${product.upc_barcode}`;
            notFoundList.appendChild(productEl);
          });
        }

        // Enable close button
        const closeBtn = document.getElementById("sync-close-button");
        closeBtn.disabled = false;
        closeBtn.style.opacity = "1";
        closeBtn.style.cursor = "pointer";

        // Show success message
        showToast(
          `Price sync complete! ${data.synced} products synced, ${data.not_found} not found`,
          "success",
        );

        // Reload products to show updated prices and low stock count
        setTimeout(() => {
          loadProducts();
        }, 1000);
      } else if (data.type === "error") {
        eventSource.close();
        document.getElementById("sync-current-product").textContent =
          `✗ Error: ${data.message}`;
        const closeBtn = document.getElementById("sync-close-button");
        closeBtn.disabled = false;
        closeBtn.style.opacity = "1";
        closeBtn.style.cursor = "pointer";
        showToast("Price sync failed: " + data.message, "error");
      }
    };

    eventSource.onerror = function (error) {
      console.error("EventSource error:", error);
      eventSource.close();
      document.getElementById("sync-current-product").textContent =
        "✗ Connection error";
      const closeBtn = document.getElementById("sync-close-button");
      closeBtn.disabled = false;
      closeBtn.style.opacity = "1";
      closeBtn.style.cursor = "pointer";
      showToast("Price sync connection failed", "error");
    };
  } catch (error) {
    console.error("Price sync error:", error);
    showToast("Failed to start price sync: " + error.message, "error");
    const closeBtn = document.getElementById("sync-close-button");
    closeBtn.disabled = false;
    closeBtn.style.opacity = "1";
    closeBtn.style.cursor = "pointer";
  }
}

// Sync sales data from Shopify orders (last month)
async function syncSales() {
  // Show progress modal
  const modal = document.getElementById("sync-progress-modal");
  modal.classList.remove("hidden");
  modal.classList.add("flex");

  // Update modal title for sales sync
  modal.querySelector("h3").textContent = "Syncing Sales Data";
  modal.querySelector("p").textContent =
    "Syncing product sales from Shopify orders (last 30 days)...";

  // Reset progress UI
  document.getElementById("sync-progress-bar").style.width = "0%";
  document.getElementById("sync-progress-text").textContent =
    "Starting sales sync...";
  document.getElementById("sync-progress-percentage").textContent = "0%";
  document.getElementById("sync-current-product").textContent =
    "Preparing sync...";
  document.getElementById("sync-synced-count").textContent = "0";
  document.getElementById("sync-notfound-count").textContent = "0";
  document.getElementById("sync-error-count").textContent = "0";
  const closeBtn = document.getElementById("sync-close-button");
  closeBtn.disabled = true;
  closeBtn.style.opacity = "0.5";
  closeBtn.style.cursor = "not-allowed";

  // Hide not found section and clear previous content
  const notFoundSection = document.getElementById("sync-notfound-section");
  const notFoundList = document.getElementById("sync-notfound-list");
  notFoundSection.classList.add("hidden");
  notFoundSection.style.display = "none";
  notFoundList.classList.add("hidden");
  notFoundList.style.display = "none";

  // Clear previous not found products
  const notFoundListContainer = notFoundList.querySelector("div");
  if (notFoundListContainer) {
    notFoundListContainer.innerHTML = "";
  }

  let syncedCount = 0;
  let notFoundCount = 0;
  let errorCount = 0;

  try {
    // Get IDs of currently visible (filtered) products
    const visibleProductIds = filteredProducts.map((p) => p.id).join(",");

    // Create EventSource for Server-Sent Events with filtered product IDs
    const eventSource = new EventSource(
      `/api/products/sync-sales?product_ids=${visibleProductIds}`,
    );

    eventSource.onmessage = function (event) {
      const data = JSON.parse(event.data);

      if (data.type === "start") {
        document.getElementById("sync-progress-text").textContent =
          `Syncing sales for 0 of ${data.total} products`;
      } else if (data.type === "status") {
        // Display intermediate status messages
        document.getElementById("sync-current-product").textContent =
          data.message;
      } else if (data.type === "progress") {
        const percentage = Math.round((data.current / data.total) * 100);
        document.getElementById("sync-progress-bar").style.width =
          `${percentage}%`;
        document.getElementById("sync-progress-percentage").textContent =
          `${percentage}%`;
        document.getElementById("sync-progress-text").textContent =
          `Syncing sales for ${data.current} of ${data.total} products`;

        // Update current product status
        let statusText = "";
        if (data.status === "synced") {
          statusText = `✓ ${data.product_name} - Sold: ${data.quantity}`;
          syncedCount++;
          document.getElementById("sync-synced-count").textContent =
            syncedCount;
        } else if (data.status === "not_found") {
          statusText = `⚠ ${data.product_name} - Not found`;
          notFoundCount++;
          document.getElementById("sync-notfound-count").textContent =
            notFoundCount;
        } else if (data.status === "error") {
          statusText = `✗ ${data.product_name} - Error`;
          errorCount++;
          document.getElementById("sync-error-count").textContent = errorCount;
        } else if (data.status === "skipped") {
          statusText = `⊘ ${data.product_name} - Skipped`;
        }

        document.getElementById("sync-current-product").textContent =
          statusText;
      } else if (data.type === "complete") {
        eventSource.close();
        document.getElementById("sync-progress-bar").style.width = "100%";
        document.getElementById("sync-progress-percentage").textContent =
          "100%";
        document.getElementById("sync-progress-text").textContent =
          "Sales sync complete!";
        document.getElementById("sync-current-product").textContent =
          `✓ Synced sales for ${data.synced} of ${data.total} products`;

        // Show not found products if any
        if (data.not_found_products && data.not_found_products.length > 0) {
          const notFoundSection = document.getElementById(
            "sync-notfound-section",
          );
          const notFoundListContainer =
            document.getElementById("sync-notfound-list");
          const notFoundList = notFoundListContainer.querySelector("div");
          const notFoundSectionCount = document.getElementById(
            "sync-notfound-section-count",
          );

          notFoundSectionCount.textContent = data.not_found_products.length;
          notFoundSection.style.display = "block";
          notFoundSection.classList.remove("hidden");

          // Clear previous list
          notFoundList.innerHTML = "";

          // Add each not found product
          data.not_found_products.forEach((product) => {
            const productEl = document.createElement("div");
            productEl.style.cssText =
              "font-size: 0.75rem; color: var(--text-secondary); padding: 0.5rem; background: rgba(245, 158, 11, 0.1); border-radius: 0.375rem; border: 1px solid rgba(245, 158, 11, 0.2);";
            productEl.innerHTML = `<strong style="color: var(--text-primary);">${product.product_name}</strong><br>SKU: ${product.upc_barcode}`;
            notFoundList.appendChild(productEl);
          });
        }

        // Enable close button
        const closeBtn = document.getElementById("sync-close-button");
        closeBtn.disabled = false;
        closeBtn.style.opacity = "1";
        closeBtn.style.cursor = "pointer";

        // Show success message
        showToast(
          `Sales sync complete! ${data.synced} products synced, ${data.not_found} with no sales`,
          "success",
        );

        // Reload products to show updated sales data and low stock count
        setTimeout(() => {
          loadProducts();
        }, 1000);
      } else if (data.type === "error") {
        eventSource.close();
        document.getElementById("sync-current-product").textContent =
          `✗ Error: ${data.message}`;
        document.getElementById("sync-close-button").disabled = false;
        document
          .getElementById("sync-close-button")
          .classList.remove("cursor-not-allowed", "bg-gray-300");
        document
          .getElementById("sync-close-button")
          .classList.add("bg-blue-600", "hover:bg-blue-700", "text-white");
        showToast("Sales sync failed: " + data.message, "error");
      }
    };

    eventSource.onerror = function (error) {
      console.error("EventSource error:", error);
      eventSource.close();
      document.getElementById("sync-current-product").textContent =
        "✗ Connection error";
      const closeBtn = document.getElementById("sync-close-button");
      closeBtn.disabled = false;
      closeBtn.style.opacity = "1";
      closeBtn.style.cursor = "pointer";
      showToast("Sales sync connection failed", "error");
    };
  } catch (error) {
    console.error("Sales sync error:", error);
    showToast("Failed to start sales sync: " + error.message, "error");
    const closeBtn = document.getElementById("sync-close-button");
    closeBtn.disabled = false;
    closeBtn.style.opacity = "1";
    closeBtn.style.cursor = "pointer";
  }
}

// Close sync progress modal
function closeSyncModal() {
  const modal = document.getElementById("sync-progress-modal");
  modal.classList.remove("flex");
  modal.classList.add("hidden");
}

// Toggle not found products list
function toggleNotFoundList() {
  const list = document.getElementById("sync-notfound-list");
  const icon = document.getElementById("sync-notfound-toggle-icon");

  if (list.classList.contains("hidden")) {
    list.classList.remove("hidden");
    list.style.display = "block";
    icon.classList.remove("fa-chevron-down");
    icon.classList.add("fa-chevron-up");
  } else {
    list.classList.add("hidden");
    list.style.display = "none";
    icon.classList.remove("fa-chevron-up");
    icon.classList.add("fa-chevron-down");
  }
}

// Sort products by column
function sortProducts(column) {
  // Toggle direction if same column, otherwise default to asc
  if (sortColumn === column) {
    sortDirection = sortDirection === "asc" ? "desc" : "asc";
  } else {
    sortColumn = column;
    sortDirection = "asc";
  }

  // Update sort icons
  const allIcons = document.querySelectorAll('[id^="sort-icon-"]');
  allIcons.forEach((icon) => {
    icon.className = "fas fa-sort ml-1 text-gray-400";
  });

  const currentIcon = document.getElementById(`sort-icon-${column}`);
  if (currentIcon) {
    currentIcon.className =
      sortDirection === "asc"
        ? "fas fa-sort-up ml-1 text-blue-600"
        : "fas fa-sort-down ml-1 text-blue-600";
  }

  // Sort the filtered products array
  filteredProducts.sort((a, b) => {
    let aValue = a[column];
    let bValue = b[column];

    // Handle null/undefined values
    if (aValue === null || aValue === undefined) aValue = "";
    if (bValue === null || bValue === undefined) bValue = "";

    // Convert to appropriate types for comparison
    if (typeof aValue === "string") aValue = aValue.toLowerCase();
    if (typeof bValue === "string") bValue = bValue.toLowerCase();

    if (aValue < bValue) return sortDirection === "asc" ? -1 : 1;
    if (aValue > bValue) return sortDirection === "asc" ? 1 : -1;
    return 0;
  });

  // Re-render the table
  renderProducts(filteredProducts);
}

// Update sort icons to reflect current sort state
function updateSortIcons() {
  // Reset all icons
  const allIcons = document.querySelectorAll('[id^="sort-icon-"]');
  allIcons.forEach((icon) => {
    icon.className = "fas fa-sort ml-1 text-gray-400";
  });

  // Update current sort column icon
  if (sortColumn) {
    const currentIcon = document.getElementById(`sort-icon-${sortColumn}`);
    if (currentIcon) {
      currentIcon.className =
        sortDirection === "asc"
          ? "fas fa-sort-up ml-1 text-blue-600"
          : "fas fa-sort-down ml-1 text-blue-600";
    }
  }
}

// Render products table
function renderProducts(products) {
  const tbody = document.getElementById("products-table-body");
  const countElement = document.getElementById("product-count");

  // Update product count
  if (countElement) {
    countElement.textContent = products.length;
  }

  if (products.length === 0) {
    tbody.innerHTML = `
            <tr>
                <td colspan="10" style="padding: 2rem; text-align: center; color: var(--text-tertiary);">
                    <i class="fas fa-box-open" style="font-size: 2.5rem; margin-bottom: 0.5rem;"></i>
                    <p>No products found. Add products manually or import from Excel.</p>
                </td>
            </tr>
        `;
    updateOrderTotal();
    return;
  }

  tbody.innerHTML = products
    .map((product, index) => {
      // Display available quantity from database
      const availableQty =
        product.available_quantity !== undefined &&
        product.available_quantity !== null
          ? product.available_quantity
          : "-";

      // Display quantity sold last month
      const soldQty =
        product.quantity_sold_last_month !== undefined &&
        product.quantity_sold_last_month !== null
          ? product.quantity_sold_last_month
          : "-";

      return `
        <tr>
            <td style="text-align: center;">
                <input
                    type="checkbox"
                    class="checkbox product-checkbox"
                    data-product-id="${product.id}"
                    data-price="${product.price || 0}"
                    data-order-qty="${soldQty !== "-" ? soldQty : 0}"
                    onchange="updateOrderTotal()"
                />
            </td>
            <td>${index + 1}</td>
            <td><strong>${product.product_name}</strong></td>
            <td style="font-family: 'Courier New', monospace;">${product.upc_barcode}</td>
            <td>${formatNumber(product.threshold_quantity)}</td>
            <td>${formatNumber(product.quantity_per_case)}</td>
            <td><strong>${formatCurrency(product.price)}</strong></td>
            <td style="text-align: center;">${availableQty}</td>
            <td style="text-align: center;">${soldQty}</td>
            <td>
                <div class="action-buttons">
                    <button onclick="editProduct(${product.id})" class="btn-icon">Edit</button>
                    <button onclick="deleteProduct(${product.id})" class="btn-icon">Delete</button>
                </div>
            </td>
        </tr>
        `;
    })
    .join("");

  // Update order total after rendering
  updateOrderTotal();
}

// Toggle select all checkboxes
function toggleSelectAll() {
  const selectAllCheckbox = document.getElementById("select-all-checkbox");
  const productCheckboxes = document.querySelectorAll(".product-checkbox");

  productCheckboxes.forEach((checkbox) => {
    checkbox.checked = selectAllCheckbox.checked;
  });

  updateOrderTotal();
}

// Update order total based on checked products
function updateOrderTotal() {
  const productCheckboxes = document.querySelectorAll(".product-checkbox");
  let total = 0;
  let selectedCount = 0;

  productCheckboxes.forEach((checkbox) => {
    if (checkbox.checked) {
      const productId = parseInt(checkbox.dataset.productId);
      const product = filteredProducts.find((p) => p.id === productId);

      if (product) {
        const orderQty = product.quantity_sold_last_month || 0;
        const price = product.price || 0;
        total += orderQty * price;
        selectedCount++;
      }
    }
  });

  // Update display
  const orderTotalElement = document.getElementById("order-total");
  const selectedCountElement = document.getElementById("selected-count");

  if (orderTotalElement) {
    orderTotalElement.textContent = total.toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }

  if (selectedCountElement) {
    selectedCountElement.textContent = selectedCount;
  }

  // Update select all checkbox state
  const selectAllCheckbox = document.getElementById("select-all-checkbox");
  if (selectAllCheckbox && productCheckboxes.length > 0) {
    const allChecked = Array.from(productCheckboxes).every((cb) => cb.checked);
    const noneChecked = Array.from(productCheckboxes).every(
      (cb) => !cb.checked,
    );

    selectAllCheckbox.checked = allChecked;
    selectAllCheckbox.indeterminate = !allChecked && !noneChecked;
  }

  // Update Create Quotation button visibility
  updateCreateQuotationButton();

  // Update Export button visibility
  updateExportButton();
}

// Restore checkbox selections by product IDs
function restoreCheckboxSelections(selectedIds) {
  if (!selectedIds || selectedIds.length === 0) {
    return;
  }

  const selectedSet = new Set(selectedIds);
  const productCheckboxes = document.querySelectorAll(".product-checkbox");

  productCheckboxes.forEach((checkbox) => {
    const productId = parseInt(checkbox.dataset.productId);
    if (selectedSet.has(productId)) {
      checkbox.checked = true;
    }
  });

  updateOrderTotal();
}

// Open product modal
function openProductModal(productId = null) {
  const modal = document.getElementById("product-modal");
  const form = document.getElementById("product-form");
  const title = document.getElementById("modal-title");

  // Reset form
  form.reset();
  editingProductId = productId;

  if (productId) {
    // Edit mode
    title.textContent = "Edit Product";
    const product = currentProducts.find((p) => p.id === productId);
    if (product) {
      document.getElementById("product-id").value = product.id;
      document.getElementById("product-name").value = product.product_name;
      document.getElementById("product-barcode").value = product.upc_barcode;
      document.getElementById("product-threshold").value =
        product.threshold_quantity || "";
      document.getElementById("product-qty-case").value =
        product.quantity_per_case || "";
      document.getElementById("product-price").value = product.price || "";
    }
  } else {
    // Add mode
    title.textContent = "Add Product";
  }

  modal.classList.remove("hidden");
  modal.classList.add("flex");
}

// Close product modal
function closeProductModal() {
  const modal = document.getElementById("product-modal");
  modal.classList.remove("flex");
  modal.classList.add("hidden");
  editingProductId = null;
}

// Product form submit handler
document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("product-form");
  if (form) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();

      const productData = {
        product_name: document.getElementById("product-name").value,
        upc_barcode: document.getElementById("product-barcode").value,
        threshold_quantity:
          parseInt(document.getElementById("product-threshold").value) || null,
        quantity_per_case:
          parseInt(document.getElementById("product-qty-case").value) || null,
        price:
          parseFloat(document.getElementById("product-price").value) || null,
      };

      try {
        if (editingProductId) {
          // Update
          await apiRequest(`/api/products/${editingProductId}`, {
            method: "PUT",
            body: JSON.stringify(productData),
          });
          showToast("Product updated successfully", "success");
        } else {
          // Create
          await apiRequest("/api/products", {
            method: "POST",
            body: JSON.stringify(productData),
          });
          showToast("Product created successfully", "success");
        }

        closeProductModal();
        loadProducts();
      } catch (error) {
        showToast("Failed to save product: " + error.message, "error");
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
  if (!confirm("Are you sure you want to delete this product?")) {
    return;
  }

  try {
    await apiRequest(`/api/products/${productId}`, {
      method: "DELETE",
    });
    showToast("Product deleted successfully", "success");
    loadProducts();
  } catch (error) {
    showToast("Failed to delete product: " + error.message, "error");
  }
}

// Clear all products
async function clearAllProducts() {
  const productCount = currentProducts.length;

  if (productCount === 0) {
    showToast("No products to delete", "info");
    return;
  }

  if (
    !confirm(
      `Are you sure you want to delete ALL ${productCount} product(s)? This action cannot be undone!`,
    )
  ) {
    return;
  }

  // Double confirmation for safety
  if (
    !confirm(
      "This will permanently delete all products. Are you absolutely sure?",
    )
  ) {
    return;
  }

  try {
    const result = await apiRequest("/api/products/batch", {
      method: "DELETE",
    });
    showToast(`Successfully deleted ${result.count} product(s)`, "success");
    loadProducts();
  } catch (error) {
    showToast("Failed to delete products: " + error.message, "error");
  }
}

// Find missing products
function findMissingProducts() {
  const modal = document.getElementById("missing-products-modal");
  const loading = document.getElementById("missing-products-loading");
  const content = document.getElementById("missing-products-content");
  const error = document.getElementById("missing-products-error");
  const statusText = document.getElementById("missing-products-status");
  const list = document.getElementById("missing-products-list");

  // Show modal with loading state
  modal.classList.remove("hidden");
  modal.classList.add("flex");
  loading.classList.remove("hidden");
  loading.style.display = "flex"; // Override inline style
  content.classList.add("hidden");
  content.style.display = "none"; // Override inline style
  error.classList.add("hidden");
  error.style.display = "none"; // Override inline style

  // Reset state
  list.innerHTML = "";
  statusText.textContent = "Connecting to Shopify...";

  const missingProducts = [];
  let productIndex = 0;

  // Start SSE connection
  const eventSource = new EventSource("/api/products/missing");

  eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);

    if (data.type === "start") {
      statusText.textContent = data.message;
    } else if (data.type === "progress") {
      statusText.textContent = `Page ${data.page}: Processed ${data.items_processed} items, found ${data.missing_count} missing products`;
    } else if (data.type === "product_found") {
      // Add product to the list in real-time
      const product = data.product;
      missingProducts.push(product);

      // Show content section if this is the first product
      if (missingProducts.length === 1) {
        loading.classList.add("hidden");
        loading.style.display = "none"; // Override inline style
        content.classList.remove("hidden");
        content.style.display = "flex"; // Override inline style
      }

      // Update count
      document.getElementById("missing-products-count").textContent =
        missingProducts.length;

      // Add product to list
      const productEl = document.createElement("div");
      productEl.style.cssText =
        "display: flex; align-items: flex-start; padding: 0.75rem; border: 1px solid var(--border-color); border-radius: 0.5rem; transition: all 0.2s ease;";
      productEl.onmouseover = function () {
        this.style.background = "var(--bg-tertiary)";
      };
      productEl.onmouseout = function () {
        this.style.background = "transparent";
      };
      productEl.innerHTML = `
        <input type="checkbox"
               class="checkbox missing-product-checkbox"
               style="margin-top: 0.25rem; margin-right: 0.75rem;"
               data-index="${productIndex}"
               data-sku="${product.sku}"
               data-title="${product.product_title}"
               data-variant="${product.variant_title}"
               data-barcode="${product.barcode || ""}"
               onchange="updateSelectedCount()">
        <div style="flex: 1;">
            <p style="font-weight: 500; color: var(--text-primary);">${product.product_title}</p>
            ${product.variant_title ? `<p style="font-size: 0.875rem; color: var(--text-secondary);">Variant: ${product.variant_title}</p>` : ""}
            <div style="display: flex; gap: 1rem; font-size: 0.75rem; color: var(--text-tertiary); margin-top: 0.25rem;">
                <span>SKU: ${product.sku}</span>
                ${product.barcode ? `<span>Barcode: ${product.barcode}</span>` : ""}
                <span style="color: var(--accent-primary); font-weight: 500;">Available: ${product.available_quantity}</span>
            </div>
        </div>
      `;
      list.appendChild(productEl);
      productIndex++;

      // Scroll to bottom to show new product
      list.scrollTop = list.scrollHeight;
    } else if (data.type === "complete") {
      eventSource.close();

      // Always hide loading and show content when complete
      loading.classList.add("hidden");
      loading.style.display = "none"; // Override inline style
      content.classList.remove("hidden");
      content.style.display = "flex"; // Override inline style

      // Update final count
      document.getElementById("missing-products-count").textContent =
        data.count;

      if (data.count === 0) {
        list.innerHTML =
          '<p style="text-align: center; color: var(--text-tertiary); padding: 2rem 0;">No missing products found. All Shopify products are in your local database.</p>';
      }

      // Reset select all checkbox
      document.getElementById("select-all-missing").checked = false;
      updateSelectedCount();

      showToast(
        `Found ${data.count} missing product(s) (processed ${data.total_items_processed} items)`,
        data.count > 0 ? "success" : "info",
      );
    } else if (data.type === "error") {
      eventSource.close();
      loading.classList.add("hidden");
      loading.style.display = "none"; // Override inline style
      error.classList.remove("hidden");
      error.style.display = "block"; // Override inline style
      error.querySelector("p").textContent = data.message;
      showToast("Error: " + data.message, "error");
    }
  };

  eventSource.onerror = (err) => {
    console.error("EventSource error:", err);
    eventSource.close();
    loading.classList.add("hidden");
    loading.style.display = "none"; // Override inline style
    error.classList.remove("hidden");
    error.style.display = "block"; // Override inline style
    error.querySelector("p").textContent =
      "Connection error. Please check your network and try again.";
    showToast("Connection error while finding missing products", "error");
  };
}

// Close missing products modal
function closeMissingProductsModal() {
  const modal = document.getElementById("missing-products-modal");
  modal.classList.remove("flex");
  modal.classList.add("hidden");
}

// Toggle select all missing products
function toggleSelectAllMissing() {
  const selectAll = document.getElementById("select-all-missing");
  const checkboxes = document.querySelectorAll(".missing-product-checkbox");

  checkboxes.forEach((checkbox) => {
    checkbox.checked = selectAll.checked;
  });

  updateSelectedCount();
}

// Update selected count
function updateSelectedCount() {
  const checkboxes = document.querySelectorAll(
    ".missing-product-checkbox:checked",
  );
  document.getElementById("selected-count").textContent = checkboxes.length;
}

// Add selected products to database
async function addSelectedProducts() {
  const checkboxes = document.querySelectorAll(
    ".missing-product-checkbox:checked",
  );

  if (checkboxes.length === 0) {
    showToast("Please select at least one product to add", "info");
    return;
  }

  const productsToAdd = [];
  checkboxes.forEach((checkbox) => {
    const title = checkbox.dataset.title;
    const variantTitle = checkbox.dataset.variant;
    const productName = variantTitle ? `${title} - ${variantTitle}` : title;

    productsToAdd.push({
      product_name: productName,
      upc_barcode: checkbox.dataset.sku,
      threshold_quantity: null,
      quantity_per_case: null,
      price: null,
    });
  });

  try {
    let addedCount = 0;
    let errorCount = 0;

    // Add each product one by one
    for (const product of productsToAdd) {
      try {
        await apiRequest("/api/products", {
          method: "POST",
          body: JSON.stringify(product),
        });
        addedCount++;
      } catch (error) {
        console.error(`Error adding product ${product.product_name}:`, error);
        errorCount++;
      }
    }

    // Show results
    if (addedCount > 0) {
      showToast(`Successfully added ${addedCount} product(s)`, "success");
      closeMissingProductsModal();
      loadProducts();
    }

    if (errorCount > 0) {
      showToast(`Failed to add ${errorCount} product(s)`, "error");
    }
  } catch (error) {
    showToast("Failed to add products: " + error.message, "error");
  }
}

// ===== Quotation Functions =====

let selectedCustomerId = null;
let customerSearchTimeout = null;

// Update Create Quotation button visibility based on checkbox selections
function updateCreateQuotationButton() {
  const checkedBoxes = document.querySelectorAll(".product-checkbox:checked");
  const btn = document.getElementById("create-quotation-btn");

  if (checkedBoxes.length > 0) {
    btn.style.display = "inline-flex";
  } else {
    btn.style.display = "none";
  }
}

// Open quotation modal with selected products
async function openQuotationModal() {
  const checkedBoxes = document.querySelectorAll(".product-checkbox:checked");

  if (checkedBoxes.length === 0) {
    showToast("Please select at least one product", "info");
    return;
  }

  // Get selected products data
  const selectedProducts = [];
  checkedBoxes.forEach((checkbox) => {
    const productId = parseInt(checkbox.dataset.productId);
    const product = currentProducts.find((p) => p.id === productId);

    if (product) {
      const orderQty =
        product.quantity_sold_last_month !== null &&
        product.quantity_sold_last_month !== undefined
          ? product.quantity_sold_last_month
          : 0;
      const price = product.price || 0;

      selectedProducts.push({
        id: product.id,
        product_name: product.product_name,
        upc_barcode: product.upc_barcode,
        price: price,
        order_qty: orderQty,
      });
    }
  });

  if (selectedProducts.length === 0) {
    showToast("No valid products selected", "error");
    return;
  }

  // Preview products in modal
  previewQuotationProducts(selectedProducts);

  // Show modal
  const modal = document.getElementById("quotation-modal");
  modal.classList.remove("hidden");
  modal.classList.add("flex");
  modal.style.display = "flex";

  // Setup customer search listener
  setupCustomerSearch();
}

// Close quotation modal and reset form
function closeQuotationModal() {
  const modal = document.getElementById("quotation-modal");
  modal.classList.remove("flex");
  modal.classList.add("hidden");
  modal.style.display = "none";

  // Reset form
  document.getElementById("quotation-customer-search").value = "";
  document.getElementById("quotation-title").value = "";
  document.getElementById("quotation-po-number").value = "";
  document.getElementById("quotation-notes").value = "";
  document.getElementById("quotation-customer-results").style.display = "none";
  document.getElementById("quotation-customer-results").innerHTML = "";

  // Clear selected customer
  selectedCustomerId = null;
  document.getElementById("quotation-selected-customer").style.display = "none";
}

// Setup customer search with debouncing
function setupCustomerSearch() {
  const searchInput = document.getElementById("quotation-customer-search");

  // Remove previous listener
  const newSearchInput = searchInput.cloneNode(true);
  searchInput.parentNode.replaceChild(newSearchInput, searchInput);

  // Add new listener
  newSearchInput.addEventListener("input", (e) => {
    const query = e.target.value.trim();

    // Clear previous timeout
    if (customerSearchTimeout) {
      clearTimeout(customerSearchTimeout);
    }

    if (query.length < 2) {
      document.getElementById("quotation-customer-results").style.display =
        "none";
      document.getElementById("quotation-customer-results").innerHTML = "";
      return;
    }

    // Debounce search
    customerSearchTimeout = setTimeout(() => {
      searchCustomers(query);
    }, 300);
  });
}

// Search customers by account number
async function searchCustomers(query) {
  try {
    const results = await apiRequest(
      `/api/quotations/customers/search?q=${encodeURIComponent(query)}`,
    );

    const resultsContainer = document.getElementById(
      "quotation-customer-results",
    );

    if (!results || results.length === 0) {
      resultsContainer.innerHTML = `
        <div style="padding: 1rem; text-align: center; color: var(--text-secondary);">
          No customers found
        </div>
      `;
      resultsContainer.style.display = "block";
      return;
    }

    resultsContainer.innerHTML = results
      .map(
        (customer) => `
        <div
          onclick="selectCustomer(${customer.CustomerID}, '${customer.BusinessName}', '${customer.AccountNo}')"
          style="padding: 0.75rem; cursor: pointer; border-bottom: 1px solid var(--border-color);"
          onmouseover="this.style.background='var(--bg-primary)'"
          onmouseout="this.style.background='transparent'"
        >
          <p style="margin: 0; font-weight: 600; color: var(--text-primary);">${customer.BusinessName || "N/A"}</p>
          <p style="margin: 0.25rem 0 0 0; font-size: 0.875rem; color: var(--text-secondary);">
            Account: ${customer.AccountNo || "N/A"}
          </p>
        </div>
      `,
      )
      .join("");

    resultsContainer.style.display = "block";
  } catch (error) {
    showToast("Failed to search customers: " + error.message, "error");
  }
}

// Select a customer from search results
function selectCustomer(customerId, businessName, accountNo) {
  selectedCustomerId = customerId;

  // Update UI
  document.getElementById("quotation-customer-name").textContent =
    businessName || "N/A";
  document.getElementById("quotation-customer-account").textContent =
    `Account: ${accountNo || "N/A"}`;

  document.getElementById("quotation-selected-customer").style.display =
    "block";
  document.getElementById("quotation-customer-search").value = "";
  document.getElementById("quotation-customer-results").style.display = "none";
  document.getElementById("quotation-customer-results").innerHTML = "";
}

// Clear selected customer
function clearSelectedCustomer() {
  selectedCustomerId = null;
  document.getElementById("quotation-selected-customer").style.display = "none";
  document.getElementById("quotation-customer-search").value = "";
}

// Preview selected products in quotation modal
function previewQuotationProducts(products) {
  const tbody = document.getElementById("quotation-products-preview");
  let total = 0;

  tbody.innerHTML = products
    .map((product) => {
      const qty = product.order_qty || 0;
      const price = product.price || 0;
      const lineTotal = qty * price;
      total += lineTotal;

      return `
      <tr style="border-bottom: 1px solid var(--border-color);">
        <td style="padding: 0.75rem; color: var(--text-primary);">${product.product_name}</td>
        <td style="padding: 0.75rem; color: var(--text-secondary); font-family: 'Courier New', monospace;">${product.upc_barcode}</td>
        <td style="padding: 0.75rem; text-align: right; color: var(--text-primary);">${qty}</td>
        <td style="padding: 0.75rem; text-align: right; color: var(--text-primary);">$${price.toFixed(2)}</td>
        <td style="padding: 0.75rem; text-align: right; font-weight: 600; color: var(--accent-primary);">$${lineTotal.toFixed(2)}</td>
      </tr>
    `;
    })
    .join("");

  // Update quotation total
  document.getElementById("quotation-total-display").textContent =
    `$${total.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

// Submit quotation creation
async function submitQuotation() {
  try {
    // Validate customer selection
    if (!selectedCustomerId) {
      showToast("Please select a customer", "error");
      return;
    }

    // Get selected products
    const checkedBoxes = document.querySelectorAll(".product-checkbox:checked");
    const selectedProducts = [];

    checkedBoxes.forEach((checkbox) => {
      const productId = parseInt(checkbox.dataset.productId);
      const product = currentProducts.find((p) => p.id === productId);

      if (product) {
        const orderQty =
          product.quantity_sold_last_month !== null &&
          product.quantity_sold_last_month !== undefined
            ? product.quantity_sold_last_month
            : 0;
        const price = product.price || 0;

        selectedProducts.push({
          id: product.id,
          product_name: product.product_name,
          upc_barcode: product.upc_barcode,
          price: price,
          order_qty: orderQty,
        });
      }
    });

    if (selectedProducts.length === 0) {
      showToast("No valid products selected", "error");
      return;
    }

    // Get form values
    const quotationTitle = document
      .getElementById("quotation-title")
      .value.trim();
    const poNumber = document
      .getElementById("quotation-po-number")
      .value.trim();
    const notes = document.getElementById("quotation-notes").value.trim();

    // Disable submit button
    const submitBtn = document.getElementById("quotation-submit-btn");
    submitBtn.disabled = true;
    submitBtn.innerHTML =
      '<i class="fas fa-spinner fa-spin" style="margin-right: 0.5rem;"></i>Creating...';

    // Send request
    const response = await apiRequest("/api/quotations/create", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        customer_id: selectedCustomerId,
        quotation_title: quotationTitle,
        po_number: poNumber,
        notes: notes,
        products: selectedProducts,
      }),
    });

    // Success
    let message = `Quotation #${response.quotation_number} created successfully`;

    if (response.skipped_products && response.skipped_products.length > 0) {
      message += ` (${response.skipped_products.length} product(s) skipped)`;
      console.warn("Skipped products:", response.skipped_products);
    }

    showToast(message, "success");

    // Clear selections
    const selectAllCheckbox = document.getElementById("select-all-checkbox");
    if (selectAllCheckbox) {
      selectAllCheckbox.checked = false;
    }

    checkedBoxes.forEach((checkbox) => {
      checkbox.checked = false;
    });

    updateOrderTotal();
    updateCreateQuotationButton();

    // Close modal
    closeQuotationModal();
  } catch (error) {
    showToast("Failed to create quotation: " + error.message, "error");
  } finally {
    // Re-enable submit button
    const submitBtn = document.getElementById("quotation-submit-btn");
    submitBtn.disabled = false;
    submitBtn.innerHTML =
      '<i class="fas fa-check" style="margin-right: 0.5rem;"></i>Create Quotation';
  }
}

// Update Export button visibility based on checkbox selections
function updateExportButton() {
  const checkedBoxes = document.querySelectorAll(".product-checkbox:checked");
  const btn = document.getElementById("export-selected-btn");

  if (checkedBoxes.length > 0) {
    btn.style.display = "inline-flex";
  } else {
    btn.style.display = "none";
  }
}

// Export selected products to Excel
async function exportSelectedProducts() {
  const checkedBoxes = document.querySelectorAll(".product-checkbox:checked");

  if (checkedBoxes.length === 0) {
    showToast("Please select at least one product", "info");
    return;
  }

  // Collect product IDs
  const productIds = [];
  checkedBoxes.forEach((checkbox) => {
    productIds.push(parseInt(checkbox.dataset.productId));
  });

  try {
    showToast("Preparing export...", "info");

    const response = await fetch("/api/products/export", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ product_ids: productIds }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || "Export failed");
    }

    // Get the blob from response
    const blob = await response.blob();

    // Extract filename from Content-Disposition header or use default
    const contentDisposition = response.headers.get("Content-Disposition");
    let filename = "products_export.xlsx";
    if (contentDisposition) {
      const filenameMatch = contentDisposition.match(/filename="?(.+)"?/i);
      if (filenameMatch) {
        filename = filenameMatch[1];
      }
    }

    // Create download link
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();

    // Cleanup
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);

    showToast(
      `Exported ${productIds.length} product(s) to ${filename}`,
      "success",
    );
  } catch (error) {
    showToast("Failed to export products: " + error.message, "error");
  }
}
