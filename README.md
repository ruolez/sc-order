# Inventory Reorder Management System

A containerized web-based inventory management application that integrates with Shopify and Microsoft SQL Server to track product reorder points.

## Features

- **Product Management**: Add, edit, and delete products with barcode tracking
- **Excel Import**: Bulk import products from Excel files
- **Shopify Integration**: Connect to Shopify Admin API to retrieve inventory levels
- **MS SQL Connection**: Link to Microsoft SQL Server database for external inventory data
- **Settings Management**: Configure Shopify and MS SQL connections

## Architecture

The application is fully containerized using Docker with the following services:

- **nginx** (Reverse Proxy): Routes requests to appropriate services on port 80
- **frontend**: Nginx container serving static HTML/CSS/JS files
- **backend**: Flask API server handling business logic
- **data volume**: Persistent SQLite database storage

## Tech Stack

- **Backend**: Python Flask
- **Frontend**: HTML, Tailwind CSS, Vanilla JavaScript
- **Database**: SQLite (persisted in Docker volume)
- **Reverse Proxy**: Nginx
- **Container Orchestration**: Docker Compose

## Quick Start

### Prerequisites

- Docker Desktop (or Docker + Docker Compose)
- Git

### Installation

1. **Clone or navigate to the project**:
   ```bash
   cd SC-Order
   ```

2. **Build and start all containers**:
   ```bash
   docker-compose up --build -d
   ```

3. **Access the application**:
   Open your browser and navigate to: **http://localhost**

4. **View logs**:
   ```bash
   # All containers
   docker-compose logs -f

   # Specific container
   docker-compose logs -f backend
   docker-compose logs -f frontend
   docker-compose logs -f nginx
   ```

5. **Stop the application**:
   ```bash
   docker-compose down
   ```

6. **Stop and remove data**:
   ```bash
   docker-compose down -v
   ```

## Configuration

### Shopify Setup
1. Go to the **Settings** page in the application
2. Enter your Shopify store details:
   - Store URL (e.g., `your-store.myshopify.com`)
   - Admin API Access Token
   - Location ID (for inventory tracking)
3. Click **Test Connection** to verify
4. Click **Save All Settings**

### MS SQL Setup
1. Go to the **Settings** page
2. Enter your MS SQL Server details:
   - Server address
   - Database name
   - Username and Password
   - Port (default: 1433)
3. Click **Test Connection** to verify
4. Click **Save All Settings**

## Product Matching Strategy

Products are linked across all three systems using barcodes:

- **Internal Database**: `upc_barcode` field
- **Shopify**: `variant.sku` field (configured to match UPC barcodes)
- **MS SQL Database**: `product_upc` column

## Excel Import Format

Your Excel file should include these columns:

**Required**:
- `product_name`: Name of the product
- `upc_barcode`: UPC/barcode identifier

**Optional**:
- `threshold_quantity`: Reorder threshold
- `quantity_per_case`: Units per case
- `price`: Product price

## Project Structure

```
SC-Order/
├── docker-compose.yml          # Container orchestration
├── backend/
│   ├── Dockerfile              # Backend container definition
│   ├── app.py                  # Flask application
│   ├── database.py             # SQLite database operations
│   ├── requirements.txt        # Python dependencies
│   ├── static/                 # Static assets (copied to frontend)
│   └── templates/              # HTML templates (copied to frontend)
├── frontend/
│   ├── Dockerfile              # Frontend container definition
│   ├── nginx.conf              # Frontend nginx configuration
│   ├── static/
│   │   ├── css/styles.css      # Custom styles
│   │   └── js/
│   │       ├── app.js          # Main JavaScript
│   │       ├── settings.js     # Settings management
│   │       ├── products.js     # Product CRUD operations
│   │       └── import.js       # Excel import functionality
│   └── templates/
│       └── index.html          # Main application template
├── nginx/
│   ├── Dockerfile              # Nginx reverse proxy container
│   └── nginx.conf              # Reverse proxy configuration
└── data/                       # Persistent SQLite database (Docker volume)
```

## Docker Commands

### View Container Status
```bash
docker-compose ps
```

### Rebuild Specific Container
```bash
docker-compose up -d --build backend
```

### Execute Commands in Container
```bash
# Access backend shell
docker-compose exec backend sh

# Access database
docker-compose exec backend python database.py
```

### View Real-time Logs
```bash
# All containers
docker-compose logs -f

# Specific service
docker-compose logs -f backend
```

## Health Checks

The application includes health checks for monitoring:

- **Nginx Reverse Proxy**: `http://localhost/health`
- **Backend API**: `http://localhost/api/products`

## Development

To develop with live reload:

1. **Backend**: Mount local code as volume in docker-compose.yml
2. **Frontend**: Rebuild frontend container after changes
3. **Nginx**: No changes needed for development

## Troubleshooting

### Container won't start
```bash
# Check logs
docker-compose logs backend

# Rebuild from scratch
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Database issues
```bash
# Remove and recreate database
docker-compose down -v
docker-compose up -d
```

### Port already in use
```bash
# Change port in docker-compose.yml
ports:
  - "8080:80"  # Use port 8080 instead of 80
```

## Next Steps

The following features will be implemented next:

1. **Shopify Integration Module** (`shopify_api.py`)
   - Fetch locations
   - Query inventory levels by location
   - Match products by SKU

2. **MS SQL Connector Module** (`mssql_connector.py`)
   - Connection management
   - Query execution
   - Product matching by `product_upc`

3. **Inventory Sync Feature**
   - Compare Shopify inventory levels with thresholds
   - Generate reorder lists
   - Export to Excel or MS SQL

## Requirements

- Docker Desktop 20.10+
- Docker Compose 2.0+
- MS SQL Server ODBC Driver (installed in backend container)
- Shopify Admin API access token with inventory permissions

## License

Private project - All rights reserved
