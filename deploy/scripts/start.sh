#!/bin/bash
# start.sh - Start WebsiteCMS service
# Usage: ./start.sh <sitename>

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

if [[ -z "$1" ]]; then
    echo "Usage: $0 <sitename>"
    exit 1
fi

SITENAME="$1"
SITE_DIR="/var/www/${SITENAME}"
SERVICE_NAME="websitecms-${SITENAME}.service"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYSTEMD_TEMPLATE="$(dirname "$SCRIPT_DIR")/systemd/websitecms.service"

# Validate site directory
if [[ ! -d "$SITE_DIR" ]]; then
    log_error "Site directory does not exist: $SITE_DIR"
    exit 1
fi

# Check if systemd service exists, create if not
if [[ ! -f "/etc/systemd/system/$SERVICE_NAME" ]]; then
    log_info "Creating systemd service..."
    
    # Generate service file from template
    sed -e "s/{{SITENAME}}/$SITENAME/g" \
        -e "s|{{SITE_DIR}}|$SITE_DIR|g" \
        "$SYSTEMD_TEMPLATE" > "/etc/systemd/system/$SERVICE_NAME"
    
    systemctl daemon-reload
    systemctl enable "$SERVICE_NAME"
fi

# Start the service
log_info "Starting $SERVICE_NAME..."
systemctl start "$SERVICE_NAME"

# Wait for startup
sleep 3

# Check status
if systemctl is-active --quiet "$SERVICE_NAME"; then
    log_info "Service started successfully"
    
    # Show container status
    cd "$SITE_DIR"
    docker compose ps
else
    log_error "Service failed to start"
    systemctl status "$SERVICE_NAME" --no-pager
    exit 1
fi
