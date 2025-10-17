from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from flask_cors import CORS
import json
import math
import database
import shopify_api
import mssql_connector
import os

app = Flask(__name__)
CORS(app)

# Initialize database on startup
database.init_database()


@app.route('/')
def index():
    """Serve the main application page."""
    return render_template('index.html')


# Settings endpoints
@app.route('/api/settings', methods=['GET'])
def get_settings():
    """Get application settings."""
    settings = database.get_settings()
    return jsonify(settings)


@app.route('/api/settings', methods=['POST'])
def update_settings():
    """Update application settings."""
    data = request.json
    database.update_settings(data)
    return jsonify({'success': True, 'message': 'Settings updated successfully'})


# Products endpoints
@app.route('/api/products', methods=['GET'])
def get_products():
    """Get all products."""
    products = database.get_products()
    return jsonify(products)


@app.route('/api/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    """Get a single product."""
    product = database.get_product(product_id)
    if product:
        return jsonify(product)
    return jsonify({'error': 'Product not found'}), 404


@app.route('/api/products', methods=['POST'])
def create_product():
    """Create a new product."""
    data = request.json
    try:
        product_id = database.create_product(data)
        return jsonify({'success': True, 'id': product_id, 'message': 'Product created successfully'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/products/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    """Update a product."""
    data = request.json
    try:
        success = database.update_product(product_id, data)
        if success:
            return jsonify({'success': True, 'message': 'Product updated successfully'})
        return jsonify({'error': 'Product not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/products/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    """Delete a product."""
    success = database.delete_product(product_id)
    if success:
        return jsonify({'success': True, 'message': 'Product deleted successfully'})
    return jsonify({'error': 'Product not found'}), 404


@app.route('/api/products/batch', methods=['DELETE'])
def delete_all_products():
    """Delete all products."""
    try:
        count = database.delete_all_products()
        return jsonify({'success': True, 'message': f'Deleted {count} product(s)', 'count': count})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/products/clear-column', methods=['POST'])
def clear_column():
    """Clear a specific column for all products."""
    data = request.json
    column_name = data.get('column')

    if not column_name:
        return jsonify({'error': 'Column name is required'}), 400

    try:
        count = database.clear_column_data(column_name)
        return jsonify({
            'success': True,
            'message': f'Cleared {column_name} for {count} product(s)',
            'count': count
        })
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/products/import', methods=['POST'])
def import_products():
    """Import products from Excel file."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not file.filename.endswith(('.xlsx', '.xls')):
        return jsonify({'error': 'Invalid file type. Please upload an Excel file'}), 400

    try:
        import pandas as pd
        import io
        import numpy as np

        # Read Excel file - IMPORTANT: read upc_barcode as string to preserve leading zeros
        df = pd.read_excel(io.BytesIO(file.read()), dtype={'upc_barcode': str})

        # Validate required columns
        required_columns = ['product_name', 'upc_barcode']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return jsonify({'error': f'Missing required columns: {", ".join(missing_columns)}'}), 400

        # Convert upc_barcode to string and strip whitespace, handle NaN/None values
        df['upc_barcode'] = df['upc_barcode'].astype(str).str.strip()

        # Replace 'nan' string (from NaN values) with empty string
        df['upc_barcode'] = df['upc_barcode'].replace('nan', '')

        # Remove rows with empty UPC barcodes
        df = df[df['upc_barcode'] != '']

        # Convert DataFrame to list of dictionaries
        products = df.to_dict('records')

        # Bulk insert
        result = database.bulk_insert_products(products)

        return jsonify({
            'success': True,
            'message': f'Imported {result["inserted"]} products, skipped {result["skipped"]} duplicates',
            'details': result
        })

    except Exception as e:
        return jsonify({'error': f'Error processing file: {str(e)}'}), 500


@app.route('/api/products/export', methods=['POST'])
def export_products():
    """Export selected products to Excel file."""
    try:
        data = request.json
        product_ids = data.get('product_ids', [])

        if not product_ids:
            return jsonify({'error': 'No products selected'}), 400

        import pandas as pd
        import io
        from datetime import datetime

        # Fetch products from database
        products = []
        for product_id in product_ids:
            product = database.get_product(product_id)
            if product:
                products.append(product)

        if not products:
            return jsonify({'error': 'No products found'}), 404

        # Create DataFrame with column names matching import format
        df = pd.DataFrame(products)

        # Select and order columns for export
        export_columns = [
            'product_name',
            'upc_barcode',
            'threshold_quantity',
            'quantity_per_case',
            'price',
            'available_quantity',
            'quantity_sold_last_month'
        ]

        # Only include columns that exist in the data
        df = df[[col for col in export_columns if col in df.columns]]

        # Convert upc_barcode to string to preserve leading zeros
        df['upc_barcode'] = df['upc_barcode'].astype(str)

        # Create Excel file in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Products')

        output.seek(0)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'products_export_{timestamp}.xlsx'

        # Return file as download
        from flask import send_file
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        return jsonify({'error': f'Error exporting products: {str(e)}'}), 500


# Shopify endpoints
@app.route('/api/shopify/test', methods=['POST'])
def test_shopify_connection():
    """Test Shopify API connection."""
    try:
        # Try to get settings from request body first, then fallback to database
        data = request.json or {}

        if data.get('shopify_store_url') and data.get('shopify_access_token'):
            # Use settings from request
            settings = data
        else:
            # Use settings from database
            settings = database.get_settings()

        client = shopify_api.create_shopify_client(settings)

        if not client:
            return jsonify({'error': 'Shopify settings not configured'}), 400

        shop_info = client.test_connection()
        return jsonify({
            'success': True,
            'message': 'Connected to Shopify successfully',
            'shop': shop_info.get('shop', {})
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/shopify/locations', methods=['POST'])
def get_shopify_locations():
    """Get all Shopify locations."""
    try:
        # Try to get settings from request body first, then fallback to database
        data = request.json or {}

        if data.get('shopify_store_url') and data.get('shopify_access_token'):
            # Use settings from request
            settings = data
        else:
            # Use settings from database
            settings = database.get_settings()

        client = shopify_api.create_shopify_client(settings)

        if not client:
            return jsonify({'error': 'Shopify settings not configured'}), 400

        locations = client.get_locations()
        return jsonify(locations)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/shopify/inventory', methods=['GET'])
def get_shopify_inventory():
    """Get Shopify inventory matched with internal products."""
    try:
        settings = database.get_settings()
        location_id = settings.get('shopify_location_id')

        if not location_id:
            return jsonify({'error': 'Shopify location not configured'}), 400

        client = shopify_api.create_shopify_client(settings)
        if not client:
            return jsonify({'error': 'Shopify settings not configured'}), 400

        # Get internal products
        products = database.get_products()

        # Match with Shopify inventory
        matched_products = client.match_products_with_inventory(products, location_id)

        return jsonify(matched_products)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# MS SQL endpoints
@app.route('/api/mssql/test', methods=['POST'])
def test_mssql_connection():
    """Test MS SQL Server connection."""
    try:
        settings = database.get_settings()
        client = mssql_connector.create_mssql_client(settings)

        if not client:
            return jsonify({'error': 'MS SQL settings not configured'}), 400

        connection_info = client.test_connection()
        return jsonify({
            'success': True,
            'message': 'Connected to MS SQL Server successfully',
            'info': connection_info
        })

    except Exception as e:
        print(f"MS SQL connection error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/mssql/schema', methods=['POST'])
def update_mssql_schema():
    """Update MS SQL schema information (for future customization)."""
    data = request.json
    # This endpoint can be used later to save custom table/column mappings
    return jsonify({
        'success': True,
        'message': 'Schema configuration saved (placeholder)'
    })


# Quotation endpoints
@app.route('/api/quotations/customers/search', methods=['GET'])
def search_customers():
    """Search customers by AccountNo."""
    try:
        query = request.args.get('q', '')
        if not query:
            return jsonify([])

        settings = database.get_settings()
        client = mssql_connector.create_mssql_client(settings)

        if not client:
            return jsonify({'error': 'MS SQL settings not configured'}), 400

        customers = client.search_customers(query)
        client.disconnect()

        return jsonify(customers)

    except Exception as e:
        print(f"Customer search error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/quotations/customers/<int:customer_id>', methods=['GET'])
def get_customer(customer_id):
    """Get customer details by ID."""
    try:
        settings = database.get_settings()
        client = mssql_connector.create_mssql_client(settings)

        if not client:
            return jsonify({'error': 'MS SQL settings not configured'}), 400

        customer = client.get_customer_by_id(customer_id)
        client.disconnect()

        if not customer:
            return jsonify({'error': 'Customer not found'}), 404

        return jsonify(customer)

    except Exception as e:
        print(f"Get customer error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/quotations/create', methods=['POST'])
def create_quotation():
    """Create a new quotation in MS SQL database."""
    try:
        data = request.json
        customer_id = data.get('customer_id')
        quotation_title = data.get('quotation_title', '').strip()
        po_number = data.get('po_number', '').strip()
        notes = data.get('notes', '').strip()
        products = data.get('products', [])

        if not customer_id:
            return jsonify({'error': 'Customer ID is required'}), 400

        if not products:
            return jsonify({'error': 'At least one product is required'}), 400

        # Get MS SQL client
        settings = database.get_settings()
        client = mssql_connector.create_mssql_client(settings)

        if not client:
            return jsonify({'error': 'MS SQL settings not configured'}), 400

        # Get customer details
        customer = client.get_customer_by_id(customer_id)
        if not customer:
            client.disconnect()
            return jsonify({'error': 'Customer not found'}), 404

        # Get next quotation number
        quotation_number = client.get_next_quotation_number()

        # Get item details for all products (batch query for performance)
        upcs = [p.get('upc_barcode') for p in products if p.get('upc_barcode')]
        item_details_map = client.get_bulk_item_details_by_upcs(upcs)

        # Calculate quotation total and build line items
        quotation_total = 0.0
        line_items = []
        skipped_products = []

        for product in products:
            upc = product.get('upc_barcode')
            price = float(product.get('price', 0))
            qty = float(product.get('order_qty', 0))

            if not upc or price <= 0 or qty <= 0:
                skipped_products.append({
                    'name': product.get('product_name', 'Unknown'),
                    'reason': 'Missing UPC, price, or quantity'
                })
                continue

            # Get item details from MS SQL
            item = item_details_map.get(upc)
            if not item:
                skipped_products.append({
                    'name': product.get('product_name', 'Unknown'),
                    'upc': upc,
                    'reason': 'Product not found in Items_tbl'
                })
                continue

            # Calculate line totals
            extended_price = qty * price
            unit_cost = float(item.get('UnitCost', 0)) if item.get('UnitCost') else 0.0
            extended_cost = qty * unit_cost

            quotation_total += extended_price

            # Build line item
            line_item = {
                'CateID': item.get('CateID'),
                'SubCateID': item.get('SubCateID'),
                'UnitDesc': item.get('UnitDesc'),
                'UnitQty': 1,
                'ProductID': item.get('ProductID'),
                'ProductSKU': item.get('ProductSKU'),
                'ProductUPC': upc,
                'ProductDescription': item.get('ProductDescription'),
                'ItemSize': item.get('ItemSize'),
                'ExpDate': item.get('ExpDate'),
                'ReasonID': 0,
                'LineMessage': '',
                'UnitPrice': price,
                'OriginalPrice': price,
                'RememberPrice': 0,
                'UnitCost': unit_cost,
                'Discount': 0,
                'ds_Percent': 0,
                'Qty': qty,
                'ItemWeight': item.get('ItemWeight'),
                'ExtendedPrice': extended_price,
                'ExtendedDisc': 0,
                'ExtendedCost': extended_cost,
                'PromotionID': 0,
                'PromotionLine': 0,
                'PromotionDescription': None,
                'PromotionAmount': None,
                'ActExtendedPrice': extended_price,
                'SPPromoted': item.get('SPPromoted'),
                'SPPromotionDescription': item.get('SPPromotionDescription'),
                'Taxable': 0,
                'ItemTaxID': item.get('ItemTaxID'),
                'Catch': 0,
                'Comments': None,
                'Flag': 0
            }

            line_items.append(line_item)

        if not line_items:
            client.disconnect()
            return jsonify({
                'error': 'No valid products to create quotation',
                'skipped_products': skipped_products
            }), 400

        # Build quotation data
        from datetime import datetime, timedelta

        quotation_date = datetime.now()
        expiration_date = quotation_date + timedelta(days=3650)  # 10 years

        quotation_data = {
            'QuotationNumber': quotation_number,
            'QuotationDate': quotation_date,
            'QuotationTitle': quotation_title,
            'PoNumber': po_number,
            'AutoOrderNo': None,
            'ExpirationDate': expiration_date,
            'CustomerID': customer_id,
            'BusinessName': customer.get('BusinessName'),
            'AccountNo': customer.get('AccountNo'),
            'Shipto': customer.get('ShipTo'),
            'ShipAddress1': customer.get('ShipAddress1'),
            'ShipAddress2': customer.get('ShipAddress2'),
            'ShipContact': customer.get('ShipContact'),
            'ShipCity': customer.get('ShipCity'),
            'ShipState': customer.get('ShipState'),
            'ShipZipCode': customer.get('ShipZipCode'),
            'ShipPhoneNo': customer.get('ShipPhone_Number'),
            'Status': 0,
            'ShipperID': 0,
            'SalesRepID': customer.get('SalesRepID'),
            'TermID': customer.get('TermID'),
            'TotalTaxes': 0.0,
            'QuotationTotal': quotation_total,
            'Header': '',
            'Footer': '',
            'Notes': notes,
            'Memo': '',
            'flaged': 0
        }

        # Insert quotation
        quotation_id = client.insert_quotation(quotation_data)
        if not quotation_id:
            client.disconnect()
            return jsonify({'error': 'Failed to create quotation'}), 500

        # Insert line items
        success = client.insert_quotation_details(quotation_id, line_items)
        client.disconnect()

        if not success:
            return jsonify({'error': 'Failed to create quotation line items'}), 500

        # Return success response
        response = {
            'success': True,
            'quotation_id': quotation_id,
            'quotation_number': quotation_number,
            'quotation_total': quotation_total,
            'line_items_count': len(line_items)
        }

        if skipped_products:
            response['skipped_products'] = skipped_products

        return jsonify(response)

    except Exception as e:
        print(f"Create quotation error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/products/missing', methods=['GET'])
def find_missing_products():
    """
    Find products that exist in Shopify but not in local database.
    Only returns products with available quantity > 0.
    Streams progress updates via SSE.
    """
    def generate_progress():
        """Generator function to stream progress updates."""
        try:
            settings = database.get_settings()
            location_id = settings.get('shopify_location_id')

            sse_newline = "\n\n"

            if not location_id:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Shopify location not configured'})}{sse_newline}"
                return

            client = shopify_api.create_shopify_client(settings)
            if not client:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Shopify settings not configured'})}{sse_newline}"
                return

            # Send start event
            yield f"data: {json.dumps({'type': 'start', 'message': 'Fetching inventory from Shopify...'})}{sse_newline}"

            # Get all local products and create SKU set
            local_products = database.get_products()
            local_skus = {p.get('upc_barcode') for p in local_products if p.get('upc_barcode')}

            # Parse excluded SKUs from settings
            excluded_skus_str = settings.get('excluded_skus', '')
            excluded_skus = set()
            if excluded_skus_str:
                # Split by comma or newline, strip whitespace
                for sku in excluded_skus_str.replace(',', '\n').split('\n'):
                    sku = sku.strip()
                    if sku:
                        excluded_skus.add(sku)

            # Fetch inventory from Shopify with pagination (streaming results)
            missing_products = []
            cursor = None
            has_next_page = True
            page_num = 0
            total_items_processed = 0

            query = """
            query getInventoryLevels($locationId: ID!, $cursor: String) {
                location(id: $locationId) {
                    id
                    name
                    inventoryLevels(first: 250, after: $cursor) {
                        pageInfo {
                            hasNextPage
                            endCursor
                        }
                        edges {
                            node {
                                id
                                quantities(names: ["available"]) {
                                    name
                                    quantity
                                }
                                item {
                                    id
                                    sku
                                    variant {
                                        id
                                        sku
                                        title
                                        barcode
                                        product {
                                            id
                                            title
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
            """

            while has_next_page:
                page_num += 1
                variables = {'locationId': location_id}
                if cursor:
                    variables['cursor'] = cursor

                try:
                    data = client._execute_query(query, variables)
                    location_data = data.get('location', {})
                    inventory_levels = location_data.get('inventoryLevels', {})

                    items_in_page = 0

                    for edge in inventory_levels.get('edges', []):
                        node = edge['node']
                        item = node.get('item', {})
                        variant = item.get('variant', {})
                        product = variant.get('product', {}) if variant else {}

                        # Get available quantity
                        available_qty = 0
                        for qty in node.get('quantities', []):
                            if qty['name'] == 'available':
                                available_qty = qty['quantity']
                                break

                        sku = variant.get('sku') or item.get('sku')
                        items_in_page += 1
                        total_items_processed += 1

                        # Check if SKU starts with any excluded prefix
                        is_excluded = any(sku.startswith(prefix) for prefix in excluded_skus) if sku else False

                        # Only include if:
                        # 1. Has a SKU
                        # 2. Available quantity > 0
                        # 3. Not in local database
                        # 4. SKU doesn't start with any excluded prefix
                        if sku and available_qty > 0 and sku not in local_skus and not is_excluded:
                            missing_product = {
                                'sku': sku,
                                'product_title': product.get('title', 'Unknown'),
                                'variant_title': variant.get('title', ''),
                                'barcode': variant.get('barcode'),
                                'available_quantity': available_qty
                            }
                            missing_products.append(missing_product)

                            # Send progress update with new product found
                            yield f"data: {json.dumps({'type': 'product_found', 'product': missing_product})}{sse_newline}"

                    # Send page progress update
                    yield f"data: {json.dumps({'type': 'progress', 'page': page_num, 'items_processed': total_items_processed, 'missing_count': len(missing_products)})}{sse_newline}"

                    # Check for next page
                    page_info = inventory_levels.get('pageInfo', {})
                    has_next_page = page_info.get('hasNextPage', False)
                    cursor = page_info.get('endCursor')

                except Exception as e:
                    print(f"Error fetching page {page_num}: {e}")
                    yield f"data: {json.dumps({'type': 'error', 'message': f'Error fetching page {page_num}: {str(e)}'})}{sse_newline}"
                    return

            # Send completion event
            yield f"data: {json.dumps({'type': 'complete', 'missing_products': missing_products, 'count': len(missing_products), 'total_items_processed': total_items_processed})}{sse_newline}"

        except Exception as e:
            print(f"Error finding missing products: {e}")
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}{sse_newline}"

    return Response(
        stream_with_context(generate_progress()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )


@app.route('/api/products/sync', methods=['GET'])
def sync_products_with_all():
    """
    Sync products with Shopify inventory using batch OR queries for better performance.
    This will:
    1. Query Shopify for multiple products' inventory by SKU using OR syntax (batch processing)
    2. Save the available quantities to the database in bulk
    3. Return the updated products with inventory data

    Returns progress information for each product processed.
    """
    def generate_progress():
        """Generator function to stream progress updates."""
        try:
            settings = database.get_settings()
            products = database.get_products()
            total_products = len(products)

            # Send initial progress
            sse_newline = "\n\n"
            yield f"data: {json.dumps({'type': 'start', 'total': total_products})}{sse_newline}"

            # Sync with Shopify
            shopify_client = shopify_api.create_shopify_client(settings)
            location_id = settings.get('shopify_location_id')

            if not shopify_client or not location_id:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Shopify not configured'})}{sse_newline}"
                return

            synced_count = 0
            not_found_count = 0
            not_found_products = []

            # Batch products into groups of 50 SKUs for bulk processing
            batch_size = 50
            current_index = 0

            # Process products in batches
            for i in range(0, len(products), batch_size):
                batch = products[i:i + batch_size]

                # Filter products with UPC barcodes
                products_with_sku = [p for p in batch if p.get('upc_barcode')]
                skus = [p['upc_barcode'] for p in products_with_sku]

                if not skus:
                    # All products in batch have no UPC, skip individually
                    for product in batch:
                        current_index += 1
                        yield f"data: {json.dumps({'type': 'progress', 'current': current_index, 'total': total_products, 'product_name': product.get('product_name', 'Unknown'), 'status': 'skipped', 'message': 'No UPC barcode'})}{sse_newline}"
                    continue

                try:
                    # Fetch inventory for all SKUs in this batch with single API call
                    inventory_results = shopify_client.get_bulk_variant_inventory_by_skus(skus, location_id)

                    # Prepare bulk database updates
                    updates = []

                    # Process each product in the batch
                    for product in batch:
                        current_index += 1
                        upc_barcode = product.get('upc_barcode')

                        if not upc_barcode:
                            # Send progress update for skipped product
                            yield f"data: {json.dumps({'type': 'progress', 'current': current_index, 'total': total_products, 'product_name': product.get('product_name', 'Unknown'), 'status': 'skipped', 'message': 'No UPC barcode'})}{sse_newline}"
                            continue

                        # Check if SKU was found in batch results
                        if upc_barcode in inventory_results:
                            available_qty = inventory_results[upc_barcode]
                            updates.append((product['id'], available_qty))
                            synced_count += 1

                            # Send progress update
                            yield f"data: {json.dumps({'type': 'progress', 'current': current_index, 'total': total_products, 'product_name': product.get('product_name', 'Unknown'), 'status': 'synced', 'quantity': available_qty})}{sse_newline}"
                        else:
                            # No match found in Shopify
                            updates.append((product['id'], None))
                            not_found_count += 1
                            not_found_products.append({
                                'product_name': product.get('product_name', 'Unknown'),
                                'upc_barcode': upc_barcode
                            })

                            # Send progress update
                            yield f"data: {json.dumps({'type': 'progress', 'current': current_index, 'total': total_products, 'product_name': product.get('product_name', 'Unknown'), 'status': 'not_found'})}{sse_newline}"

                    # Bulk update database for this batch
                    if updates:
                        database.bulk_update_inventory(updates)

                except Exception as e:
                    print(f"Error syncing batch starting at index {i}: {e}")
                    # Send error for each product in the failed batch
                    for product in batch:
                        current_index += 1
                        yield f"data: {json.dumps({'type': 'progress', 'current': current_index, 'total': total_products, 'product_name': product.get('product_name', 'Unknown'), 'status': 'error', 'message': str(e)})}{sse_newline}"

            # Send completion message
            yield f"data: {json.dumps({'type': 'complete', 'synced': synced_count, 'not_found': not_found_count, 'not_found_products': not_found_products, 'total': total_products})}{sse_newline}"

        except Exception as e:
            print(f"Sync error: {e}")
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}{sse_newline}"

    return Response(
        stream_with_context(generate_progress()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )


@app.route('/api/products/sync-price', methods=['GET'])
def sync_products_price():
    """
    Sync product prices from MS SQL Server using batch queries for better performance.
    This will:
    1. Split products into batches of 50 UPCs
    2. Query MS SQL Items_tbl for each batch using IN clause (single query per batch)
    3. Update the price field with UnitPriceC from Items_tbl in bulk
    4. Return progress information for each product processed
    """
    def generate_progress():
        """Generator function to stream progress updates."""
        try:
            settings = database.get_settings()
            products = database.get_products()
            total_products = len(products)

            # Send initial progress
            sse_newline = "\n\n"
            yield f"data: {json.dumps({'type': 'start', 'total': total_products})}{sse_newline}"

            # Get MS SQL client
            mssql_client = mssql_connector.create_mssql_client(settings)

            if not mssql_client:
                yield f"data: {json.dumps({'type': 'error', 'message': 'MS SQL not configured'})}{sse_newline}"
                return

            # Connect to MS SQL
            try:
                mssql_client.connect()
            except Exception as e:
                msg = f'Failed to connect to MS SQL: {str(e)}'
                yield f"data: {json.dumps({'type': 'error', 'message': msg})}{sse_newline}"
                return

            synced_count = 0
            not_found_count = 0
            not_found_products = []

            # Batch products into groups of 50 UPCs for bulk processing
            batch_size = 50
            current_index = 0

            # Process products in batches
            for i in range(0, len(products), batch_size):
                batch = products[i:i + batch_size]

                # Filter products with UPC barcodes
                products_with_upc = [p for p in batch if p.get('upc_barcode')]
                upcs = [p['upc_barcode'] for p in products_with_upc]

                if not upcs:
                    # All products in batch have no UPC, skip individually
                    for product in batch:
                        current_index += 1
                        yield f"data: {json.dumps({'type': 'progress', 'current': current_index, 'total': total_products, 'product_name': product.get('product_name', 'Unknown'), 'status': 'skipped', 'message': 'No UPC barcode'})}{sse_newline}"
                    continue

                try:
                    # Fetch prices for all UPCs in this batch with single query
                    price_results = mssql_client.get_bulk_prices_by_upcs(upcs)

                    # Prepare bulk database updates
                    updates = []

                    # Process each product in the batch
                    for product in batch:
                        current_index += 1
                        upc_barcode = product.get('upc_barcode')

                        if not upc_barcode:
                            # Send progress update for skipped product
                            yield f"data: {json.dumps({'type': 'progress', 'current': current_index, 'total': total_products, 'product_name': product.get('product_name', 'Unknown'), 'status': 'skipped', 'message': 'No UPC barcode'})}{sse_newline}"
                            continue

                        # Check if UPC was found in batch results
                        if upc_barcode in price_results:
                            price = price_results[upc_barcode]
                            updates.append((product['id'], price))
                            synced_count += 1

                            # Send progress update
                            yield f"data: {json.dumps({'type': 'progress', 'current': current_index, 'total': total_products, 'product_name': product.get('product_name', 'Unknown'), 'status': 'synced', 'price': price})}{sse_newline}"
                        else:
                            # No match found in MS SQL
                            not_found_count += 1
                            not_found_products.append({
                                'product_name': product.get('product_name', 'Unknown'),
                                'upc_barcode': upc_barcode
                            })

                            # Send progress update
                            yield f"data: {json.dumps({'type': 'progress', 'current': current_index, 'total': total_products, 'product_name': product.get('product_name', 'Unknown'), 'status': 'not_found'})}{sse_newline}"

                    # Bulk update database for this batch
                    if updates:
                        database.bulk_update_prices(updates)

                except Exception as e:
                    print(f"Error syncing batch starting at index {i}: {e}")
                    # Send error for each product in the failed batch
                    for product in batch:
                        current_index += 1
                        yield f"data: {json.dumps({'type': 'progress', 'current': current_index, 'total': total_products, 'product_name': product.get('product_name', 'Unknown'), 'status': 'error', 'message': str(e)})}{sse_newline}"

            # Disconnect from MS SQL
            mssql_client.disconnect()

            # Send completion message
            yield f"data: {json.dumps({'type': 'complete', 'synced': synced_count, 'not_found': not_found_count, 'not_found_products': not_found_products, 'total': total_products})}{sse_newline}"

        except Exception as e:
            print(f"Price sync error: {e}")
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}{sse_newline}"

    return Response(
        stream_with_context(generate_progress()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )


def fetch_sales_data_from_stores(products, settings, from_date=None, to_date=None, days=None):
    """
    Fetch sales data from all configured Shopify stores for the given products and date range.

    This helper function is used by both the sync endpoint and reports endpoint.
    It fetches sales data in parallel from all configured stores and aggregates by SKU.

    Args:
        products: List of product dicts with upc_barcode field
        settings: Settings dict with store configs and sales_order_tag
        from_date: Optional datetime for start of date range
        to_date: Optional datetime for end of date range
        days: Optional number of days to look back (used if from_date/to_date not provided)

    Returns:
        Dictionary with:
            - sales_by_sku: {sku: total_quantity}
            - stores_processed: int (number of stores successfully queried)
            - stores_failed: list of {store, error} dicts
            - date_range: {from, to, days}
            - tag_used: str
    """
    import concurrent.futures
    from datetime import datetime, timedelta
    import queue

    # Get sales order tag from settings
    sales_order_tag = settings.get('sales_order_tag', '').strip()
    if not sales_order_tag:
        raise ValueError('Sales Order Tag not configured in settings')

    # Calculate date range
    if from_date and to_date:
        date_info = {
            'from': from_date.strftime('%Y-%m-%d'),
            'to': to_date.strftime('%Y-%m-%d'),
            'days': (to_date - from_date).days + 1
        }
    elif days:
        to_date = datetime.now()
        from_date = to_date - timedelta(days=days)
        date_info = {
            'from': from_date.strftime('%Y-%m-%d'),
            'to': to_date.strftime('%Y-%m-%d'),
            'days': days
        }
    else:
        # Default to last 30 days
        days = settings.get('sales_sync_days', 30)
        to_date = datetime.now()
        from_date = to_date - timedelta(days=days)
        date_info = {
            'from': from_date.strftime('%Y-%m-%d'),
            'to': to_date.strftime('%Y-%m-%d'),
            'days': days
        }

    # Build list of store configurations (main + additional stores)
    stores = []

    # Main store (always first)
    if settings.get('shopify_store_url') and settings.get('shopify_access_token'):
        stores.append({
            'name': 'Store 1 (Main)',
            'url': settings['shopify_store_url'],
            'token': settings['shopify_access_token']
        })

    # Additional stores (2-6)
    for i in range(2, 7):
        url = settings.get(f'shopify_store_{i}_url')
        token = settings.get(f'shopify_store_{i}_token')
        if url and token:
            stores.append({
                'name': f'Store {i}',
                'url': url,
                'token': token
            })

    if not stores:
        raise ValueError('No Shopify stores configured')

    # Get all SKUs from products
    skus = [p['upc_barcode'] for p in products if p.get('upc_barcode')]

    if not skus:
        return {
            'sales_by_sku': {},
            'stores_processed': 0,
            'stores_failed': [],
            'date_range': date_info,
            'tag_used': sales_order_tag
        }

    # Batch SKUs into groups of 50
    batch_size = 50
    sku_batches = [skus[i:i + batch_size] for i in range(0, len(skus), batch_size)]

    # Aggregate sales across all stores and batches
    total_sales_by_sku = {}
    failed_stores = []

    def fetch_store_sales(store_config, all_skus):
        """Fetch sales from a single store for all SKU batches."""
        store_name = store_config['name']
        try:
            client = shopify_api.ShopifyAPI(store_config['url'], store_config['token'])
            store_sales = {}

            # Process each batch of SKUs
            for batch_skus in sku_batches:
                batch_sales = client.get_sales_by_skus_and_tag(
                    skus=batch_skus,
                    order_tag=sales_order_tag,
                    from_date=from_date,
                    to_date=to_date,
                    days=days,
                    page_size=250
                )

                # Aggregate batch results
                for sku, qty in batch_sales.items():
                    store_sales[sku] = store_sales.get(sku, 0) + qty

            return {'store': store_name, 'success': True, 'sales': store_sales}
        except Exception as e:
            return {'store': store_name, 'success': False, 'error': str(e)}

    # Fetch from all stores in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(fetch_store_sales, store, skus) for store in stores]

        for future in concurrent.futures.as_completed(futures):
            result = future.result()

            if result['success']:
                # Aggregate sales from this store
                for sku, qty in result['sales'].items():
                    total_sales_by_sku[sku] = total_sales_by_sku.get(sku, 0) + qty
            else:
                failed_stores.append({'store': result['store'], 'error': result['error']})

    stores_processed = len(stores) - len(failed_stores)

    return {
        'sales_by_sku': total_sales_by_sku,
        'stores_processed': stores_processed,
        'stores_failed': failed_stores,
        'date_range': date_info,
        'tag_used': sales_order_tag
    }


@app.route('/api/products/sync-sales', methods=['GET'])
def sync_products_sales():
    """
    Sync product sales quantities from multiple Shopify stores.

    This endpoint uses the fetch_sales_data_from_stores() helper to:
    1. Fetch sales from all configured stores in parallel
    2. Aggregate quantities sold by SKU across all stores
    3. Update the quantity_sold_last_month field with case rounding
    4. Provide product-by-product progress tracking via SSE

    Query Parameters:
        product_ids: Comma-separated list of product IDs to sync (syncs filtered products)
    """
    def generate_progress():
        """Generator function to stream progress updates."""
        try:
            import math

            settings = database.get_settings()
            all_products = database.get_products()

            # Get sales sync days from settings (default to 30)
            sales_sync_days = settings.get('sales_sync_days', 30)
            if not isinstance(sales_sync_days, int) or sales_sync_days < 1:
                sales_sync_days = 30

            # Filter products if product_ids provided
            product_ids_param = request.args.get('product_ids', '')
            if product_ids_param:
                product_ids = [int(pid) for pid in product_ids_param.split(',') if pid]
                products = [p for p in all_products if p['id'] in product_ids]
            else:
                products = all_products

            total_products = len(products)
            sse_newline = "\n\n"

            # Send initial progress
            yield f"data: {json.dumps({'type': 'start', 'total': total_products, 'current': 0})}{sse_newline}"
            yield f"data: {json.dumps({'type': 'status', 'message': 'Fetching sales data from all stores...'})}{sse_newline}"

            # Fetch sales data using helper function
            try:
                sales_result = fetch_sales_data_from_stores(
                    products=products,
                    settings=settings,
                    days=sales_sync_days
                )
            except ValueError as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}{sse_newline}"
                return
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': f'Failed to fetch sales data: {str(e)}'})}{sse_newline}"
                return

            # Report fetch completion
            stores_processed = sales_result['stores_processed']
            stores_failed = sales_result['stores_failed']
            sales_by_sku = sales_result['sales_by_sku']
            date_range = sales_result['date_range']
            tag_used = sales_result['tag_used']

            msg = f'Fetched sales from {stores_processed} store(s) with tag "{tag_used}" ({date_range["from"]} to {date_range["to"]})'
            yield f"data: {json.dumps({'type': 'status', 'message': msg})}{sse_newline}"

            if stores_failed:
                for failed in stores_failed:
                    error_msg = f'✗ {failed.get("store")}: {failed.get("error")}'
                    yield f"data: {json.dumps({'type': 'status', 'message': error_msg})}{sse_newline}"

            # Process each product and update database
            all_updates = []
            synced_count = 0
            not_found_count = 0
            not_found_products = []

            for idx, product in enumerate(products):
                current_index = idx + 1
                upc_barcode = product.get('upc_barcode')

                if not upc_barcode:
                    yield f"data: {json.dumps({'type': 'progress', 'current': current_index, 'total': total_products, 'product_name': product.get('product_name', 'Unknown'), 'status': 'skipped', 'message': 'No UPC barcode'})}{sse_newline}"
                    continue

                try:
                    quantity_per_case = product.get('quantity_per_case') or 0
                    total_sales = sales_by_sku.get(upc_barcode, 0)

                    if total_sales > 0:
                        # Round up to nearest full case
                        if quantity_per_case > 0:
                            order_quantity = math.ceil(total_sales / quantity_per_case) * quantity_per_case
                        else:
                            order_quantity = total_sales

                        all_updates.append((product['id'], order_quantity))
                        synced_count += 1

                        yield f"data: {json.dumps({'type': 'progress', 'current': current_index, 'total': total_products, 'product_name': product.get('product_name', 'Unknown'), 'status': 'synced', 'quantity': order_quantity})}{sse_newline}"
                    else:
                        # No sales found - use 1 case as minimum
                        fallback_quantity = quantity_per_case if quantity_per_case > 0 else 0
                        all_updates.append((product['id'], fallback_quantity))
                        not_found_count += 1
                        not_found_products.append({
                            'product_name': product.get('product_name', 'Unknown'),
                            'upc_barcode': upc_barcode
                        })

                        yield f"data: {json.dumps({'type': 'progress', 'current': current_index, 'total': total_products, 'product_name': product.get('product_name', 'Unknown'), 'status': 'not_found', 'fallback_quantity': fallback_quantity})}{sse_newline}"

                except Exception as e:
                    print(f"Error processing product {product.get('product_name')}: {e}")
                    yield f"data: {json.dumps({'type': 'progress', 'current': current_index, 'total': total_products, 'product_name': product.get('product_name', 'Unknown'), 'status': 'error', 'message': str(e)})}{sse_newline}"

            # BULK UPDATE all products in single transaction
            if all_updates:
                try:
                    database.bulk_update_sales(all_updates)
                    yield f"data: {json.dumps({'type': 'status', 'message': f'Updated {len(all_updates)} product(s) in database'})}{sse_newline}"
                except Exception as e:
                    yield f"data: {json.dumps({'type': 'error', 'message': f'Failed to update database: {str(e)}'})}{sse_newline}"
                    return

            # Send completion message
            completion_data = {
                'type': 'complete',
                'synced': synced_count,
                'not_found': not_found_count,
                'not_found_products': not_found_products,
                'total': total_products,
                'stores_processed': stores_processed,
                'stores_failed': len(stores_failed),
                'failed_stores': stores_failed
            }
            yield f"data: {json.dumps(completion_data)}{sse_newline}"

        except Exception as e:
            print(f"Sales sync error: {e}")
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return Response(
        stream_with_context(generate_progress()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )


# Reports endpoints
@app.route('/api/reports/sc-sales', methods=['GET'])
def get_sc_sales_report():
    """
    Get SC Sales report for a custom date range.

    This is a read-only endpoint that fetches sales data from all configured
    Shopify stores and returns aggregated sales by product.

    Query Parameters:
        from_date: Start date in YYYY-MM-DD format (required)
        to_date: End date in YYYY-MM-DD format (required)

    Returns:
        JSON with:
            - products: List of products with sales data
            - summary: Aggregated statistics
            - date_range: Date range used
            - stores_info: Store processing status
    """
    try:
        from datetime import datetime

        # Get and validate query parameters
        from_date_str = request.args.get('from_date')
        to_date_str = request.args.get('to_date')

        if not from_date_str or not to_date_str:
            return jsonify({'error': 'Both from_date and to_date are required'}), 400

        try:
            from_date = datetime.strptime(from_date_str, '%Y-%m-%d')
            to_date = datetime.strptime(to_date_str, '%Y-%m-%d')
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

        if from_date > to_date:
            return jsonify({'error': 'from_date must be before or equal to to_date'}), 400

        # Get all products and settings
        settings = database.get_settings()
        all_products = database.get_products()

        if not all_products:
            return jsonify({
                'products': [],
                'summary': {
                    'total_products': 0,
                    'products_with_sales': 0,
                    'total_items_sold': 0
                },
                'date_range': {
                    'from': from_date_str,
                    'to': to_date_str,
                    'days': (to_date - from_date).days + 1
                },
                'stores_info': {
                    'stores_processed': 0,
                    'stores_failed': []
                }
            })

        # Fetch sales data using helper function
        try:
            sales_result = fetch_sales_data_from_stores(
                products=all_products,
                settings=settings,
                from_date=from_date,
                to_date=to_date
            )
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            return jsonify({'error': f'Failed to fetch sales data: {str(e)}'}), 500

        # Build report data
        sales_by_sku = sales_result['sales_by_sku']
        report_products = []
        total_items_sold = 0
        products_with_sales = 0
        total_sales_value = 0.0

        for product in all_products:
            upc_barcode = product.get('upc_barcode')

            if not upc_barcode:
                continue

            quantity_sold = sales_by_sku.get(upc_barcode, 0)

            # Skip products with no sales
            if quantity_sold == 0:
                continue

            products_with_sales += 1
            total_items_sold += quantity_sold

            # Calculate estimated total (qty × price)
            price = product.get('price') or 0
            estimated_total = quantity_sold * price
            total_sales_value += estimated_total

            report_products.append({
                'id': product.get('id'),
                'product_name': product.get('product_name'),
                'upc_barcode': upc_barcode,
                'quantity_sold': quantity_sold,
                'price': price,
                'estimated_total': estimated_total,
                'quantity_per_case': product.get('quantity_per_case'),
                'available_quantity': product.get('available_quantity'),
                'threshold_quantity': product.get('threshold_quantity')
            })

        # Sort by quantity_sold descending (highest sales first)
        report_products.sort(key=lambda x: x['quantity_sold'], reverse=True)

        # Build response
        response = {
            'products': report_products,
            'summary': {
                'total_products': len(report_products),
                'products_with_sales': products_with_sales,
                'total_items_sold': total_items_sold,
                'total_sales_value': total_sales_value
            },
            'date_range': sales_result['date_range'],
            'stores_info': {
                'stores_processed': sales_result['stores_processed'],
                'stores_failed': sales_result['stores_failed'],
                'tag_used': sales_result['tag_used']
            }
        }

        return jsonify(response)

    except Exception as e:
        print(f"SC Sales report error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/reports/sc-sales/export', methods=['POST'])
def export_sc_sales_report():
    """
    Export SC Sales report to Excel file.

    Request Body:
        {
            "from_date": "YYYY-MM-DD",
            "to_date": "YYYY-MM-DD"
        }

    Returns:
        Excel file download with sales report data
    """
    try:
        from datetime import datetime
        import pandas as pd
        import io
        from flask import send_file

        # Get and validate request data
        data = request.json
        from_date_str = data.get('from_date')
        to_date_str = data.get('to_date')

        if not from_date_str or not to_date_str:
            return jsonify({'error': 'Both from_date and to_date are required'}), 400

        try:
            from_date = datetime.strptime(from_date_str, '%Y-%m-%d')
            to_date = datetime.strptime(to_date_str, '%Y-%m-%d')
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

        if from_date > to_date:
            return jsonify({'error': 'from_date must be before or equal to to_date'}), 400

        # Get all products and settings
        settings = database.get_settings()
        all_products = database.get_products()

        if not all_products:
            return jsonify({'error': 'No products found'}), 404

        # Fetch sales data using helper function
        try:
            sales_result = fetch_sales_data_from_stores(
                products=all_products,
                settings=settings,
                from_date=from_date,
                to_date=to_date
            )
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            return jsonify({'error': f'Failed to fetch sales data: {str(e)}'}), 500

        # Build export data
        sales_by_sku = sales_result['sales_by_sku']
        export_data = []

        for product in all_products:
            upc_barcode = product.get('upc_barcode')

            if not upc_barcode:
                continue

            quantity_sold = sales_by_sku.get(upc_barcode, 0)

            # Skip products with no sales
            if quantity_sold == 0:
                continue

            # Calculate estimated total (qty × price)
            price = product.get('price') or 0
            estimated_total = quantity_sold * price

            export_data.append({
                'Product Name': product.get('product_name'),
                'UPC Barcode': upc_barcode,
                'Quantity Sold': quantity_sold,
                'Price': price,
                'Estimated Total': estimated_total,
                'Case Qty': product.get('quantity_per_case'),
                'Available Stock': product.get('available_quantity'),
                'Threshold': product.get('threshold_quantity')
            })

        # Sort by quantity sold descending
        export_data.sort(key=lambda x: x['Quantity Sold'], reverse=True)

        # Create DataFrame
        df = pd.DataFrame(export_data)

        # Create Excel file in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='SC Sales Report')

            # Calculate total sales value
            total_sales_value = sum(item['Estimated Total'] for item in export_data)

            # Add summary sheet
            summary_data = {
                'Metric': [
                    'Report Period',
                    'From Date',
                    'To Date',
                    'Number of Days',
                    'Total Products',
                    'Products with Sales',
                    'Total Items Sold',
                    'Total Sales Value',
                    'Stores Processed',
                    'Tag Used'
                ],
                'Value': [
                    f"{from_date_str} to {to_date_str}",
                    from_date_str,
                    to_date_str,
                    sales_result['date_range']['days'],
                    len(export_data),
                    sum(1 for item in export_data if item['Quantity Sold'] > 0),
                    sum(item['Quantity Sold'] for item in export_data),
                    f"${total_sales_value:,.2f}",
                    sales_result['stores_processed'],
                    sales_result['tag_used']
                ]
            }
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, index=False, sheet_name='Summary')

        output.seek(0)

        # Generate filename with date range
        filename = f'sc_sales_report_{from_date_str}_to_{to_date_str}.xlsx'

        # Return file as download
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        print(f"SC Sales export error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Error exporting report: {str(e)}'}), 500


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
