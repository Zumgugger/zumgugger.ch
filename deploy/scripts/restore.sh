#!/bin/bash
# restore.sh - Restore database from backup
# Usage: ./restore.sh /var/www/sitename /path/to/backup.db

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check arguments
if [[ -z "$1" ]] || [[ -z "$2" ]]; then
    echo "Usage: $0 <site-directory> <backup-file>"
    echo "Example: $0 /var/www/mysite /var/www/mysite/data/backups/backup_20260203_120000.db"
    exit 1
fi

SITE_DIR="$1"
BACKUP_FILE="$2"
DATA_DIR="${SITE_DIR}/data"
DB_FILE="${DATA_DIR}/site.db"
SITENAME=$(basename "$SITE_DIR")

# Validate paths
if [[ ! -d "$SITE_DIR" ]]; then
    log_error "Site directory does not exist: $SITE_DIR"
    exit 1
fi

if [[ ! -f "$BACKUP_FILE" ]]; then
    log_error "Backup file does not exist: $BACKUP_FILE"
    exit 1
fi

# Verify backup file is a valid SQLite database
if command -v sqlite3 &> /dev/null; then
    if ! sqlite3 "$BACKUP_FILE" "SELECT 1" &>/dev/null; then
        log_error "Backup file is not a valid SQLite database"
        exit 1
    fi
fi

log_info "Restoring database from: $BACKUP_FILE"

# Confirm with user
echo ""
log_warn "This will replace the current database with the backup."
log_warn "Current database will be saved as site.db.before-restore"
echo ""
read -p "Are you sure you want to continue? (yes/no): " confirm
if [[ "$confirm" != "yes" ]]; then
    log_info "Restore cancelled"
    exit 0
fi

# Stop the service
log_info "Stopping service..."
SERVICE_NAME="websitecms-${SITENAME}.service"
if systemctl is-active --quiet "$SERVICE_NAME"; then
    systemctl stop "$SERVICE_NAME"
    sleep 2
fi

# Also stop via docker-compose as fallback
cd "$SITE_DIR"
docker compose down 2>/dev/null || true

# Backup current database before restore
if [[ -f "$DB_FILE" ]]; then
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    CURRENT_BACKUP="${DB_FILE}.before-restore.${TIMESTAMP}"
    log_info "Backing up current database to: $CURRENT_BACKUP"
    cp "$DB_FILE" "$CURRENT_BACKUP"
fi

# Restore the backup
log_info "Restoring database..."
cp "$BACKUP_FILE" "$DB_FILE"

# Fix permissions
chown www-data:www-data "$DB_FILE" 2>/dev/null || true
chmod 664 "$DB_FILE"

# Start the service
log_info "Starting service..."
if [[ -f "/etc/systemd/system/$SERVICE_NAME" ]]; then
    systemctl start "$SERVICE_NAME"
else
    cd "$SITE_DIR"
    docker compose up -d
fi

# Verify service is running
sleep 3
log_info "Verifying service..."

# Get port from .env
PORT=$(grep -oP "^APP_PORT=\K[0-9]+" "$SITE_DIR/.env" 2>/dev/null || echo "30000")

HEALTH_CHECK=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$PORT/health" || echo "000")
if [[ "$HEALTH_CHECK" == "200" ]]; then
    log_info "Service is healthy!"
else
    log_warn "Service health check returned: $HEALTH_CHECK"
    log_warn "Please check the logs: docker logs websitecms-${SITENAME}"
fi

echo ""
log_info "Restore complete!"
echo ""
echo "The previous database was saved to:"
echo "  $CURRENT_BACKUP"
echo ""
echo "If you need to rollback, run:"
echo "  sudo cp $CURRENT_BACKUP $DB_FILE"
echo "  sudo systemctl restart $SERVICE_NAME"
