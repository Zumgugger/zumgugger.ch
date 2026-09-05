#!/bin/bash
# allocate-port.sh - Allocate an available port for a new site
# Usage: ./allocate-port.sh [--min 30000] [--max 30999]
# Returns: Available port number or exits with error

set -e

# Default port range
MIN_PORT=30000
MAX_PORT=30999

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --min)
            MIN_PORT="$2"
            shift 2
            ;;
        --max)
            MAX_PORT="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
    esac
done

# Get list of used ports in the range
get_used_ports() {
    # Check netstat for listening ports
    (netstat -tlnp 2>/dev/null || ss -tlnp 2>/dev/null) | \
        grep -oP "127\.0\.0\.1:\K[0-9]+" | \
        sort -n | uniq
    
    # Also check docker containers
    docker ps --format '{{.Ports}}' 2>/dev/null | \
        grep -oP "127\.0\.0\.1:\K[0-9]+" | \
        sort -n | uniq
    
    # Also check .env files in /var/www/*/
    for env_file in /var/www/*/.env; do
        if [[ -f "$env_file" ]]; then
            grep -oP "^APP_PORT=\K[0-9]+" "$env_file" 2>/dev/null
        fi
    done
}

# Find first available port
USED_PORTS=$(get_used_ports | sort -n | uniq)

for PORT in $(seq $MIN_PORT $MAX_PORT); do
    if ! echo "$USED_PORTS" | grep -q "^${PORT}$"; then
        # Double-check port is not in use
        if ! (netstat -tlnp 2>/dev/null || ss -tlnp 2>/dev/null) | grep -q ":${PORT} "; then
            echo $PORT
            exit 0
        fi
    fi
done

echo "No available ports in range $MIN_PORT-$MAX_PORT" >&2
exit 1
