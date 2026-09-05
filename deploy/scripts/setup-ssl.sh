#!/bin/bash
# setup-ssl.sh - Configure Let's Encrypt SSL certificate
# Usage: ./setup-ssl.sh --domain example.com --sitename mysite

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

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
        --email)
            EMAIL="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Validate arguments
if [[ -z "$DOMAIN" ]] || [[ -z "$SITENAME" ]]; then
    echo "Usage: $0 --domain <domain> --sitename <sitename> [--email <email>]"
    exit 1
fi

# Default email (use domain-based if not provided)
if [[ -z "$EMAIL" ]]; then
    EMAIL="admin@${DOMAIN}"
fi

log_info "Setting up SSL for $DOMAIN"

# Check if certificate already exists
if [[ -d "/etc/letsencrypt/live/$DOMAIN" ]]; then
    log_warn "Certificate already exists for $DOMAIN"
    log_info "To renew, run: sudo certbot renew"
    exit 0
fi

# Obtain certificate using Apache plugin
log_info "Obtaining SSL certificate..."
certbot --apache \
    --non-interactive \
    --agree-tos \
    --email "$EMAIL" \
    --redirect \
    -d "$DOMAIN" \
    -d "www.$DOMAIN" || {
        log_error "Failed to obtain SSL certificate"
        log_info "Make sure DNS is properly configured and ports 80/443 are accessible"
        exit 1
    }

log_info "SSL certificate obtained successfully"

# Update HSTS header to longer duration (optional - after testing)
# Uncomment to increase HSTS max-age after initial testing
# VHOST_FILE="/etc/apache2/sites-available/${SITENAME}-le-ssl.conf"
# if [[ -f "$VHOST_FILE" ]]; then
#     sed -i 's/max-age=86400/max-age=31536000/' "$VHOST_FILE"
#     systemctl reload apache2
# fi

log_info "SSL setup complete!"
echo ""
echo "Certificate files:"
echo "  Fullchain: /etc/letsencrypt/live/$DOMAIN/fullchain.pem"
echo "  Private key: /etc/letsencrypt/live/$DOMAIN/privkey.pem"
echo ""
echo "Auto-renewal is configured via systemd timer"
echo "Check status: sudo certbot certificates"
