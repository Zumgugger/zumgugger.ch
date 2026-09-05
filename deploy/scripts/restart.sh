#!/bin/bash
# restart.sh - Restart WebsiteCMS service
# Usage: ./restart.sh <sitename>

set -e

# Colors
GREEN='\033[0;32m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }

if [[ -z "$1" ]]; then
    echo "Usage: $0 <sitename>"
    exit 1
fi

SITENAME="$1"
SITE_DIR="/var/www/${SITENAME}"
SERVICE_NAME="websitecms-${SITENAME}.service"

log_info "Restarting $SERVICE_NAME..."

# Restart via systemd if service exists
if [[ -f "/etc/systemd/system/$SERVICE_NAME" ]]; then
    systemctl restart "$SERVICE_NAME"
else
    # Fallback to docker-compose
    if [[ -d "$SITE_DIR" ]]; then
        cd "$SITE_DIR"
        docker compose restart
    fi
fi

# Wait for startup
sleep 3

# Show status
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"$SCRIPT_DIR/status.sh" "$SITENAME"
