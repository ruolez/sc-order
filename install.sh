#!/bin/bash

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script banner
echo -e "${BLUE}"
echo "╔════════════════════════════════════════════════╗"
echo "║   SC-Order Installation Script                 ║"
echo "║   Inventory Management System                  ║"
echo "║   Ubuntu 24.04 LTS                             ║"
echo "╚════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo -e "${RED}Error: This script should NOT be run as root${NC}"
   echo "Please run as a regular user with sudo privileges"
   exit 1
fi

# Check if sudo is available
if ! command -v sudo &> /dev/null; then
    echo -e "${RED}Error: sudo is not installed${NC}"
    exit 1
fi

# Function to print step headers
print_step() {
    echo -e "\n${BLUE}▶ $1${NC}"
}

# Function to print success messages
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

# Function to print warnings
print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# Function to print errors
print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Function to update application from GitHub
update_application() {
    echo -e "\n${BLUE}╔════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║   Update from GitHub                           ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════╝${NC}\n"

    # Check if we're in a git repository
    if ! git rev-parse --git-dir > /dev/null 2>&1; then
        print_error "Not a git repository. Cannot update from GitHub."
        print_warning "Please clone the repository using: git clone https://github.com/ruolez/sc-order.git"
        exit 1
    fi

    # Show current git status
    print_step "Current Repository Status"
    CURRENT_BRANCH=$(git branch --show-current)
    CURRENT_COMMIT=$(git log -1 --format="%h - %s" 2>/dev/null || echo "Unknown")
    echo "Branch: ${CURRENT_BRANCH}"
    echo "Commit: ${CURRENT_COMMIT}"

    # Check for uncommitted changes
    if ! git diff-index --quiet HEAD -- 2>/dev/null; then
        print_warning "You have uncommitted local changes"
        git status --short
        echo ""
        read -p "Continue with update anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_error "Update cancelled"
            exit 1
        fi
    fi

    # Database backup handling
    BACKUP_FILE=""
    if [ -f "./data/inventory.db" ]; then
        echo -e "\n${YELLOW}Database Backup${NC}"
        read -p "Backup database before updating? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_step "Creating database backup..."

            # Create backups directory if it doesn't exist
            mkdir -p ./data/backups

            # Create timestamped backup
            BACKUP_FILE="./data/backups/inventory.db.backup.$(date +%Y%m%d_%H%M%S)"
            cp ./data/inventory.db "$BACKUP_FILE"

            if [ -f "$BACKUP_FILE" ]; then
                print_success "Database backed up to: $BACKUP_FILE"
            else
                print_error "Failed to create backup"
                exit 1
            fi
        fi
    fi

    # Pull latest changes from GitHub
    print_step "Pulling latest changes from GitHub..."
    if git pull origin "${CURRENT_BRANCH}"; then
        print_success "Code updated successfully"
    else
        print_error "Failed to pull changes from GitHub"
        exit 1
    fi

    # Stop running containers
    print_step "Stopping containers..."
    if command -v docker &> /dev/null; then
        sg docker -c "docker compose down" || {
            print_error "Failed to stop containers"
            exit 1
        }
        print_success "Containers stopped"
    fi

    # Rebuild Docker images
    print_step "Rebuilding Docker images (this may take a few minutes)..."
    sg docker -c "docker compose build --no-cache" || {
        print_error "Failed to build Docker images"
        exit 1
    }
    print_success "Docker images rebuilt successfully"

    # Start containers
    print_step "Starting containers..."
    sg docker -c "docker compose up -d" || {
        print_error "Failed to start containers"
        exit 1
    }
    print_success "Containers started"

    # Database restoration check
    if [ ! -z "$BACKUP_FILE" ]; then
        print_step "Verifying database..."
        if [ -f "./data/inventory.db" ]; then
            print_success "Database intact, backup preserved at: $BACKUP_FILE"
        else
            print_warning "Database not found, restoring from backup..."
            cp "$BACKUP_FILE" ./data/inventory.db
            if [ -f "./data/inventory.db" ]; then
                print_success "Database restored successfully from: $BACKUP_FILE"
            else
                print_error "Failed to restore database"
                exit 1
            fi
        fi
    fi

    # Wait for services to be healthy
    print_step "Waiting for services to be ready..."
    echo "This may take up to 60 seconds..."
    sleep 10

    # Check container status
    MAX_RETRIES=12
    RETRY_COUNT=0
    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        if sg docker -c "docker compose ps" | grep -q "healthy"; then
            print_success "All services are healthy"
            break
        fi

        RETRY_COUNT=$((RETRY_COUNT + 1))
        if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
            echo "Waiting... ($RETRY_COUNT/$MAX_RETRIES)"
            sleep 5
        else
            print_warning "Services started but health checks are still pending"
            print_warning "Check 'docker compose ps' for status"
        fi
    done

    # Display container status
    print_step "Container Status"
    sg docker -c "docker compose ps"

    # Update complete
    echo -e "\n${GREEN}╔════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║   Update Complete! ✓                           ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════╝${NC}\n"

    # Access information
    echo -e "${BLUE}Access Information:${NC}"
    APP_PORT=$(grep '".*:80"' docker-compose.yml | awk -F'[:"]+' '{print $2}' || echo "5001")
    LOCAL_IP=$(hostname -I | awk '{print $1}' 2>/dev/null || ipconfig getifaddr en0 2>/dev/null || echo "localhost")
    echo "  • Local:    http://localhost:${APP_PORT}"
    echo "  • Network:  http://${LOCAL_IP}:${APP_PORT}"

    if [ ! -z "$BACKUP_FILE" ]; then
        echo -e "\n${BLUE}Backup Information:${NC}"
        echo "  • Backup saved at: $BACKUP_FILE"
    fi

    echo ""
    exit 0
}

# Check Ubuntu version
print_step "Checking Ubuntu version..."
if [ -f /etc/os-release ]; then
    . /etc/os-release
    if [[ "$ID" == "ubuntu" ]]; then
        print_success "Ubuntu $VERSION_ID detected"
    else
        print_warning "This script is designed for Ubuntu 24.04"
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
else
    print_error "Cannot determine OS version"
    exit 1
fi

# Check for existing installation
print_step "Checking for existing installation..."
EXISTING_INSTALL=false

# Check for running containers
if command -v docker &> /dev/null; then
    if sg docker -c "docker ps -a --format '{{.Names}}'" 2>/dev/null | grep -q "sc-order"; then
        EXISTING_INSTALL=true
        print_warning "Found existing SC-Order containers"
    fi
fi

# Check for systemd service
if [ -f "/etc/systemd/system/sc-order.service" ]; then
    EXISTING_INSTALL=true
    print_warning "Found existing SC-Order systemd service"
fi

# Check for data directory
if [ -d "./data" ] && [ -f "./data/inventory.db" ]; then
    EXISTING_INSTALL=true
    print_warning "Found existing data directory with database"
fi

if [ "$EXISTING_INSTALL" = true ]; then
    echo -e "\n${YELLOW}╔════════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║   Existing Installation Detected              ║${NC}"
    echo -e "${YELLOW}╚════════════════════════════════════════════════╝${NC}\n"

    echo "What would you like to do?"
    echo "  [1] Update from GitHub (pull latest code, keep data)"
    echo "  [2] Fresh Install (remove everything and start clean)"
    echo "  [3] Cancel"
    echo ""
    read -p "Choose an option [1/2/3]: " -n 1 -r INSTALL_CHOICE
    echo ""

    case $INSTALL_CHOICE in
        1)
            # Update from GitHub
            update_application
            ;;
        2)
            # Fresh Install - Remove existing installation
            print_step "Removing existing installation..."

            # Stop and remove containers
            if command -v docker &> /dev/null; then
                if sg docker -c "docker compose ps -q" &> /dev/null; then
                    print_step "Stopping containers..."
                    sg docker -c "docker compose down" || true
                    print_success "Containers stopped"
                fi

                # Remove SC-Order images
                IMAGES=$(sg docker -c "docker images --format '{{.Repository}}:{{.Tag}}'" | grep "sc-order" || true)
                if [ ! -z "$IMAGES" ]; then
                    print_step "Removing Docker images..."
                    echo "$IMAGES" | while read -r image; do
                        sg docker -c "docker rmi $image" || true
                    done
                    print_success "Docker images removed"
                fi
            fi

            # Remove systemd service
            if [ -f "/etc/systemd/system/sc-order.service" ]; then
                print_step "Removing systemd service..."
                sudo systemctl stop sc-order.service 2>/dev/null || true
                sudo systemctl disable sc-order.service 2>/dev/null || true
                sudo rm -f /etc/systemd/system/sc-order.service
                sudo systemctl daemon-reload
                print_success "Systemd service removed"
            fi

            # Ask about data directory
            if [ -d "./data" ]; then
                echo -e "\n${YELLOW}Data Directory Found${NC}"
                read -p "Do you want to delete the existing database? (y/N): " -n 1 -r
                echo
                if [[ $REPLY =~ ^[Yy]$ ]]; then
                    print_step "Backing up database..."
                    mkdir -p ./data/backups
                    BACKUP_FILE="./data/backups/inventory.db.backup.$(date +%Y%m%d_%H%M%S)"
                    cp ./data/inventory.db "$BACKUP_FILE" 2>/dev/null || true
                    if [ -f "$BACKUP_FILE" ]; then
                        print_success "Database backed up to: $BACKUP_FILE"
                    fi

                    rm -rf ./data
                    print_success "Data directory removed"
                else
                    print_warning "Keeping existing database"
                fi
            fi

            print_success "Existing installation removed"
            echo ""
            ;;
        3)
            # Cancel
            print_error "Installation cancelled"
            exit 0
            ;;
        *)
            # Invalid choice
            print_error "Invalid choice. Installation cancelled."
            exit 1
            ;;
    esac
fi

# Ask for server IP
print_step "Network Configuration"
echo "Enter the local network IP address for this server"
echo "Examples: 192.168.1.100, 10.0.0.50"
echo "Or press Enter to bind to all interfaces (0.0.0.0)"
read -p "Server IP [0.0.0.0]: " SERVER_IP
SERVER_IP=${SERVER_IP:-0.0.0.0}

# Validate IP address format
if [[ ! $SERVER_IP =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] && [[ $SERVER_IP != "0.0.0.0" ]]; then
    print_error "Invalid IP address format"
    exit 1
fi

# Ask for port
read -p "Enter the port number [5001]: " APP_PORT
APP_PORT=${APP_PORT:-5001}

# Validate port number
if ! [[ "$APP_PORT" =~ ^[0-9]+$ ]] || [ "$APP_PORT" -lt 1 ] || [ "$APP_PORT" -gt 65535 ]; then
    print_error "Invalid port number"
    exit 1
fi

print_success "Server will be accessible at: http://${SERVER_IP}:${APP_PORT}"

# Update system packages
print_step "Updating system packages..."
sudo apt-get update -qq
print_success "System packages updated"

# Install required dependencies
print_step "Installing system dependencies..."
sudo apt-get install -y -qq \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    git \
    wget
print_success "System dependencies installed"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    print_step "Installing Docker..."

    # Add Docker's official GPG key
    sudo install -m 0755 -d /etc/apt/keyrings
    sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    sudo chmod a+r /etc/apt/keyrings/docker.asc

    # Add Docker repository
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
      $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
      sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

    # Install Docker Engine
    sudo apt-get update -qq
    sudo apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    # Add current user to docker group
    sudo usermod -aG docker $USER

    print_success "Docker installed successfully"
    print_warning "You may need to log out and back in for Docker group permissions to take effect"
else
    print_success "Docker is already installed"
fi

# Verify Docker Compose
if ! sg docker -c "docker compose version" &> /dev/null; then
    print_error "Docker Compose plugin not found"
    exit 1
else
    print_success "Docker Compose is available"
fi

# Create data directory
print_step "Creating application directories..."
mkdir -p ./data
print_success "Data directory created"

# Update docker-compose.yml with custom port
print_step "Configuring application..."
if [ "$APP_PORT" != "5001" ] || [ "$SERVER_IP" != "0.0.0.0" ]; then
    sed -i.bak "s/\"5001:80\"/\"${SERVER_IP}:${APP_PORT}:80\"/" docker-compose.yml
    print_success "Docker Compose configuration updated"
fi

# Build Docker images
print_step "Building Docker images (this may take a few minutes)..."
sg docker -c "docker compose build --no-cache"
print_success "Docker images built successfully"

# Start containers
print_step "Starting containers..."
sg docker -c "docker compose up -d"
print_success "Containers started"

# Wait for services to be healthy
print_step "Waiting for services to be ready..."
echo "This may take up to 60 seconds..."
sleep 10

# Check container status
MAX_RETRIES=12
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if sg docker -c "docker compose ps" | grep -q "healthy"; then
        print_success "All services are healthy"
        break
    fi

    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
        echo "Waiting... ($RETRY_COUNT/$MAX_RETRIES)"
        sleep 5
    else
        print_warning "Services started but health checks are still pending"
        print_warning "Check 'docker compose ps' for status"
    fi
done

# Display container status
print_step "Container Status"
sg docker -c "docker compose ps"

# Test application endpoint
print_step "Testing application..."
sleep 2
if curl -s -o /dev/null -w "%{http_code}" http://localhost:${APP_PORT}/health | grep -q "200"; then
    print_success "Application is responding"
else
    print_warning "Application may still be starting up"
fi

# Set up firewall rules (if ufw is installed)
if command -v ufw &> /dev/null; then
    print_step "Configuring firewall..."
    read -p "Allow port ${APP_PORT} through firewall? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo ufw allow ${APP_PORT}/tcp
        print_success "Firewall rule added"
    fi
fi

# Create systemd service for auto-start (optional)
print_step "System Integration"
read -p "Create systemd service for auto-start on boot? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    INSTALL_DIR=$(pwd)
    SERVICE_FILE="/etc/systemd/system/sc-order.service"

    sudo tee $SERVICE_FILE > /dev/null <<EOF
[Unit]
Description=SC-Order Inventory Management
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=${INSTALL_DIR}
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
User=${USER}

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable sc-order.service
    print_success "Systemd service created and enabled"
fi

# Installation complete
echo -e "\n${GREEN}╔════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   Installation Complete! ✓                     ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════╝${NC}\n"

# Access information
echo -e "${BLUE}Access Information:${NC}"
if [ "$SERVER_IP" == "0.0.0.0" ]; then
    LOCAL_IP=$(hostname -I | awk '{print $1}')
    echo "  • Local:    http://localhost:${APP_PORT}"
    echo "  • Network:  http://${LOCAL_IP}:${APP_PORT}"
else
    echo "  • URL:      http://${SERVER_IP}:${APP_PORT}"
fi

echo -e "\n${BLUE}Useful Commands:${NC}"
echo "  • View logs:        docker compose logs -f"
echo "  • Stop services:    docker compose down"
echo "  • Start services:   docker compose up -d"
echo "  • Restart services: docker compose restart"
echo "  • View status:      docker compose ps"
echo "  • Update app:       git pull && docker compose build --no-cache && docker compose up -d"

echo -e "\n${BLUE}Configuration Files:${NC}"
echo "  • Database:         ./data/inventory.db"
echo "  • Docker Compose:   ./docker-compose.yml"
echo "  • Application Logs: docker compose logs"

echo -e "\n${YELLOW}Next Steps:${NC}"
echo "  1. Access the application at the URL above"
echo "  2. Go to Settings to configure Shopify and MS SQL integrations"
echo "  3. Import your product data or sync from Shopify"

if [[ $(groups $USER) != *"docker"* ]]; then
    echo -e "\n${YELLOW}Important:${NC}"
    echo "  You may need to log out and back in for Docker permissions to take effect"
    echo "  Or run: newgrp docker"
fi

echo ""
