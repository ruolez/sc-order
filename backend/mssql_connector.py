import pyodbc
from typing import Optional, Dict, List, Any


class MSSQLConnector:
    """Microsoft SQL Server connection manager."""

    def __init__(
        self,
        server: str,
        database: str,
        username: str,
        password: str,
        port: int = 1433
    ):
        """
        Initialize MS SQL connector.

        Args:
            server: SQL Server address
            database: Database name
            username: SQL Server username
            password: SQL Server password
            port: SQL Server port (default: 1433)
        """
        self.server = server
        self.database = database
        self.username = username
        self.password = password
        self.port = port
        self.connection = None

    def _get_connection_string(self) -> str:
        """
        Build ODBC connection string.

        Returns:
            Connection string for pyodbc
        """
        # For older SQL Server with older TLS protocols, use FreeTDS driver
        # FreeTDS is more compatible with SQL Server 2012 and earlier
        connection_string = (
            f'DRIVER={{FreeTDS}};'
            f'SERVER={self.server};'
            f'PORT={self.port};'
            f'DATABASE={self.database};'
            f'UID={self.username};'
            f'PWD={self.password};'
            f'TDS_Version=7.2;'  # TDS 7.2 for SQL Server 2008/2012
        )

        return connection_string

    def connect(self) -> None:
        """
        Establish connection to MS SQL Server.

        Raises:
            Exception: If connection fails
        """
        try:
            connection_string = self._get_connection_string()
            self.connection = pyodbc.connect(connection_string, timeout=10)
        except pyodbc.Error as e:
            raise Exception(f"Failed to connect to MS SQL Server: {str(e)}")

    def disconnect(self) -> None:
        """Close the database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None

    def test_connection(self) -> Dict[str, Any]:
        """
        Test the MS SQL Server connection.

        Returns:
            Dictionary with connection status and server info

        Raises:
            Exception: If connection test fails
        """
        try:
            self.connect()

            # Get SQL Server version
            cursor = self.connection.cursor()
            cursor.execute("SELECT @@VERSION as version, DB_NAME() as database_name")
            row = cursor.fetchone()

            result = {
                'status': 'connected',
                'version': row.version if row else 'Unknown',
                'database': row.database_name if row else self.database,
                'server': self.server
            }

            cursor.close()
            return result

        except Exception as e:
            raise Exception(f"Connection test failed: {str(e)}")
        finally:
            self.disconnect()

    def execute_query(
        self,
        query: str,
        params: Optional[tuple] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute a SELECT query and return results.

        Args:
            query: SQL SELECT query
            params: Optional query parameters

        Returns:
            List of row dictionaries

        Raises:
            Exception: If query execution fails
        """
        try:
            if not self.connection:
                self.connect()

            cursor = self.connection.cursor()

            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            # Get column names
            columns = [column[0] for column in cursor.description]

            # Fetch all rows and convert to dictionaries
            results = []
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))

            cursor.close()
            return results

        except pyodbc.Error as e:
            raise Exception(f"Query execution failed: {str(e)}")

    def get_inventory_by_upc(self, upc_barcode: str) -> Optional[Dict[str, Any]]:
        """
        Get inventory data for a specific UPC barcode.

        Note: This is a placeholder query. You'll need to provide the actual
        table schema and column names for your MS SQL database.

        Args:
            upc_barcode: UPC barcode to search for

        Returns:
            Inventory data dictionary or None if not found
        """
        query = """
        SELECT
            product_upc,
            product_name,
            quantity_on_hand,
            quantity_available,
            unit_price
        FROM inventory
        WHERE product_upc = ?
        """

        try:
            results = self.execute_query(query, (upc_barcode,))
            return results[0] if results else None
        except Exception as e:
            # If the query fails (table doesn't exist, wrong columns, etc.)
            # Return None or raise the exception
            raise Exception(f"Failed to get inventory by UPC: {str(e)}")

    def get_price_by_upc(self, upc_barcode: str) -> Optional[float]:
        """
        Get UnitPriceC from Items_tbl for a specific UPC barcode.

        Args:
            upc_barcode: UPC barcode to search for

        Returns:
            Price (UnitPriceC) or None if not found
        """
        query = """
        SELECT UnitPriceC
        FROM Items_tbl
        WHERE ProductUPC = ?
        """

        try:
            results = self.execute_query(query, (upc_barcode,))
            if results and results[0].get('UnitPriceC') is not None:
                return float(results[0]['UnitPriceC'])
            return None
        except Exception as e:
            raise Exception(f"Failed to get price by UPC: {str(e)}")

    def get_bulk_prices_by_upcs(self, upcs: List[str]) -> Dict[str, float]:
        """
        Get prices for multiple UPC barcodes in a single query using batch processing.
        Uses SQL IN clause for better performance.

        Args:
            upcs: List of UPC barcodes to search for (recommended max 50 per batch)

        Returns:
            Dictionary mapping UPC to price: {upc: price}
            UPCs not found in Items_tbl are not included in the result
        """
        if not upcs:
            return {}

        try:
            # Build parameterized IN clause: WHERE ProductUPC IN (?, ?, ?, ...)
            placeholders = ','.join(['?' for _ in upcs])
            query = f"""
            SELECT ProductUPC, UnitPriceC
            FROM Items_tbl
            WHERE ProductUPC IN ({placeholders})
            """

            results = self.execute_query(query, tuple(upcs))

            # Build dictionary mapping UPC to price
            price_map = {}
            for row in results:
                upc = row.get('ProductUPC')
                price = row.get('UnitPriceC')

                if upc and price is not None:
                    price_map[upc] = float(price)

            return price_map

        except Exception as e:
            print(f"Error fetching bulk prices for {len(upcs)} UPCs: {e}")
            return {}

    def search_customers(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search customers by AccountNo with LIKE query.

        Args:
            query: Search query for AccountNo
            limit: Maximum number of results (default: 20)

        Returns:
            List of customer dictionaries with CustomerID, AccountNo, BusinessName
        """
        if not query:
            return []

        try:
            sql_query = """
            SELECT TOP (?) CustomerID, AccountNo, BusinessName
            FROM Customers_tbl
            WHERE AccountNo LIKE ?
            ORDER BY AccountNo
            """

            results = self.execute_query(sql_query, (limit, f"%{query}%"))
            return results

        except Exception as e:
            print(f"Error searching customers: {e}")
            return []

    def get_customer_by_id(self, customer_id: int) -> Optional[Dict[str, Any]]:
        """
        Get full customer record by CustomerID.

        Args:
            customer_id: Customer ID to fetch

        Returns:
            Customer dictionary with all fields or None if not found
        """
        try:
            query = """
            SELECT *
            FROM Customers_tbl
            WHERE CustomerID = ?
            """

            results = self.execute_query(query, (customer_id,))
            return results[0] if results else None

        except Exception as e:
            print(f"Error fetching customer {customer_id}: {e}")
            return None

    def get_next_quotation_number(self) -> str:
        """
        Get next quotation number by finding max and adding 1.

        Returns:
            Next quotation number as string
        """
        try:
            query = """
            SELECT TOP 1 QuotationNumber
            FROM Quotations_tbl
            ORDER BY QuotationID DESC
            """

            results = self.execute_query(query)

            if results and results[0].get('QuotationNumber'):
                last_number = results[0]['QuotationNumber']
                try:
                    next_number = int(last_number) + 1
                    return str(next_number)
                except ValueError:
                    # If QuotationNumber is not numeric, generate based on timestamp
                    from datetime import datetime
                    return datetime.now().strftime("%Y%m%d%H%M%S")
            else:
                # No quotations exist, start with 1001202500
                return "1001202500"

        except Exception as e:
            print(f"Error getting next quotation number: {e}")
            from datetime import datetime
            return datetime.now().strftime("%Y%m%d%H%M%S")

    def get_item_details_by_upc(self, upc: str) -> Optional[Dict[str, Any]]:
        """
        Get full item details from Items_tbl by ProductUPC.
        Joins with Units_tbl to get UnitDesc.

        Args:
            upc: UPC barcode to search for

        Returns:
            Item dictionary with all fields or None if not found
        """
        try:
            query = """
            SELECT i.*, u.UnitDesc
            FROM Items_tbl i
            LEFT JOIN Units_tbl u ON i.UnitID = u.UnitID
            WHERE i.ProductUPC = ?
            """

            results = self.execute_query(query, (upc,))
            return results[0] if results else None

        except Exception as e:
            print(f"Error fetching item details for UPC {upc}: {e}")
            return None

    def get_bulk_item_details_by_upcs(self, upcs: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Get full item details for multiple UPC barcodes in a single query.
        Joins with Units_tbl to get UnitDesc.

        Args:
            upcs: List of UPC barcodes to search for

        Returns:
            Dictionary mapping UPC to item details: {upc: item_dict}
        """
        if not upcs:
            return {}

        try:
            placeholders = ','.join(['?' for _ in upcs])
            query = f"""
            SELECT i.*, u.UnitDesc
            FROM Items_tbl i
            LEFT JOIN Units_tbl u ON i.UnitID = u.UnitID
            WHERE i.ProductUPC IN ({placeholders})
            """

            results = self.execute_query(query, tuple(upcs))

            # Build dictionary mapping UPC to item details
            item_map = {}
            for row in results:
                upc = row.get('ProductUPC')
                if upc:
                    item_map[upc] = row

            return item_map

        except Exception as e:
            print(f"Error fetching bulk item details for {len(upcs)} UPCs: {e}")
            return {}

    def insert_quotation(self, quotation_data: Dict[str, Any]) -> Optional[int]:
        """
        Insert a new quotation into Quotations_tbl.

        Args:
            quotation_data: Dictionary with quotation fields

        Returns:
            QuotationID of inserted record or None if failed
        """
        try:
            if not self.connection:
                self.connect()

            cursor = self.connection.cursor()

            # Build INSERT query
            query = """
            INSERT INTO Quotations_tbl (
                QuotationNumber, QuotationDate, QuotationTitle, PoNumber,
                AutoOrderNo, ExpirationDate, CustomerID, BusinessName, AccountNo,
                Shipto, ShipAddress1, ShipAddress2, ShipContact, ShipCity,
                ShipState, ShipZipCode, ShipPhoneNo, Status, ShipperID,
                SalesRepID, TermID, TotalTaxes, QuotationTotal, Header,
                Footer, Notes, Memo, flaged
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            );
            SELECT SCOPE_IDENTITY() AS QuotationID;
            """

            cursor.execute(query, (
                quotation_data.get('QuotationNumber'),
                quotation_data.get('QuotationDate'),
                quotation_data.get('QuotationTitle'),
                quotation_data.get('PoNumber'),
                quotation_data.get('AutoOrderNo'),
                quotation_data.get('ExpirationDate'),
                quotation_data.get('CustomerID'),
                quotation_data.get('BusinessName'),
                quotation_data.get('AccountNo'),
                quotation_data.get('Shipto'),
                quotation_data.get('ShipAddress1'),
                quotation_data.get('ShipAddress2'),
                quotation_data.get('ShipContact'),
                quotation_data.get('ShipCity'),
                quotation_data.get('ShipState'),
                quotation_data.get('ShipZipCode'),
                quotation_data.get('ShipPhoneNo'),
                quotation_data.get('Status', 0),
                quotation_data.get('ShipperID', 0),
                quotation_data.get('SalesRepID'),
                quotation_data.get('TermID'),
                quotation_data.get('TotalTaxes', 0.0),
                quotation_data.get('QuotationTotal'),
                quotation_data.get('Header'),
                quotation_data.get('Footer'),
                quotation_data.get('Notes'),
                quotation_data.get('Memo'),
                quotation_data.get('flaged', 0)
            ))

            # Get the QuotationID
            row = cursor.fetchone()
            quotation_id = int(row[0]) if row else None

            self.connection.commit()
            cursor.close()

            return quotation_id

        except Exception as e:
            if self.connection:
                self.connection.rollback()
            print(f"Error inserting quotation: {e}")
            return None

    def insert_quotation_details(self, quotation_id: int, line_items: List[Dict[str, Any]]) -> bool:
        """
        Insert quotation line items into QuotationsDetails_tbl.

        Args:
            quotation_id: QuotationID from Quotations_tbl
            line_items: List of line item dictionaries

        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.connection:
                self.connect()

            cursor = self.connection.cursor()

            query = """
            INSERT INTO QuotationsDetails_tbl (
                QuotationID, CateID, SubCateID, UnitDesc, UnitQty,
                ProductID, ProductSKU, ProductUPC, ProductDescription, ItemSize,
                ExpDate, ReasonID, LineMessage, UnitPrice, OriginalPrice,
                RememberPrice, UnitCost, Discount, ds_Percent, Qty,
                ItemWeight, ExtendedPrice, ExtendedDisc, ExtendedCost,
                PromotionID, PromotionLine, PromotionDescription, PromotionAmount,
                ActExtendedPrice, SPPromoted, SPPromotionDescription, Taxable,
                ItemTaxID, Catch, Comments, Flag
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """

            for item in line_items:
                cursor.execute(query, (
                    quotation_id,
                    item.get('CateID'),
                    item.get('SubCateID'),
                    item.get('UnitDesc'),
                    item.get('UnitQty', 1),
                    item.get('ProductID'),
                    item.get('ProductSKU'),
                    item.get('ProductUPC'),
                    item.get('ProductDescription'),
                    item.get('ItemSize'),
                    item.get('ExpDate'),
                    item.get('ReasonID'),
                    item.get('LineMessage'),
                    item.get('UnitPrice'),
                    item.get('OriginalPrice'),
                    item.get('RememberPrice'),
                    item.get('UnitCost'),
                    item.get('Discount', 0),
                    item.get('ds_Percent', 0),
                    item.get('Qty'),
                    item.get('ItemWeight'),
                    item.get('ExtendedPrice'),
                    item.get('ExtendedDisc', 0),
                    item.get('ExtendedCost'),
                    item.get('PromotionID'),
                    item.get('PromotionLine'),
                    item.get('PromotionDescription'),
                    item.get('PromotionAmount'),
                    item.get('ActExtendedPrice'),
                    item.get('SPPromoted'),
                    item.get('SPPromotionDescription'),
                    item.get('Taxable'),
                    item.get('ItemTaxID'),
                    item.get('Catch'),
                    item.get('Comments'),
                    item.get('Flag')
                ))

            self.connection.commit()
            cursor.close()

            return True

        except Exception as e:
            if self.connection:
                self.connection.rollback()
            print(f"Error inserting quotation details: {e}")
            return False

    def get_all_inventory(self) -> List[Dict[str, Any]]:
        """
        Get all inventory records from MS SQL database.

        Note: This is a placeholder query. You'll need to provide the actual
        table schema and column names for your MS SQL database.

        Returns:
            List of inventory dictionaries
        """
        query = """
        SELECT
            product_upc,
            product_name,
            quantity_on_hand,
            quantity_available,
            unit_price
        FROM inventory
        """

        try:
            return self.execute_query(query)
        except Exception as e:
            raise Exception(f"Failed to get all inventory: {str(e)}")

    def match_products_with_mssql(
        self,
        products: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Match internal products with MS SQL inventory data.

        Args:
            products: List of internal products with upc_barcode field

        Returns:
            List of products with MS SQL inventory data added
        """
        matched_products = []

        try:
            self.connect()

            for product in products:
                product_copy = product.copy()
                upc_barcode = product.get('upc_barcode')

                if upc_barcode:
                    try:
                        mssql_data = self.get_inventory_by_upc(upc_barcode)

                        if mssql_data:
                            product_copy['mssql_quantity'] = mssql_data.get('quantity_on_hand')
                            product_copy['mssql_available'] = mssql_data.get('quantity_available')
                            product_copy['mssql_price'] = mssql_data.get('unit_price')
                            product_copy['mssql_matched'] = True
                        else:
                            product_copy['mssql_matched'] = False

                    except Exception:
                        # If query fails for this product, mark as not matched
                        product_copy['mssql_matched'] = False
                else:
                    product_copy['mssql_matched'] = False

                matched_products.append(product_copy)

        finally:
            self.disconnect()

        return matched_products


def create_mssql_client(settings: Dict[str, Any]) -> Optional[MSSQLConnector]:
    """
    Create an MS SQL connector from settings.

    Args:
        settings: Settings dictionary with MS SQL connection details

    Returns:
        MSSQLConnector instance or None if settings are incomplete
    """
    server = settings.get('mssql_server')
    database = settings.get('mssql_database')
    username = settings.get('mssql_username')
    password = settings.get('mssql_password')
    port = settings.get('mssql_port', 1433)

    if not all([server, database, username, password]):
        return None

    return MSSQLConnector(
        server=server,
        database=database,
        username=username,
        password=password,
        port=port
    )
