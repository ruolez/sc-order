# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture Overview

This is a Docker-based inventory management application that integrates Shopify and MS SQL Server. The system uses a **microservices architecture** with three separate containers communicating via a bridge network:

### Container Architecture

1. **nginx** (Reverse Proxy): Port 5001 → routes to frontend/backend
   - `/` → frontend container (static files)
   - `/api/*` → backend container (Flask API)
   - `/health` → health check endpoint

2. **frontend** (Nginx Static Server): Serves HTML/CSS/JS
   - Single-page application (SPA) architecture
   - No framework - vanilla JavaScript (Tailwind CSS used only for modal utilities)
   - Dark theme with CSS variables for easy customization
   - All static files in `/frontend/static/` and `/frontend/templates/`

3. **backend** (Flask API): Python REST API
   - SQLite database with auto-migrations on startup
   - Integrates with Shopify GraphQL API (2025-01)
   - Integrates with MS SQL Server via FreeTDS (TDS 7.2 for SQL 2008/2012 compatibility)
   - Server-Sent Events (SSE) for real-time sync progress

4. **data** (Volume): Persistent SQLite database at `./data/inventory.db`

### Key Integration Points

**Product Matching Strategy**: All systems use UPC barcode as the primary key:
- Internal SQLite: `products.upc_barcode`
- Shopify: `variant.sku` (configured to match UPC)
- MS SQL: `Items_tbl.ProductUPC`

**External MS SQL Schema**: The application connects to a legacy MS SQL database with these key tables:
- `Items_tbl`: Product master data (ProductID, ProductUPC, ProductDescription, UnitPriceC for price sync, UnitID foreign key)
- `Units_tbl`: Unit of measure descriptions (UnitID, UnitDesc) - joined with Items_tbl for quotation line items
- `Customers_tbl`: Customer information (CustomerID, BusinessName, AccountNo, shipping addresses, sales rep, terms)
- `Quotations_tbl`: Quotation headers (QuotationID, QuotationNumber, customer details, totals, dates)
- `QuotationsDetails_tbl`: Quotation line items (LineID, QuotationID, product details, quantities, prices)

## Development Commands

### Building and Running

```bash
# Build all containers from scratch
docker-compose build --no-cache

# Start all services
docker-compose up -d

# Rebuild and restart a specific container
docker-compose build --no-cache backend
docker-compose up -d backend

# Rebuild frontend only (most common during UI development)
docker-compose build --no-cache frontend && docker-compose up -d frontend
```

### Code Formatting

```bash
# Format JavaScript files with prettier
npx prettier --write frontend/static/js/products.js

# Check formatting without modifying
npx prettier --check frontend/static/js/*.js
```

### Monitoring

```bash
# View container status and health
docker-compose ps

# View logs
docker-compose logs -f              # All containers
docker-compose logs -f backend      # Backend only
docker-compose logs -f frontend     # Frontend only
docker-compose logs -f nginx        # Nginx only
```

### Database Operations

```bash
# Access database directly
docker-compose exec backend python database.py

# View database file
docker-compose exec backend sqlite3 /app/data/inventory.db

# Reset database (WARNING: deletes all data)
docker-compose down -v
docker-compose up -d
```

### Troubleshooting

```bash
# Full rebuild from clean state
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# Access backend shell
docker-compose exec backend sh

# Test API endpoint
curl http://localhost:5001/api/products
```

## Code Organization

### Backend (`/backend/`)

**Core Files**:
- `app.py`: Flask application with all API endpoints
  - Product CRUD: `/api/products`, `/api/products/<id>`
  - Bulk operations: `/api/products/batch` (DELETE), `/api/products/import` (POST), `/api/products/clear-column` (POST)
  - Shopify: `/api/shopify/test`, `/api/shopify/locations`, `/api/shopify/inventory`
  - MS SQL: `/api/mssql/test`
  - Sync inventory: `/api/products/sync` (GET - returns SSE stream for Shopify stock sync)
  - Sync price: `/api/products/sync-price` (GET - returns SSE stream for MS SQL price sync)
  - Sync sales: `/api/products/sync-sales?product_ids=1,2,3` (GET - returns SSE stream for Shopify sales data sync)
  - Missing products: `/api/products/missing` (GET - returns SSE stream for finding products in Shopify not in local DB)
  - Clear column: `/api/products/clear-column` (POST - sets specific column to NULL for all products, whitelist protected)
  - Quotations: `/api/quotations/customers/search?q=<query>` (GET - customer autocomplete), `/api/quotations/customers/<id>` (GET - customer details), `/api/quotations/create` (POST - create quotation with line items)
  - Reports: `/api/reports/sc-sales?from_date=YYYY-MM-DD&to_date=YYYY-MM-DD` (GET - SC sales report), `/api/reports/sc-sales/export` (POST - Excel export with formatted summary)

- `database.py`: SQLite operations with automatic schema migrations
  - `init_database()`: Creates tables and runs migrations on startup
  - Migration pattern: Check `PRAGMA table_info()` → `ALTER TABLE` if column missing
  - All functions return dicts (using `sqlite3.Row`)
  - `update_product_available_quantity()`: Updates stock from Shopify sync
  - `update_product_price()`: Updates price from MS SQL sync
  - `update_product_sales_last_month()`: Updates order quantity from Shopify sales sync
  - `clear_column_data()`: Clears (sets to NULL) specific column for all products with whitelist validation

- `shopify_api.py`: Shopify GraphQL API wrapper (ShopifyAPI class)
  - Uses Admin API 2025-01
  - All queries use GraphQL (not REST)
  - Cursor-based pagination for large result sets

- `mssql_connector.py`: MS SQL connector (MSSQLConnector class)
  - Uses FreeTDS driver for compatibility with SQL Server 2008/2012
  - TDS version 7.2 explicitly set
  - Connection pooling not implemented (single connection per request)
  - `get_price_by_upc()`: Queries `Items_tbl.UnitPriceC` by `ProductUPC` for price sync
  - `search_customers()`, `get_customer_by_id()`: Customer lookup for quotations
  - `get_next_quotation_number()`: Auto-increment quotation numbers
  - `get_item_details_by_upc()`, `get_bulk_item_details_by_upcs()`: Product details with Units_tbl JOIN for UnitDesc
  - `insert_quotation()`, `insert_quotation_details()`: Create quotations with line items

### Frontend (`/frontend/`)

**JavaScript Modules** (all in `/frontend/static/js/`):
- `app.js`: Main application, navigation, toast notifications
- `products.js`: Product table, CRUD, sorting, filtering, sync operations
  - `loadProducts()`: Fetches products and preserves search filters, order filters, sort state, and checkbox selections across reloads
  - Client-side sorting with `sortProducts(column)` function - supports all columns including Order (quantity_sold_last_month)
  - `syncInventory()`: SSE client for Shopify stock sync with real-time progress
  - `syncPrice()`: SSE client for MS SQL price sync with real-time progress
  - `syncSales()`: SSE client for Shopify sales sync with real-time progress (only syncs filtered/visible products)
  - `findMissingProducts()`: SSE client for finding products in Shopify not in local DB - streams results in real-time as they're found
  - `addSelectedProducts()`: Adds selected missing products to local database
  - `toggleOrderFilter()`: Filters products that need reordering (available_quantity <= threshold_quantity)
  - `toggleSelectAll()`: Selects/deselects all visible product checkboxes
  - `updateOrderTotal()`: Calculates total order value from checked products (Order Qty × Price) with comma thousands separator
  - `updateLowStockCount()`: Updates low stock counter based on available_quantity <= threshold_quantity
  - `restoreCheckboxSelections()`: Helper to restore selected products after reload
  - `updateSortIcons()`: Helper to update sort column visual indicators
- `reports.js`: SC Sales report functionality
  - `formatCurrency()`: Helper function for currency formatting with comma thousands separators using `toLocaleString('en-US')`
  - `loadSCScalesReport()`: Fetches sales report data for selected date range
  - `renderReportTable()`: Renders product sales table with formatted currency
  - `sortReportTable(column)`: Client-side table sorting with ascending/descending toggle
  - `exportReport()`: Downloads Excel file with formatted sales data and summary
  - `setLast7Days()`, `setLast30Days()`, `setThisMonth()`: Date range shortcuts
- `settings.js`: Settings form management, API connections, data management operations
  - `clearColumnData()`: Clears specific column data for all products (threshold, case, price, stock, order)
- `import.js`: Excel file upload and import

**Important UI Patterns**:
- All API calls use `apiRequest()` helper (handles auth, errors)
- Toast notifications: `showToast(message, type)` where type is 'success', 'error', 'info', 'warning'
- Server-Sent Events for long-running operations (sync)
- No state management library - uses global variables and DOM manipulation
- Real-time order total calculation: Checkboxes on each product row allow selection, total displays `Sum(OrderQty × Price)` for all checked products
- Select All checkbox supports indeterminate state when some (but not all) products are selected
- **State Persistence**: Search filters, order filters, sort state, and checkbox selections are preserved when `loadProducts()` is called after any operation (edit, delete, sync)

**Dark Theme Implementation**:
- CSS variables defined in `:root` in `/frontend/static/css/styles.css`:
  - `--bg-primary`, `--bg-secondary`, `--bg-tertiary` (backgrounds)
  - `--text-primary`, `--text-secondary`, `--text-tertiary` (text colors)
  - `--accent-primary` (green), `--accent-secondary` (blue), `--accent-danger` (red)
  - `--border-color` (borders and dividers)
- Modals use `.modal-content` class with dark theme styling
- Dynamically generated content (table rows, modal lists) uses inline styles with CSS variables
- Avoid Tailwind utility classes for dynamic content - use CSS variables and inline styles instead

**Settings Page Organization**:
- **Shopify Integration**: Single unified card with main store (bordered) and collapsible additional stores section (stores 2-6)
- **MS SQL Integration**: Separate card with server/port/database/credentials in 2-column grid layout
- **Sales Sync Configuration**: Separate card for configuring:
  - Sales Order Tag: Tag used in tag-based filtering
  - Sales Sync Period: Number of days to look back (1-365, default 30)
- **Data Management**: Danger zone card with red border containing delete and clear operations
- **Save Button**: Sticky at bottom with prominent styling

### Database Schema

**Settings Table** (singleton - always ID=1):
```sql
- shopify_store_url, shopify_access_token, shopify_location_id (Main store)
- shopify_store_2_url, shopify_store_2_token, shopify_store_2_location_id
- shopify_store_3_url, shopify_store_3_token, shopify_store_3_location_id
- shopify_store_4_url, shopify_store_4_token, shopify_store_4_location_id
- shopify_store_5_url, shopify_store_5_token, shopify_store_5_location_id
- shopify_store_6_url, shopify_store_6_token, shopify_store_6_location_id
- excluded_skus (TEXT - comma or newline separated SKU prefixes)
- sales_order_tag (TEXT - required for sales sync, filters orders by tag)
- sales_sync_days (INTEGER - days to look back for sales sync, default 30)
- mssql_server, mssql_database, mssql_username, mssql_password, mssql_port
```

**Note**: The application supports up to 6 Shopify stores for sales aggregation.

**Products Table**:
```sql
- id (PRIMARY KEY AUTOINCREMENT)
- product_name (TEXT NOT NULL)
- upc_barcode (TEXT UNIQUE NOT NULL)
- threshold_quantity, quantity_per_case, price
- available_quantity (synced from Shopify)
- quantity_sold_last_month (synced from Shopify orders)
- created_at, updated_at (TIMESTAMP)
```

## Important Implementation Details

### Quotation Creation Feature

The application includes functionality to create quotations in the MS SQL database from selected products:

**Workflow**:
1. User selects products using checkboxes in the product list
2. "Create Quotation" button appears when products are selected
3. Clicking the button opens a modal with:
   - Customer search (autocomplete with 300ms debouncing)
   - Optional fields: Quotation Title, PO Number, Notes
   - Product preview table showing selected items
4. On submission, creates records in both `Quotations_tbl` and `QuotationsDetails_tbl`

**Key API Endpoints** (`backend/app.py`):
- `GET /api/quotations/customers/search?q=<query>`: Customer autocomplete search
- `GET /api/quotations/customers/<id>`: Get customer details by ID
- `POST /api/quotations/create`: Create quotation with line items

**MS SQL Connector Methods** (`backend/mssql_connector.py`):
- `search_customers(query, limit)`: Search customers by business name or account number
- `get_customer_by_id(customer_id)`: Retrieve full customer record
- `get_next_quotation_number()`: Auto-increment quotation number
- `get_item_details_by_upc(upc)`: Fetch product details with JOIN to Units_tbl for UnitDesc
- `get_bulk_item_details_by_upcs(upcs)`: Batch fetch product details (performance optimization)
- `insert_quotation(quotation_data)`: Insert quotation header, returns QuotationID
- `insert_quotation_details(quotation_id, line_items)`: Insert line items for quotation

**Data Population Rules**:
- **Quotation Number**: Auto-generated by incrementing last number by 1
- **Quotation Date**: Current timestamp
- **Expiration Date**: 10 years from creation date (`QuotationDate + timedelta(days=3650)`)
- **Customer Data**: Populated from `Customers_tbl` (business name, addresses, contact info)
- **Line Item Calculations**: `ExtendedPrice = Qty × UnitPrice`, `ExtendedCost = Qty × UnitCost`
- **Product Details**: Retrieved from `Items_tbl` with LEFT JOIN to `Units_tbl` for UnitDesc
- **Status**: Always set to 0 (pending/draft status)
- **Tax**: TotalTaxes = 0.0 (not calculated)

**Field Value Conventions** (QuotationsDetails_tbl):
- Empty strings: `QuotationTitle`, `PoNumber`, `AutoOrderNo`, `Header`, `Footer`, `Notes`, `Memo`, `LineMessage`
- Zero values: `ReasonID`, `RememberPrice`, `PromotionID`, `PromotionLine`, `Taxable`, `Catch`, `Flag`
- NULL values: `UnitDesc` (from Units_tbl join), `PromotionDescription`, `PromotionAmount`, `Comments`

**Frontend Implementation** (`frontend/static/js/products.js`):
- `openQuotationModal()`: Opens quotation creation modal
- `setupCustomerSearch()`: Configures autocomplete with debouncing
- `searchCustomers(query)`: Fetches customer matches from API
- `selectCustomer(id, name, account)`: Populates selected customer
- `previewQuotationProducts(products)`: Displays selected products in modal
- `submitQuotation()`: Validates and submits quotation data
- State management: Checkbox selections cleared after successful quotation creation

### SC Sales Reports Feature

The application includes a comprehensive sales reporting system that aggregates sales data across all configured Shopify stores:

**Workflow**:
1. User navigates to Reports section and selects date range (or uses quick presets: Last 7 Days, Last 30 Days, This Month)
2. "Load Report" fetches sales data from all configured Shopify stores in parallel
3. Report displays products with sales during the period, sorted by quantity sold (descending)
4. User can sort by any column (Product Name, UPC, Quantity Sold, Price, Estimated Total, etc.)
5. "Export to Excel" generates formatted Excel file with summary and detailed data

**Key Features**:
- **Multi-Store Aggregation**: Combines sales data from up to 6 Shopify stores
- **Tag-Based Filtering**: Uses `sales_order_tag` setting to filter relevant orders
- **Currency Formatting**: All dollar amounts display with comma thousands separators (e.g., $12,345.67)
- **Total Sales Value**: Automatically calculates sum of all estimated totals (Quantity × Price)
- **Real-Time Progress**: Shows store processing status and handles failures gracefully
- **Excel Export**: Generates formatted .xlsx file with summary sheet and detailed product data

**Key API Endpoints** (`backend/app.py`):
- `GET /api/reports/sc-sales?from_date=YYYY-MM-DD&to_date=YYYY-MM-DD`: Generate sales report
  - Fetches orders from all configured stores in parallel using ThreadPoolExecutor
  - Aggregates sales by SKU across all stores
  - Calculates estimated totals (quantity × price)
  - Returns products with sales only (excludes zero-sale items)
  - Includes summary: total_products, products_with_sales, total_items_sold, total_sales_value
  - Includes stores_info: stores_processed, stores_failed (with error details), tag_used
- `POST /api/reports/sc-sales/export`: Export report to Excel
  - Generates .xlsx file using pandas and openpyxl
  - Summary sheet with formatted metrics including Total Sales Value
  - Detailed sheet with all product sales data
  - Currency values formatted with comma separators (e.g., "$12,345.67")

**Currency Formatting Pattern** (`frontend/static/js/reports.js`):
```javascript
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
```

**Report Summary Display**:
- Total Products: Count of products with sales in the period
- Products with Sales: Same as total products (only products with sales are shown)
- Total Items Sold: Sum of all quantities sold
- **Total Sales Value**: Sum of all estimated totals (Quantity × Price) with formatted currency
- Stores Processed: Number of stores successfully queried
- Date Range: Selected from/to dates with number of days
- Tag Used: Tag used for order filtering

**Failed Stores Handling**:
- If any store fails to respond, the report continues with available data
- Failed stores are displayed in a warning section with error details
- Each failed store shows: store URL and specific error message
- User can still generate report from successfully processed stores

**Frontend Implementation** (`frontend/static/js/reports.js`):
- `formatCurrency(amount)`: Formats numbers as currency with comma separators
- `loadSCScalesReport()`: Fetches report data and updates UI with formatted values
- `renderReportTable(products)`: Renders table rows with formatted currency columns
- `sortReportTable(column)`: Client-side sorting with direction toggle
- `exportReport()`: Downloads Excel file via POST request with blob handling
- `setLast7Days()`, `setLast30Days()`, `setThisMonth()`: Date range shortcuts

**Excel Export Format**:
- **Summary Sheet**: Metrics table with formatted values
  - Report Period, From Date, To Date, Number of Days
  - Total Products, Products with Sales, Total Items Sold
  - **Total Sales Value** (formatted as "$XXX,XXX.XX")
  - Stores Processed, Tag Used
- **Detailed Sheet**: Product-level data with columns:
  - Product Name, UPC Barcode, Quantity Sold, Price, **Estimated Total**, Quantity per Case, Available Quantity
  - All currency columns formatted with 2 decimal places

**Important Notes**:
- Only products with sales > 0 are included in the report
- Products are sorted by quantity sold (descending) by default
- Currency formatting is consistent across UI and Excel export
- Report data matches exactly what's shown in the UI table

### Excluded SKUs Feature
- Supports prefix matching (not exact matching)
- SKUs starting with any excluded prefix are filtered out
- Used in "Find Missing Products" feature
- Parsed from comma or newline-separated text input

### Sync Operations

**Inventory Sync (Shopify Stock - Optimized with Batch Queries)**:
1. User clicks "Sync Inventory" button
2. Frontend opens EventSource to `/api/products/sync`
3. Backend uses **batch OR queries** to fetch multiple products in single API call:
   - Products split into batches of 50 SKUs
   - Query format: `"sku:ABC OR sku:DEF OR sku:GHI..."`
   - Single GraphQL request fetches up to 50 products simultaneously
   - **Performance**: 50-100x faster than sequential queries
4. Updates `products.available_quantity` field via `bulk_update_inventory()`
5. Streams progress via SSE: `{type: 'start'|'progress'|'complete'|'error'}`
   - Progress tracked per product (not per batch) for smooth UI updates
   - Frontend receives same event structure as before (no changes required)
6. Frontend shows real-time progress and "not found" products

**Key Implementation**:
- `shopify_api.py`: `get_bulk_variant_inventory_by_skus(skus, location_id)` returns `{sku: quantity}` dict
- `database.py`: `bulk_update_inventory(updates)` performs batch database updates
- `app.py`: `/api/products/sync` processes in batches but reports progress per product

**Price Sync (MS SQL)**:
1. User clicks "Sync Price" button
2. Frontend opens EventSource to `/api/products/sync-price`
3. Backend queries `Items_tbl.UnitPriceC` for each product by `ProductUPC`
4. Updates `products.price` field
5. Streams progress via SSE with same format as inventory sync
6. Frontend shows real-time progress and "not found" products

**Sales Sync (Shopify Orders - Multi-Store Aggregation with Tag-Based Batch Queries)**:
1. User clicks "Sync Sales" button (syncs only filtered/visible products on screen)
2. Frontend sends visible product IDs via query parameter: `/api/products/sync-sales?product_ids=1,2,3`
3. Backend uses **tag-based batch queries** for optimal performance:
   - Products split into batches of 50 SKUs
   - Query format: `"created_at:>=DATE AND tag:TAG AND (sku:A OR sku:B OR ...)"`
   - Shopify does server-side filtering by tag + SKU (no need for location filtering)
   - **Performance**: 4-10x faster than fetching all orders and filtering in Python
4. For each batch, fetches orders from **all configured stores** in parallel using ThreadPoolExecutor
5. **Linear progress tracking (0-100%)**:
   - Progress reported per product processed (not per batch)
   - Thread-safe Queue for parallel store communication
6. Sales data is aggregated across all stores by SKU
7. For each product, calculates order quantity with case rounding logic:
   - **If sales > 0**: Rounds up to nearest full case quantity: `ceil(sales / case) × case`
     - Example: Sales = 5, Case = 12 → Order = 12 (1 case)
     - Example: Sales = 25, Case = 12 → Order = 36 (3 cases)
   - **If sales = 0 or not found**: Uses 1 case as minimum (`quantity_per_case`)
8. Updates `products.quantity_sold_last_month` field with rounded order quantity via `bulk_update_sales()`
9. Streams progress via SSE with real-time updates
10. Frontend shows real-time progress and "not found" products

**Key Implementation**:
- `shopify_api.py`: `get_sales_by_skus_and_tag(skus, order_tag, days)` returns `{sku: quantity}` dict
- `database.py`: `bulk_update_sales(updates)` performs batch database updates
- `app.py`: `/api/products/sync-sales` processes in batches with linear progress tracking
- **Days parameter**: Configurable via `sales_sync_days` setting (default 30, range 1-365)
- **Critical Requirement**: Orders must be tagged at fulfillment with the configured `sales_order_tag`

### Excel Import Requirements
- Uses pandas to read Excel (.xlsx, .xls)
- `upc_barcode` column read as string (preserves leading zeros)
- NaN values converted to empty string and filtered out
- Duplicate UPC barcodes skipped during bulk insert (SQLite UNIQUE constraint)

### Column Header Conventions
Current UI labels (as of latest changes):
- ☐ | # | Product Name | UPC Barcode | Thold | Case | Price | Stock | Order | Actions

Where:
- **☐**: Checkbox for selecting products (calculates order total)
- **#**: Row number
- **Thold**: Threshold quantity for reordering
- **Case**: Quantity per case (used for order rounding)
- **Stock**: Available quantity (synced from Shopify)
- **Order**: Quantity to order (synced from Shopify sales, rounded to full cases)

**Stats Bar Display**: Located at the top of the page in a 4-column grid
- **Total Products**: Shows total count with optional filtered count
- **Low Stock Items**: Count of products where available_quantity <= threshold_quantity (auto-updates after sync operations)
- **Order Value**: Format "$XXX,XXX.XX (N selected)" - Sum of (Order Qty × Price) for checked products with comma thousands separator
- **Store Status**: Displays main Shopify store name or "Not Connected"

## Container Rebuild Requirements

**Backend changes require rebuild when**:
- Python code modified (`*.py`)
- Dependencies changed (`requirements.txt`)
- Dockerfile modified

**Frontend changes require rebuild when**:
- HTML modified (`templates/index.html`)
- CSS modified (`static/css/styles.css`)
- JavaScript modified (`static/js/*.js`)
- Dockerfile or nginx.conf modified

**Nginx changes require rebuild when**:
- `nginx.conf` modified
- Dockerfile modified

## Application Access

- **Main Application**: http://localhost:5001
- **Health Check**: http://localhost:5001/health
- **API Test**: http://localhost:5001/api/products

**Note**: The external port is **5001** (configured in `docker-compose.yml`: `"5001:80"`). The application is accessible at `http://localhost:5001`, not port 80. The README.md mentions port 80, but the actual docker-compose.yml configuration uses port 5001.

## Critical Notes

- The SQLite database persists in `./data/` volume (survives container restarts)
- Backend uses development Flask server (debug=False, host='0.0.0.0', port=5000)
- Port 5001 is configured in docker-compose.yml (change if needed)
- All containers restart automatically unless explicitly stopped
- FreeTDS driver is specifically chosen for SQL Server 2008/2012 compatibility (not Microsoft ODBC 18)
- Nginx proxy is configured with `proxy_buffering off` and `proxy_cache off` for SSE streaming support
- Sales sync only processes filtered/visible products on screen (not all products in database)
- Order quantities are always rounded up to full case quantities using `math.ceil(sales / case) × case`
- **Sales sync requires orders to be tagged**: Orders must have the tag configured in `sales_order_tag` setting for tag-based filtering to work correctly

## Modal Management

All modals (`#product-modal`, `#sync-progress-modal`, `#missing-products-modal`, `#quotation-modal`) follow the same pattern:
- Hidden by default with `display: none`
- Show/hide controlled by adding/removing `.flex` class
- Open: `modal.classList.remove('hidden'); modal.classList.add('flex');`
- Close: `modal.classList.remove('flex'); modal.classList.add('hidden');`
- All modals use the same dark theme CSS defined in `/frontend/static/css/styles.css`
- Modal overlay uses `rgba(0, 0, 0, 0.7)` background
- Modal content uses `.modal-content` class with dark background and border styling

**Important**: When resetting sync modals, MUST clear both CSS class AND inline `style.display`:
```javascript
notFoundSection.classList.add("hidden");
notFoundSection.style.display = "none";  // Required - inline style overrides class
notFoundListContainer.innerHTML = "";    // Clear previous content
```

## Server-Sent Events (SSE) Architecture

All sync operations use SSE for real-time progress updates:

**Backend Pattern**:
- Uses `@stream_with_context` decorator for streaming responses
- Content-Type: `text/event-stream`
- Event format: `data: {json}\n\n`
- Event types: `start`, `status`, `progress`, `complete`, `error`
- Thread-safe communication via `queue.Queue()` for parallel operations

**Frontend Pattern**:
- `EventSource` for SSE connection
- `onmessage` handler parses JSON events
- Progress bar updates on `type: 'progress'` events
- Status messages display on `type: 'status'` events
- Close EventSource on `complete` or `error`

**Progress Tracking Strategies**:
- **Linear Progress (Inventory/Sales/Missing Products Sync)**: Batch processing with per-product progress reporting (0-100%)
- **Two-phase Progress (Legacy)**: Phase 1 (0-50%) for slow I/O, Phase 2 (50-100%) for fast processing
  - Note: All current sync operations use linear progress for better UX

**Missing Products Feature**:
The "Find Missing Products" operation uses SSE to stream results in real-time:
1. Backend fetches Shopify inventory in pages of 250 items
2. Compares each item's SKU against local database
3. Streams matching products as they're found via `type: 'product_found'` events
4. Frontend displays products in real-time with checkboxes for bulk selection
5. User can select multiple products and click "Add Selected" to import them
6. Respects excluded SKUs settings (prefix matching)

---

## Deployment History

### Store 6 Implementation (October 2025)
**Status**: ✅ Deployed and Verified

**Changes Made**:
- Extended multi-store support from 5 to 6 Shopify stores
- Database migration: Added `shopify_store_6_url`, `shopify_store_6_token`, `shopify_store_6_location_id` columns
- Backend: Updated store aggregation loop from `range(2, 6)` to `range(2, 7)` in `app.py:1084`
- Frontend HTML: Added Store 6 collapsible section in settings UI
- Frontend JavaScript: Updated settings.js loops from `i <= 5` to `i <= 6`
- Documentation: Updated all references from "5 stores" to "6 stores"

**Files Modified**:
- `backend/database.py` (3 edits): Migration array, UPDATE query, SQL parameters
- `backend/app.py` (1 edit): Store iteration loop
- `frontend/static/js/settings.js` (2 edits): Load/save loops
- `frontend/templates/index.html` (2 edits): UI section, description text
- `CLAUDE.md` (3 edits): Documentation updates

**Verification Results**:
- ✅ Database columns created successfully via automatic migration
- ✅ Settings API returns Store 6 fields with null values (expected)
- ✅ Frontend displays Store 6 in Additional Stores section
- ✅ JavaScript correctly iterates through 6 stores
- ✅ All containers healthy and running
- ✅ Multi-store operations (Sales Sync, SC Sales Report) now support 6 stores

**Deployment Command**:
```bash
docker-compose build --no-cache backend frontend
docker-compose up -d
```

**Post-Deployment**:
- Zero downtime migration - database schema updated automatically on container restart
- No data loss - existing store configurations (1-5) preserved
- Store 6 ready for configuration in Settings → Shopify Integration → Additional Stores
