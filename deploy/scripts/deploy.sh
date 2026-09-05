#!/bin/bash
# deploy.sh - Main deployment script for WebsiteCMS
# Usage: sudo ./deploy.sh --domain example.com --sitename mysite [--port 30000]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
PORT=""
INSTALL_DIR="/var/www"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Function to print colored messages
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Function to show usage
show_usage() {
    echo "Usage: $0 --domain <domain> --sitename <sitename> [--port <port>]"
    echo ""
    echo "Options:"
    echo "  --domain    The domain name (e.g., example.com)"
    echo "  --sitename  The site identifier (e.g., mysite)"
    echo "  --port      Optional port number (default: auto-allocated from 30000-30999)"
    echo ""
    echo "Example:"
    echo "  sudo $0 --domain example.com --sitename mysite --port 30000"
    exit 1
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --domain)
            DOMAIN="$2"
            shift 2
            ;;
        --sitename)
            SITENAME="$2"
            shift 2
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        -h|--help)
            show_usage
            ;;
        *)
            log_error "Unknown option: $1"
            show_usage
            ;;
    esac
done

# Validate required arguments
if [[ -z "$DOMAIN" ]] || [[ -z "$SITENAME" ]]; then
    log_error "Missing required arguments"
    show_usage
fi

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    log_error "This script must be run as root (use sudo)"
    exit 1
fi

log_info "Starting deployment of WebsiteCMS"
log_info "Domain: $DOMAIN"
log_info "Site name: $SITENAME"

# Step 1: Check prerequisites
log_info "Checking prerequisites..."

check_command() {
    if ! command -v $1 &> /dev/null; then
        log_error "$1 is not installed. Please install it first."
        exit 1
    fi
}

check_command docker
check_command docker-compose || check_command "docker compose"
check_command apache2ctl
check_command certbot

log_info "All prerequisites satisfied"

# Step 2: Allocate port if not specified
if [[ -z "$PORT" ]]; then
    log_info "Allocating port..."
    PORT=$("$SCRIPT_DIR/allocate-port.sh")
    if [[ -z "$PORT" ]]; then
        log_error "Failed to allocate port"
        exit 1
    fi
fi
log_info "Using port: $PORT"

# Step 3: Create site directory
SITE_DIR="${INSTALL_DIR}/${SITENAME}"
log_info "Creating site directory: $SITE_DIR"

if [[ -d "$SITE_DIR" ]]; then
    log_warn "Site directory already exists. Backing up..."
    mv "$SITE_DIR" "${SITE_DIR}.backup.$(date +%Y%m%d%H%M%S)"
fi

mkdir -p "$SITE_DIR"

# Step 4: Copy application files
log_info "Copying application files..."
cp -r "$PROJECT_DIR/app" "$SITE_DIR/"
cp -r "$PROJECT_DIR/deploy" "$SITE_DIR/"
cp "$PROJECT_DIR/Dockerfile" "$SITE_DIR/"
cp "$PROJECT_DIR/docker-compose.yml" "$SITE_DIR/"
cp "$PROJECT_DIR/docker-compose.prod.yml" "$SITE_DIR/"
cp "$PROJECT_DIR/requirements.txt" "$SITE_DIR/"
cp "$PROJECT_DIR/run.py" "$SITE_DIR/"
cp "$PROJECT_DIR/.env.example" "$SITE_DIR/.env"

# Create data directory
mkdir -p "$SITE_DIR/data"
mkdir -p "$SITE_DIR/data/uploads"
mkdir -p "$SITE_DIR/data/backups"

# Step 5: Configure environment
log_info "Configuring environment..."
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

# Update .env file
sed -i "s/^SECRET_KEY=.*/SECRET_KEY=$SECRET_KEY/" "$SITE_DIR/.env"
sed -i "s/^DEBUG=.*/DEBUG=false/" "$SITE_DIR/.env"
sed -i "s/^LOG_LEVEL=.*/LOG_LEVEL=WARNING/" "$SITE_DIR/.env"

# Set APP_PORT in .env without creating duplicate entries.
if grep -q "^APP_PORT=" "$SITE_DIR/.env"; then
    sed -i "s/^APP_PORT=.*/APP_PORT=$PORT/" "$SITE_DIR/.env"
else
    echo "APP_PORT=$PORT" >> "$SITE_DIR/.env"
fi

# Step 6: Set permissions
log_info "Setting permissions..."
chown -R root:www-data "$SITE_DIR"
chmod -R 755 "$SITE_DIR"
chown -R 1000:1000 "$SITE_DIR/data"
chmod -R 775 "$SITE_DIR/data"
chmod 600 "$SITE_DIR/.env"

# Step 7: Setup Apache vhost
log_info "Setting up Apache virtual host..."
"$SCRIPT_DIR/setup-vhost.sh" --domain "$DOMAIN" --sitename "$SITENAME" --port "$PORT"

# Step 8: Enable Apache modules
log_info "Enabling required Apache modules..."
a2enmod proxy proxy_http rewrite headers ssl > /dev/null 2>&1

# Step 9: Enable site and reload Apache
log_info "Enabling site..."
a2ensite "${SITENAME}.conf" > /dev/null 2>&1
apache2ctl configtest
systemctl reload apache2

# Step 10: Setup SSL with Certbot
log_info "Setting up SSL certificate..."
"$SCRIPT_DIR/setup-ssl.sh" --domain "$DOMAIN" --sitename "$SITENAME"

# Step 11: Create and start systemd service
log_info "Creating systemd service..."
"$SCRIPT_DIR/start.sh" "$SITENAME"

# Step 12: Run smoke tests
log_info "Running smoke tests..."
sleep 5  # Wait for container to start

HEALTH_CHECK=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$PORT/health" || echo "000")
if [[ "$HEALTH_CHECK" == "200" ]]; then
    log_info "Health check passed!"
else
    log_warn "Health check returned: $HEALTH_CHECK (container may still be starting)"
fi

# Step 13: Setup backup cron job
log_info "Setting up backup cron job..."
CRON_LINE="0 * * * * $SITE_DIR/deploy/scripts/backup.sh $SITE_DIR"
(crontab -l 2>/dev/null | grep -v "$SITE_DIR/deploy/scripts/backup.sh" ; echo "$CRON_LINE") | crontab -

# Final output
echo ""
log_info "=========================================="
log_info "Deployment complete!"
log_info "=========================================="
echo ""
echo "Site URL: https://$DOMAIN"
echo "Admin URL: https://$DOMAIN/admin/login"
echo "Health: https://$DOMAIN/health"
echo ""
echo "Site directory: $SITE_DIR"
echo "Port: $PORT"
echo ""
echo "Next steps:"
echo "  1. Edit $SITE_DIR/.env to configure SMTP and other settings"
echo "  2. Restart the service: sudo systemctl restart websitecms-${SITENAME}.service"
echo "  3. Visit https://$DOMAIN to verify the site is working"
echo ""
