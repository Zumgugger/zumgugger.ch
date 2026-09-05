#!/bin/bash
# Update a Git-backed WebsiteCMS deployment and rebuild its container.
# Usage: sudo ./update.sh <sitename> [branch]

set -euo pipefail

SITENAME="${1:-}"
BRANCH="${2:-master}"
SITE_DIR="/var/www/${SITENAME}"

if [[ -z "$SITENAME" ]]; then
    echo "Usage: $0 <sitename> [branch]" >&2
    exit 1
fi

[[ $EUID -eq 0 ]] || { echo "Run this script as root." >&2; exit 1; }
[[ -d "$SITE_DIR" ]] || { echo "Site directory does not exist: $SITE_DIR" >&2; exit 1; }
git -C "$SITE_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1 || {
    echo "$SITE_DIR is not a Git working tree. Run adopt-git-repository.sh once first." >&2
    exit 1
}

if [[ -n "$(git -C "$SITE_DIR" status --porcelain --untracked-files=no)" ]]; then
    echo "Tracked local changes found in $SITE_DIR. Commit or discard them before updating." >&2
    exit 1
fi

echo "Updating $SITENAME from origin/$BRANCH"
git -C "$SITE_DIR" fetch --prune origin "$BRANCH"
git -C "$SITE_DIR" pull --ff-only origin "$BRANCH"

mkdir -p "$SITE_DIR/data"
chown -R 1000:1000 "$SITE_DIR/data"

(
    cd "$SITE_DIR"
    COMPOSE_PROJECT_NAME="websitecms-${SITENAME}" \
        docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
)

APP_PORT=$(grep -E '^APP_PORT=' "$SITE_DIR/.env" 2>/dev/null | tail -n 1 | cut -d= -f2-)
APP_PORT="${APP_PORT:-30000}"
echo "Update complete. Verify with: curl http://127.0.0.1:${APP_PORT}/health"