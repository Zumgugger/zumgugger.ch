#!/bin/bash
# stop.sh - Stop WebsiteCMS service
# Usage: ./stop.sh <sitename>

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

if [[ -z "$1" ]]; then
    echo "Usage: $0 <sitename>"
    exit 1
fi

SITENAME="$1"
SITE_DIR="/var/www/${SITENAME}"
SERVICE_NAME="websitecms-${SITENAME}.service"

# Stop via systemd if service exists
if [[ -f "/etc/systemd/system/$SERVICE_NAME" ]]; then
    log_info "Stopping $SERVICE_NAME..."
    systemctl stop "$SERVICE_NAME"
fi

# Also stop via docker-compose as fallback
if [[ -d "$SITE_DIR" ]]; then
    cd "$SITE_DIR"
    docker compose down 2>/dev/null || true
fi

log_info "Service stopped"
