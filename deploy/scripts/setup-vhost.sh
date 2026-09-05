#!/bin/bash
# setup-vhost.sh - Create Apache virtual host configuration
# Usage: ./setup-vhost.sh --domain example.com --sitename mysite --port 30000

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_DIR="$(dirname "$SCRIPT_DIR")/apache"

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
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Validate arguments
if [[ -z "$DOMAIN" ]] || [[ -z "$SITENAME" ]] || [[ -z "$PORT" ]]; then
    echo "Usage: $0 --domain <domain> --sitename <sitename> --port <port>"
    exit 1
fi

# Generate vhost configuration
VHOST_FILE="/etc/apache2/sites-available/${SITENAME}.conf"

echo "Creating Apache vhost: $VHOST_FILE"

# Read template and replace variables
sed -e "s/{{DOMAIN}}/$DOMAIN/g" \
    -e "s/{{SITENAME}}/$SITENAME/g" \
    -e "s/{{APP_PORT}}/$PORT/g" \
    "$TEMPLATE_DIR/vhost.conf" > "$VHOST_FILE"

echo "Apache vhost created successfully"
echo "Run 'sudo a2ensite ${SITENAME}.conf && sudo systemctl reload apache2' to enable"
