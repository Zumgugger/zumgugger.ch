#!/bin/bash
# Convert a copied deployment into a Git working tree without replacing live data.
# Usage: sudo ./adopt-git-repository.sh --sitename mysite --repository <git-url> [--branch master]

set -euo pipefail

INSTALL_DIR="/var/www"
BRANCH="master"
SITENAME=""
REPOSITORY=""

show_usage() {
    echo "Usage: $0 --sitename <name> --repository <git-url> [--branch <branch>]"
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --sitename) SITENAME="$2"; shift 2 ;;
        --repository) REPOSITORY="$2"; shift 2 ;;
        --branch) BRANCH="$2"; shift 2 ;;
        -h|--help) show_usage ;;
        *) echo "Unknown option: $1" >&2; show_usage ;;
    esac
done

[[ $EUID -eq 0 ]] || { echo "Run this script as root." >&2; exit 1; }
[[ -n "$SITENAME" && -n "$REPOSITORY" ]] || show_usage

SITE_DIR="${INSTALL_DIR}/${SITENAME}"
[[ -d "$SITE_DIR" ]] || { echo "Site directory does not exist: $SITE_DIR" >&2; exit 1; }

if git -C "$SITE_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "$SITE_DIR is already a Git working tree. Use update.sh instead." >&2
    exit 1
fi

command -v git >/dev/null || { echo "git is required." >&2; exit 1; }
command -v rsync >/dev/null || { echo "rsync is required." >&2; exit 1; }
command -v docker >/dev/null || { echo "docker is required." >&2; exit 1; }

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="${INSTALL_DIR}/${SITENAME}.pre-git.${TIMESTAMP}"
STAGING_DIR=$(mktemp -d)

cleanup() {
    rm -rf "$STAGING_DIR"
}
trap cleanup EXIT

echo "Creating recovery backup at $BACKUP_DIR"
mkdir -p "$BACKUP_DIR"
backup_paths=(data)
[[ -f "$SITE_DIR/.env" ]] && backup_paths+=(.env)
[[ -f "$SITE_DIR/site.config.json" ]] && backup_paths+=(site.config.json)
tar -C "$SITE_DIR" -czf "$BACKUP_DIR/live-state.tar.gz" "${backup_paths[@]}"

echo "Fetching ${REPOSITORY} (${BRANCH})"
git clone --branch "$BRANCH" --single-branch "$REPOSITORY" "$STAGING_DIR/repository"

echo "Stopping the current container"
(
    cd "$SITE_DIR"
    docker compose -f docker-compose.yml -f docker-compose.prod.yml down
)

echo "Installing tracked application files while preserving data/ and .env"
rsync -a --delete --exclude='data/' --exclude='.env' \
    "$STAGING_DIR/repository/" "$SITE_DIR/"

mkdir -p "$SITE_DIR/data"
chown -R 1000:1000 "$SITE_DIR/data"

echo "Starting the Git-backed deployment"
(
    cd "$SITE_DIR"
    docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
)

echo "Migration complete. Live state backup: $BACKUP_DIR/live-state.tar.gz"
echo "Future updates: $SITE_DIR/deploy/scripts/update.sh $SITENAME"