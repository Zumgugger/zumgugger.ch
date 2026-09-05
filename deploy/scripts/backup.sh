#!/bin/bash
# backup.sh - Backup SQLite database with smart retention
# Usage: ./backup.sh /var/www/sitename

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
if [[ -z "$1" ]]; then
    echo "Usage: $0 <site-directory>"
    echo "Example: $0 /var/www/mysite"
    exit 1
fi

SITE_DIR="$1"
DATA_DIR="${SITE_DIR}/data"
BACKUP_DIR="${DATA_DIR}/backups"
DB_FILE="${DATA_DIR}/site.db"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/backup_${TIMESTAMP}.db"

# Validate paths
if [[ ! -d "$SITE_DIR" ]]; then
    log_error "Site directory does not exist: $SITE_DIR"
    exit 1
fi

if [[ ! -f "$DB_FILE" ]]; then
    log_warn "Database file does not exist: $DB_FILE"
    log_info "Nothing to backup"
    exit 0
fi

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Create backup using SQLite's backup command (safe for concurrent access)
log_info "Creating backup: $BACKUP_FILE"

if command -v sqlite3 &> /dev/null; then
    # Use SQLite backup command for safe backup
    sqlite3 "$DB_FILE" ".backup '$BACKUP_FILE'"
else
    # Fallback to copy (less safe but works without sqlite3 CLI)
    cp "$DB_FILE" "$BACKUP_FILE"
fi

# Verify backup
if [[ ! -f "$BACKUP_FILE" ]]; then
    log_error "Backup failed - file not created"
    exit 1
fi

BACKUP_SIZE=$(stat -c%s "$BACKUP_FILE" 2>/dev/null || stat -f%z "$BACKUP_FILE" 2>/dev/null)
if [[ "$BACKUP_SIZE" -lt 1024 ]]; then
    log_warn "Backup file seems too small: $BACKUP_SIZE bytes"
fi

log_info "Backup created successfully: $BACKUP_FILE ($BACKUP_SIZE bytes)"

# Smart retention (GFS-style: Grandfather-Father-Son)
# Keep:
#   - All backups from the last 24 hours (hourly)
#   - One backup per day for the last 7 days (daily)
#   - One backup per week for the last 4 weeks (weekly)
#   - One backup per month for the last 12 months (monthly)

log_info "Applying retention policy..."

cleanup_old_backups() {
    local now=$(date +%s)
    local one_hour=$((60 * 60))
    local one_day=$((24 * one_hour))
    local one_week=$((7 * one_day))
    local one_month=$((30 * one_day))
    
    # Track which backups to keep
    declare -A keep_daily
    declare -A keep_weekly
    declare -A keep_monthly
    
    for backup in "$BACKUP_DIR"/backup_*.db; do
        [[ -f "$backup" ]] || continue
        
        # Extract timestamp from filename
        filename=$(basename "$backup")
        backup_date="${filename#backup_}"
        backup_date="${backup_date%.db}"
        
        # Parse date (format: YYYYMMDD_HHMMSS)
        year="${backup_date:0:4}"
        month="${backup_date:4:2}"
        day="${backup_date:6:2}"
        hour="${backup_date:9:2}"
        min="${backup_date:11:2}"
        sec="${backup_date:13:2}"
        
        backup_ts=$(date -d "${year}-${month}-${day} ${hour}:${min}:${sec}" +%s 2>/dev/null || echo 0)
        [[ "$backup_ts" -eq 0 ]] && continue
        
        age=$((now - backup_ts))
        
        # Always keep backups from last 24 hours
        if [[ $age -lt $one_day ]]; then
            continue
        fi
        
        # For older backups, apply GFS retention
        day_key="${year}${month}${day}"
        week_key=$(date -d "${year}-${month}-${day}" +%Y%W 2>/dev/null || echo "")
        month_key="${year}${month}"
        
        # Keep one per day for last 7 days
        if [[ $age -lt $((7 * one_day)) ]]; then
            if [[ -z "${keep_daily[$day_key]}" ]]; then
                keep_daily[$day_key]="$backup"
            else
                # Delete older backup for same day
                if [[ "$backup" < "${keep_daily[$day_key]}" ]]; then
                    rm -f "$backup"
                    log_info "Removed old backup: $(basename $backup)"
                else
                    rm -f "${keep_daily[$day_key]}"
                    log_info "Removed old backup: $(basename ${keep_daily[$day_key]})"
                    keep_daily[$day_key]="$backup"
                fi
            fi
            continue
        fi
        
        # Keep one per week for last 4 weeks
        if [[ $age -lt $((4 * one_week)) ]]; then
            if [[ -n "$week_key" ]]; then
                if [[ -z "${keep_weekly[$week_key]}" ]]; then
                    keep_weekly[$week_key]="$backup"
                else
                    rm -f "$backup"
                    log_info "Removed old backup: $(basename $backup)"
                fi
            fi
            continue
        fi
        
        # Keep one per month for last 12 months
        if [[ $age -lt $((12 * one_month)) ]]; then
            if [[ -z "${keep_monthly[$month_key]}" ]]; then
                keep_monthly[$month_key]="$backup"
            else
                rm -f "$backup"
                log_info "Removed old backup: $(basename $backup)"
            fi
            continue
        fi
        
        # Delete backups older than 12 months
        rm -f "$backup"
        log_info "Removed old backup: $(basename $backup)"
    done
}

cleanup_old_backups

# Count remaining backups
BACKUP_COUNT=$(ls -1 "$BACKUP_DIR"/backup_*.db 2>/dev/null | wc -l)
log_info "Total backups: $BACKUP_COUNT"

log_info "Backup complete"
