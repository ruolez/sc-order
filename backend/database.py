import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any
import os

DATABASE_FILE = os.getenv('DATABASE_PATH', '/app/data/inventory.db')


def get_connection():
    """Get a database connection."""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """Initialize the database with required tables."""
    conn = get_connection()
    cursor = conn.cursor()

    # Settings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY,
            shopify_store_url TEXT,
            shopify_access_token TEXT,
            shopify_location_id TEXT,
            mssql_server TEXT,
            mssql_database TEXT,
            mssql_username TEXT,
            mssql_password TEXT,
            mssql_port INTEGER DEFAULT 1433
        )
    ''')

    # Insert default settings row if not exists
    cursor.execute('SELECT COUNT(*) FROM settings')
    if cursor.fetchone()[0] == 0:
        cursor.execute('INSERT INTO settings (id) VALUES (1)')

    # Products table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT NOT NULL,
            upc_barcode TEXT UNIQUE NOT NULL,
            threshold_quantity INTEGER,
            quantity_per_case INTEGER,
            price REAL,
            available_quantity INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Add available_quantity column if it doesn't exist (migration for existing databases)
    cursor.execute("PRAGMA table_info(products)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'available_quantity' not in columns:
        cursor.execute('ALTER TABLE products ADD COLUMN available_quantity INTEGER')

    # Add excluded_skus column to settings if it doesn't exist (migration for existing databases)
    cursor.execute("PRAGMA table_info(settings)")
    settings_columns = [column[1] for column in cursor.fetchall()]
    if 'excluded_skus' not in settings_columns:
        cursor.execute('ALTER TABLE settings ADD COLUMN excluded_skus TEXT')

    # Add quantity_sold_last_month column to products if it doesn't exist (migration for existing databases)
    cursor.execute("PRAGMA table_info(products)")
    products_columns = [column[1] for column in cursor.fetchall()]
    if 'quantity_sold_last_month' not in products_columns:
        cursor.execute('ALTER TABLE products ADD COLUMN quantity_sold_last_month INTEGER')

    # Add additional Shopify store columns for multi-store sales sync (stores 2-5)
    cursor.execute("PRAGMA table_info(settings)")
    settings_columns = [column[1] for column in cursor.fetchall()]

    additional_store_columns = [
        'shopify_store_2_url', 'shopify_store_2_token', 'shopify_store_2_location_id',
        'shopify_store_3_url', 'shopify_store_3_token', 'shopify_store_3_location_id',
        'shopify_store_4_url', 'shopify_store_4_token', 'shopify_store_4_location_id',
        'shopify_store_5_url', 'shopify_store_5_token', 'shopify_store_5_location_id'
    ]

    for column in additional_store_columns:
        if column not in settings_columns:
            cursor.execute(f'ALTER TABLE settings ADD COLUMN {column} TEXT')

    # Add sales_order_tag column to settings if it doesn't exist (migration for tag-based sales filtering)
    cursor.execute("PRAGMA table_info(settings)")
    settings_columns = [column[1] for column in cursor.fetchall()]
    if 'sales_order_tag' not in settings_columns:
        cursor.execute('ALTER TABLE settings ADD COLUMN sales_order_tag TEXT')

    # Add sales_sync_days column to settings if it doesn't exist (migration for configurable sales sync period)
    cursor.execute("PRAGMA table_info(settings)")
    settings_columns = [column[1] for column in cursor.fetchall()]
    if 'sales_sync_days' not in settings_columns:
        cursor.execute('ALTER TABLE settings ADD COLUMN sales_sync_days INTEGER DEFAULT 30')

    conn.commit()
    conn.close()


def get_settings() -> Optional[Dict[str, Any]]:
    """Get application settings."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM settings WHERE id = 1')
    row = cursor.fetchone()
    conn.close()

    if row:
        return dict(row)
    return None


def update_settings(settings: Dict[str, Any]) -> bool:
    """Update application settings."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE settings
        SET shopify_store_url = ?,
            shopify_access_token = ?,
            shopify_location_id = ?,
            mssql_server = ?,
            mssql_database = ?,
            mssql_username = ?,
            mssql_password = ?,
            mssql_port = ?,
            excluded_skus = ?,
            shopify_store_2_url = ?,
            shopify_store_2_token = ?,
            shopify_store_2_location_id = ?,
            shopify_store_3_url = ?,
            shopify_store_3_token = ?,
            shopify_store_3_location_id = ?,
            shopify_store_4_url = ?,
            shopify_store_4_token = ?,
            shopify_store_4_location_id = ?,
            shopify_store_5_url = ?,
            shopify_store_5_token = ?,
            shopify_store_5_location_id = ?,
            sales_order_tag = ?,
            sales_sync_days = ?
        WHERE id = 1
    ''', (
        settings.get('shopify_store_url'),
        settings.get('shopify_access_token'),
        settings.get('shopify_location_id'),
        settings.get('mssql_server'),
        settings.get('mssql_database'),
        settings.get('mssql_username'),
        settings.get('mssql_password'),
        settings.get('mssql_port', 1433),
        settings.get('excluded_skus', ''),
        settings.get('shopify_store_2_url'),
        settings.get('shopify_store_2_token'),
        settings.get('shopify_store_2_location_id'),
        settings.get('shopify_store_3_url'),
        settings.get('shopify_store_3_token'),
        settings.get('shopify_store_3_location_id'),
        settings.get('shopify_store_4_url'),
        settings.get('shopify_store_4_token'),
        settings.get('shopify_store_4_location_id'),
        settings.get('shopify_store_5_url'),
        settings.get('shopify_store_5_token'),
        settings.get('shopify_store_5_location_id'),
        settings.get('sales_order_tag', ''),
        settings.get('sales_sync_days', 30)
    ))

    conn.commit()
    conn.close()
    return True


def get_products() -> List[Dict[str, Any]]:
    """Get all products."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM products ORDER BY product_name')
    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_product(product_id: int) -> Optional[Dict[str, Any]]:
    """Get a single product by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM products WHERE id = ?', (product_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return dict(row)
    return None


def create_product(product: Dict[str, Any]) -> int:
    """Create a new product."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO products (product_name, upc_barcode, threshold_quantity, quantity_per_case, price)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        product['product_name'],
        product['upc_barcode'],
        product.get('threshold_quantity'),
        product.get('quantity_per_case'),
        product.get('price')
    ))

    product_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return product_id


def update_product(product_id: int, product: Dict[str, Any]) -> bool:
    """Update an existing product."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE products
        SET product_name = ?,
            upc_barcode = ?,
            threshold_quantity = ?,
            quantity_per_case = ?,
            price = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (
        product['product_name'],
        product['upc_barcode'],
        product.get('threshold_quantity'),
        product.get('quantity_per_case'),
        product.get('price'),
        product_id
    ))

    conn.commit()
    conn.close()
    return cursor.rowcount > 0


def update_product_available_quantity(product_id: int, available_quantity: Optional[int]) -> bool:
    """Update the available quantity for a product."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE products
        SET available_quantity = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (available_quantity, product_id))

    conn.commit()
    conn.close()
    return cursor.rowcount > 0


def update_product_price(product_id: int, price: Optional[float]) -> bool:
    """Update the price for a product."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE products
        SET price = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (price, product_id))

    conn.commit()
    conn.close()
    return cursor.rowcount > 0


def bulk_update_prices(updates: List[tuple]) -> bool:
    """Update multiple products' prices in a single transaction.

    Args:
        updates: List of (product_id, price) tuples

    Returns:
        True if successful
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executemany('''
        UPDATE products
        SET price = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', [(price, pid) for pid, price in updates])

    conn.commit()
    conn.close()
    return True


def update_product_sales_last_month(product_id: int, quantity: Optional[int]) -> bool:
    """Update the quantity sold in the last month for a product."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE products
        SET quantity_sold_last_month = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (quantity, product_id))

    conn.commit()
    conn.close()
    return cursor.rowcount > 0


def bulk_update_sales(updates: List[tuple]) -> bool:
    """Update multiple products' sales quantities in a single transaction.

    Args:
        updates: List of (product_id, quantity_sold_last_month) tuples

    Returns:
        True if successful
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executemany('''
        UPDATE products
        SET quantity_sold_last_month = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', [(qty, pid) for pid, qty in updates])

    conn.commit()
    conn.close()
    return True


def bulk_update_inventory(updates: List[tuple]) -> bool:
    """Update multiple products' available quantities in a single transaction.

    Args:
        updates: List of (product_id, available_quantity) tuples

    Returns:
        True if successful
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executemany('''
        UPDATE products
        SET available_quantity = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', [(qty, pid) for pid, qty in updates])

    conn.commit()
    conn.close()
    return True


def delete_product(product_id: int) -> bool:
    """Delete a product."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM products WHERE id = ?', (product_id,))
    conn.commit()
    conn.close()
    return cursor.rowcount > 0


def delete_all_products() -> int:
    """Delete all products and return count of deleted rows."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM products')
    count = cursor.fetchone()[0]
    cursor.execute('DELETE FROM products')
    conn.commit()
    conn.close()
    return count


def clear_column_data(column_name: str) -> int:
    """Clear (set to NULL) a specific column for all products.

    Args:
        column_name: Name of the column to clear. Must be in the whitelist.

    Returns:
        Count of products updated.

    Raises:
        ValueError: If column_name is not in the whitelist.
    """
    # Whitelist of allowed columns to prevent SQL injection
    allowed_columns = [
        'threshold_quantity',
        'quantity_per_case',
        'price',
        'available_quantity',
        'quantity_sold_last_month'
    ]

    if column_name not in allowed_columns:
        raise ValueError(f"Column '{column_name}' is not allowed. Must be one of: {', '.join(allowed_columns)}")

    conn = get_connection()
    cursor = conn.cursor()

    # Count products before clearing
    cursor.execute('SELECT COUNT(*) FROM products')
    count = cursor.fetchone()[0]

    # Clear the column (set to NULL)
    cursor.execute(f'UPDATE products SET {column_name} = NULL, updated_at = CURRENT_TIMESTAMP')

    conn.commit()
    conn.close()
    return count


def bulk_insert_products(products: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Bulk insert products, handling duplicates."""
    conn = get_connection()
    cursor = conn.cursor()

    inserted = 0
    skipped = 0
    errors = []

    for product in products:
        try:
            cursor.execute('''
                INSERT INTO products (product_name, upc_barcode, threshold_quantity, quantity_per_case, price)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                product.get('product_name'),
                product.get('upc_barcode'),
                product.get('threshold_quantity'),
                product.get('quantity_per_case'),
                product.get('price')
            ))
            inserted += 1
        except sqlite3.IntegrityError:
            skipped += 1
        except Exception as e:
            errors.append(f"Error inserting {product.get('upc_barcode')}: {str(e)}")

    conn.commit()
    conn.close()

    return {
        'inserted': inserted,
        'skipped': skipped,
        'errors': errors
    }


if __name__ == '__main__':
    # Initialize database when run directly
    init_database()
    print('Database initialized successfully!')
