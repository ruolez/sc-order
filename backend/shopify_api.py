import requests
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta


class ShopifyAPI:
    """Shopify Admin GraphQL API integration."""

    def __init__(self, store_url: str, access_token: str):
        """
        Initialize Shopify API client.

        Args:
            store_url: Shopify store URL (e.g., 'your-store.myshopify.com')
            access_token: Admin API access token
        """
        self.store_url = store_url.replace('https://', '').replace('http://', '')
        self.access_token = access_token
        self.graphql_url = f"https://{self.store_url}/admin/api/2025-01/graphql.json"

    def _execute_query(self, query: str, variables: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Execute a GraphQL query against Shopify Admin API.

        Args:
            query: GraphQL query string
            variables: Optional variables for the query

        Returns:
            Response data dictionary

        Raises:
            Exception: If the request fails
        """
        headers = {
            'Content-Type': 'application/json',
            'X-Shopify-Access-Token': self.access_token
        }

        payload = {'query': query}
        if variables:
            payload['variables'] = variables

        response = requests.post(
            self.graphql_url,
            json=payload,
            headers=headers,
            timeout=30
        )

        if response.status_code != 200:
            raise Exception(f"Shopify API request failed: {response.status_code} - {response.text}")

        data = response.json()

        if 'errors' in data:
            error_messages = [error.get('message', str(error)) for error in data['errors']]
            raise Exception(f"GraphQL errors: {', '.join(error_messages)}")

        return data.get('data', {})

    def test_connection(self) -> Dict[str, Any]:
        """
        Test the Shopify API connection.

        Returns:
            Shop information if successful
        """
        query = """
        {
            shop {
                name
                email
                currencyCode
                primaryDomain {
                    url
                }
            }
        }
        """

        return self._execute_query(query)

    def get_locations(self) -> List[Dict[str, Any]]:
        """
        Get all locations from Shopify store.

        Returns:
            List of location dictionaries with id and name
        """
        query = """
        {
            locations(first: 50) {
                edges {
                    node {
                        id
                        name
                        address {
                            city
                            province
                            country
                        }
                    }
                }
            }
        }
        """

        data = self._execute_query(query)
        locations = []

        for edge in data.get('locations', {}).get('edges', []):
            node = edge['node']
            locations.append({
                'id': node['id'],
                'name': node['name'],
                'address': node.get('address', {})
            })

        return locations

    def get_inventory_by_location(self, location_id: str) -> List[Dict[str, Any]]:
        """
        Get inventory levels for all products at a specific location.

        Args:
            location_id: Shopify location ID (e.g., 'gid://shopify/Location/123')

        Returns:
            List of inventory items with SKU, quantity, and product info
        """
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

        all_inventory = []
        cursor = None
        has_next_page = True

        while has_next_page:
            variables = {'locationId': location_id}
            if cursor:
                variables['cursor'] = cursor

            data = self._execute_query(query, variables)
            location_data = data.get('location', {})
            inventory_levels = location_data.get('inventoryLevels', {})

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

                all_inventory.append({
                    'inventory_level_id': node['id'],
                    'inventory_item_id': item.get('id'),
                    'sku': variant.get('sku') or item.get('sku'),
                    'barcode': variant.get('barcode'),
                    'variant_title': variant.get('title'),
                    'product_title': product.get('title'),
                    'product_id': product.get('id'),
                    'variant_id': variant.get('id'),
                    'available_quantity': available_qty
                })

            # Check for next page
            page_info = inventory_levels.get('pageInfo', {})
            has_next_page = page_info.get('hasNextPage', False)
            cursor = page_info.get('endCursor')

        return all_inventory

    def get_inventory_by_sku(self, location_id: str, sku: str) -> Optional[Dict[str, Any]]:
        """
        Get inventory level for a specific SKU at a location.

        Args:
            location_id: Shopify location ID
            sku: Product SKU/barcode to search for

        Returns:
            Inventory data if found, None otherwise
        """
        # Get all inventory and filter by SKU
        all_inventory = self.get_inventory_by_location(location_id)

        for item in all_inventory:
            if item['sku'] == sku:
                return item

        return None

    def get_variant_inventory_by_sku(self, sku: str, location_id: str) -> Optional[Dict[str, Any]]:
        """
        Get inventory level for a specific product variant by SKU at a location.
        Uses optimized GraphQL query to search for specific SKU.

        Args:
            sku: Product SKU (barcode) to search for
            location_id: Shopify location ID (e.g., 'gid://shopify/Location/123')

        Returns:
            Dictionary with available_quantity and variant info if found, None otherwise
        """
        query = """
        query GetVariantInventory($sku: String!, $locationId: ID!) {
          productVariants(first: 1, query: $sku) {
            edges {
              node {
                id
                sku
                inventoryItem {
                  id
                  inventoryLevel(locationId: $locationId) {
                    quantities(names: "available") {
                      quantity
                      name
                    }
                  }
                }
              }
            }
          }
        }
        """

        variables = {
            'sku': f'sku:{sku}',
            'locationId': location_id
        }

        try:
            data = self._execute_query(query, variables)
            edges = data.get('productVariants', {}).get('edges', [])

            if not edges:
                return None

            node = edges[0]['node']
            inventory_item = node.get('inventoryItem', {})
            inventory_level = inventory_item.get('inventoryLevel')

            if not inventory_level:
                return None

            quantities = inventory_level.get('quantities', [])
            available_qty = 0

            for qty in quantities:
                if qty['name'] == 'available':
                    available_qty = qty['quantity']
                    break

            return {
                'variant_id': node['id'],
                'sku': node['sku'],
                'available_quantity': available_qty
            }

        except Exception as e:
            print(f"Error fetching inventory for SKU {sku}: {e}")
            return None

    def get_bulk_variant_inventory_by_skus(self, skus: List[str], location_id: str) -> Dict[str, int]:
        """
        Get inventory levels for multiple product variants by SKUs at a location in a single request.
        Uses Shopify OR query syntax to batch multiple SKUs together for better performance.

        Args:
            skus: List of product SKUs (barcodes) to search for (recommended max 50-100 per batch)
            location_id: Shopify location ID (e.g., 'gid://shopify/Location/123')

        Returns:
            Dictionary mapping SKU to available_quantity: {sku: quantity}
            SKUs not found in Shopify are not included in the result
        """
        if not skus:
            return {}

        # Build OR query: "sku:ABC OR sku:DEF OR sku:GHI"
        query_parts = [f'sku:{sku}' for sku in skus]
        query_string = ' OR '.join(query_parts)

        query = """
        query GetBulkInventory($query: String!, $locationId: ID!) {
          productVariants(first: 250, query: $query) {
            edges {
              node {
                id
                sku
                inventoryItem {
                  id
                  inventoryLevel(locationId: $locationId) {
                    quantities(names: "available") {
                      quantity
                      name
                    }
                  }
                }
              }
            }
          }
        }
        """

        variables = {
            'query': query_string,
            'locationId': location_id
        }

        try:
            data = self._execute_query(query, variables)
            edges = data.get('productVariants', {}).get('edges', [])

            # Build dictionary mapping SKU to available quantity
            results = {}
            for edge in edges:
                node = edge['node']
                sku = node.get('sku')

                if not sku:
                    continue

                inventory_item = node.get('inventoryItem', {})
                inventory_level = inventory_item.get('inventoryLevel')

                if not inventory_level:
                    results[sku] = 0
                    continue

                quantities = inventory_level.get('quantities', [])
                available_qty = 0

                for qty in quantities:
                    if qty['name'] == 'available':
                        available_qty = qty['quantity']
                        break

                results[sku] = available_qty

            return results

        except Exception as e:
            print(f"Error fetching bulk inventory for {len(skus)} SKUs: {e}")
            return {}

    def match_products_with_inventory(
        self,
        products: List[Dict[str, Any]],
        location_id: str
    ) -> List[Dict[str, Any]]:
        """
        Match internal products with Shopify inventory levels.

        Args:
            products: List of internal products with upc_barcode field
            location_id: Shopify location ID

        Returns:
            List of products with Shopify inventory data added
        """
        # Get all inventory from Shopify
        shopify_inventory = self.get_inventory_by_location(location_id)

        # Create SKU lookup dictionary
        inventory_by_sku = {item['sku']: item for item in shopify_inventory if item['sku']}

        # Match products
        matched_products = []
        for product in products:
            product_copy = product.copy()
            upc_barcode = product.get('upc_barcode')

            if upc_barcode and upc_barcode in inventory_by_sku:
                shopify_data = inventory_by_sku[upc_barcode]
                product_copy['shopify_available'] = shopify_data['available_quantity']
                product_copy['shopify_product_title'] = shopify_data['product_title']
                product_copy['shopify_variant_title'] = shopify_data['variant_title']
                product_copy['shopify_matched'] = True
            else:
                product_copy['shopify_available'] = None
                product_copy['shopify_matched'] = False

            matched_products.append(product_copy)

        return matched_products

    def get_sales_by_location_last_month(self, location_id: str, days: int = 30, page_size: int = 250, progress_callback=None) -> Dict[str, int]:
        """
        Get aggregated sales quantities by SKU for a specific location in the last N days.
        Optimized with larger page size for better performance.

        Args:
            location_id: Shopify location ID (e.g., 'gid://shopify/Location/123')
            days: Number of days to look back (default: 30)
            page_size: Number of orders per page (default: 250, max: 250)
            progress_callback: Optional callback function(page_num, total_orders) for progress updates

        Returns:
            Dictionary mapping SKU to total quantity sold: {sku: quantity}
        """
        # Calculate date threshold
        date_threshold = datetime.now() - timedelta(days=days)
        date_filter = date_threshold.strftime('%Y-%m-%dT%H:%M:%SZ')

        query = """
        query GetOrdersByDate($cursor: String, $dateQuery: String, $pageSize: Int!) {
            orders(first: $pageSize, after: $cursor, query: $dateQuery) {
                pageInfo {
                    hasNextPage
                    endCursor
                }
                edges {
                    node {
                        id
                        createdAt
                        fulfillmentOrders(first: 10) {
                            edges {
                                node {
                                    id
                                    assignedLocation {
                                        location {
                                            id
                                        }
                                    }
                                    lineItems(first: 50) {
                                        edges {
                                            node {
                                                sku
                                                totalQuantity
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        """

        sales_by_sku = {}
        cursor = None
        has_next_page = True
        page_num = 0
        total_orders_processed = 0

        while has_next_page:
            variables = {
                'dateQuery': f'created_at:>={date_filter}',
                'pageSize': page_size
            }
            if cursor:
                variables['cursor'] = cursor

            try:
                data = self._execute_query(query, variables)
                orders_connection = data.get('orders', {})
                page_num += 1
                orders_in_page = len(orders_connection.get('edges', []))
                total_orders_processed += orders_in_page

                for order_edge in orders_connection.get('edges', []):
                    order_node = order_edge['node']
                    fulfillment_orders = order_node.get('fulfillmentOrders', {}).get('edges', [])

                    for fo_edge in fulfillment_orders:
                        fo_node = fo_edge['node']
                        assigned_location = fo_node.get('assignedLocation', {})
                        fo_location = assigned_location.get('location', {})
                        fo_location_id = fo_location.get('id')

                        # Only count sales from the specified location
                        if fo_location_id == location_id:
                            line_items = fo_node.get('lineItems', {}).get('edges', [])

                            for li_edge in line_items:
                                li_node = li_edge['node']
                                sku = li_node.get('sku')
                                quantity = li_node.get('totalQuantity', 0)

                                if sku:
                                    sales_by_sku[sku] = sales_by_sku.get(sku, 0) + quantity

                # Report progress if callback provided
                if progress_callback:
                    progress_callback(page_num, total_orders_processed)

                # Check for next page
                page_info = orders_connection.get('pageInfo', {})
                has_next_page = page_info.get('hasNextPage', False)
                cursor = page_info.get('endCursor')

            except Exception as e:
                print(f"Error fetching sales data: {e}")
                break

        return sales_by_sku

    def get_sales_last_month(self, days: int = 30, page_size: int = 250) -> Dict[str, int]:
        """
        Get aggregated sales quantities by SKU for ALL locations in the last N days.
        Optimized with larger page size for better performance.

        Args:
            days: Number of days to look back (default: 30)
            page_size: Number of orders per page (default: 250, max: 250)

        Returns:
            Dictionary mapping SKU to total quantity sold: {sku: quantity}
        """
        # Calculate date threshold
        date_threshold = datetime.now() - timedelta(days=days)
        date_filter = date_threshold.strftime('%Y-%m-%dT%H:%M:%SZ')

        query = """
        query GetOrdersByDate($cursor: String, $dateQuery: String, $pageSize: Int!) {
            orders(first: $pageSize, after: $cursor, query: $dateQuery) {
                pageInfo {
                    hasNextPage
                    endCursor
                }
                edges {
                    node {
                        id
                        createdAt
                        lineItems(first: 250) {
                            edges {
                                node {
                                    sku
                                    quantity
                                }
                            }
                        }
                    }
                }
            }
        }
        """

        sales_by_sku = {}
        cursor = None
        has_next_page = True

        while has_next_page:
            variables = {
                'dateQuery': f'created_at:>={date_filter}',
                'pageSize': page_size
            }
            if cursor:
                variables['cursor'] = cursor

            try:
                data = self._execute_query(query, variables)
                orders_connection = data.get('orders', {})

                for order_edge in orders_connection.get('edges', []):
                    order_node = order_edge['node']
                    line_items = order_node.get('lineItems', {}).get('edges', [])

                    for li_edge in line_items:
                        li_node = li_edge['node']
                        sku = li_node.get('sku')
                        quantity = li_node.get('quantity', 0)

                        if sku:
                            sales_by_sku[sku] = sales_by_sku.get(sku, 0) + quantity

                # Check for next page
                page_info = orders_connection.get('pageInfo', {})
                has_next_page = page_info.get('hasNextPage', False)
                cursor = page_info.get('endCursor')

            except Exception as e:
                print(f"Error fetching sales data: {e}")
                break

        return sales_by_sku

    def get_sales_by_skus_and_tag(self, skus: List[str], order_tag: str, from_date=None, to_date=None, days: int = None, page_size: int = 250, progress_callback=None) -> Dict[str, int]:
        """
        Get aggregated sales quantities by SKU filtered by order tag for a date range.
        Uses batch SKU filtering with OR syntax for optimal performance.

        This method is optimized for speed by:
        1. Server-side filtering by tag (Shopify does the work)
        2. Batch SKU filtering (only fetch orders with relevant products)
        3. Simplified query structure (no fulfillmentOrders needed)

        Args:
            skus: List of product SKUs to search for (recommended max 50 per batch)
            order_tag: Tag to filter orders by (e.g., "warehouse-main")
            from_date: Optional datetime object for start of date range
            to_date: Optional datetime object for end of date range
            days: Optional number of days to look back (used if from_date/to_date not provided)
            page_size: Number of orders per page (default: 250, max: 250)
            progress_callback: Optional callback function(page_num, total_orders) for progress updates

        Returns:
            Dictionary mapping SKU to total quantity sold: {sku: quantity}
        """
        if not skus or not order_tag:
            return {}

        # Build date filter based on parameters
        if from_date and to_date:
            # Use custom date range
            from_filter = from_date.strftime('%Y-%m-%dT%H:%M:%SZ')
            to_filter = to_date.strftime('%Y-%m-%dT%H:%M:%SZ')
            date_query = f'created_at:>={from_filter} AND created_at:<={to_filter}'
        elif days:
            # Use days parameter (backward compatible)
            date_threshold = datetime.now() - timedelta(days=days)
            date_filter = date_threshold.strftime('%Y-%m-%dT%H:%M:%SZ')
            date_query = f'created_at:>={date_filter}'
        else:
            # Default to last 30 days if no parameters provided
            date_threshold = datetime.now() - timedelta(days=30)
            date_filter = date_threshold.strftime('%Y-%m-%dT%H:%M:%SZ')
            date_query = f'created_at:>={date_filter}'

        # Build query: "created_at filters AND tag:TAG AND (sku:A OR sku:B OR ...)"
        sku_query = ' OR '.join([f'sku:{sku}' for sku in skus])
        query_string = f'{date_query} AND tag:{order_tag} AND ({sku_query})'

        # Simplified GraphQL query - no fulfillmentOrders needed!
        query = """
        query GetOrdersByTagAndSKUs($cursor: String, $query: String, $pageSize: Int!) {
            orders(first: $pageSize, after: $cursor, query: $query) {
                pageInfo {
                    hasNextPage
                    endCursor
                }
                edges {
                    node {
                        id
                        createdAt
                        lineItems(first: 250) {
                            edges {
                                node {
                                    sku
                                    quantity
                                }
                            }
                        }
                    }
                }
            }
        }
        """

        sales_by_sku = {}
        cursor = None
        has_next_page = True
        page_num = 0
        total_orders_processed = 0

        while has_next_page:
            variables = {
                'query': query_string,
                'pageSize': page_size
            }
            if cursor:
                variables['cursor'] = cursor

            try:
                data = self._execute_query(query, variables)
                orders_connection = data.get('orders', {})
                page_num += 1
                orders_in_page = len(orders_connection.get('edges', []))
                total_orders_processed += orders_in_page

                # Process line items from each order
                for order_edge in orders_connection.get('edges', []):
                    order_node = order_edge['node']
                    line_items = order_node.get('lineItems', {}).get('edges', [])

                    for li_edge in line_items:
                        li_node = li_edge['node']
                        sku = li_node.get('sku')
                        quantity = li_node.get('quantity', 0)

                        if sku:
                            sales_by_sku[sku] = sales_by_sku.get(sku, 0) + quantity

                # Report progress if callback provided
                if progress_callback:
                    progress_callback(page_num, total_orders_processed)

                # Check for next page
                page_info = orders_connection.get('pageInfo', {})
                has_next_page = page_info.get('hasNextPage', False)
                cursor = page_info.get('endCursor')

            except Exception as e:
                print(f"Error fetching sales data: {e}")
                break

        return sales_by_sku


def create_shopify_client(settings: Dict[str, Any]) -> Optional[ShopifyAPI]:
    """
    Create a Shopify API client from settings.

    Args:
        settings: Settings dictionary with shopify_store_url and shopify_access_token

    Returns:
        ShopifyAPI instance or None if settings are incomplete
    """
    store_url = settings.get('shopify_store_url')
    access_token = settings.get('shopify_access_token')

    if not store_url or not access_token:
        return None

    return ShopifyAPI(store_url, access_token)
