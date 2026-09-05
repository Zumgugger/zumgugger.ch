#!/bin/bash
# status.sh - Check WebsiteCMS service status
# Usage: ./status.sh <sitename>

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

if [[ -z "$1" ]]; then
    echo "Usage: $0 <sitename>"
    exit 1
fi

SITENAME="$1"
SITE_DIR="/var/www/${SITENAME}"
SERVICE_NAME="websitecms-${SITENAME}.service"
CONTAINER_NAME="websitecms-${SITENAME}"

echo "========================================"
echo "WebsiteCMS Status: $SITENAME"
echo "========================================"
echo ""

# Check systemd service
echo "Systemd Service:"
if [[ -f "/etc/systemd/system/$SERVICE_NAME" ]]; then
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        echo -e "  Status: ${GREEN}Active${NC}"
    else
        echo -e "  Status: ${RED}Inactive${NC}"
    fi
    echo "  Details: systemctl status $SERVICE_NAME"
else
    echo -e "  ${YELLOW}Not configured${NC}"
fi
echo ""

# Check Docker container
echo "Docker Container:"
if docker ps --format '{{.Names}}' | grep -q "$CONTAINER_NAME"; then
    echo -e "  Status: ${GREEN}Running${NC}"
    
    # Get container info
    CONTAINER_ID=$(docker ps -q -f "name=$CONTAINER_NAME")
    if [[ -n "$CONTAINER_ID" ]]; then
        echo "  Container ID: $CONTAINER_ID"
        echo "  Uptime: $(docker inspect -f '{{.State.StartedAt}}' $CONTAINER_ID)"
        
        # Health status
        HEALTH=$(docker inspect -f '{{.State.Health.Status}}' $CONTAINER_ID 2>/dev/null || echo "N/A")
        if [[ "$HEALTH" == "healthy" ]]; then
            echo -e "  Health: ${GREEN}$HEALTH${NC}"
        elif [[ "$HEALTH" == "unhealthy" ]]; then
            echo -e "  Health: ${RED}$HEALTH${NC}"
        else
            echo "  Health: $HEALTH"
        fi
    fi
else
    echo -e "  Status: ${RED}Not running${NC}"
fi
echo ""

# Check HTTP health endpoint
echo "HTTP Health Check:"
if [[ -d "$SITE_DIR" ]]; then
    PORT=$(grep -oP "^APP_PORT=\K[0-9]+" "$SITE_DIR/.env" 2>/dev/null || echo "30000")
    RESPONSE=$(curl -s -w "\n%{http_code}" "http://localhost:$PORT/health" 2>/dev/null || echo -e "\n000")
    HTTP_CODE=$(echo "$RESPONSE" | tail -1)
    BODY=$(echo "$RESPONSE" | head -n -1)
    
    echo "  URL: http://localhost:$PORT/health"
    if [[ "$HTTP_CODE" == "200" ]]; then
        echo -e "  HTTP Status: ${GREEN}$HTTP_CODE${NC}"
        echo "  Response: $BODY"
    else
        echo -e "  HTTP Status: ${RED}$HTTP_CODE${NC}"
    fi
else
    echo -e "  ${YELLOW}Site directory not found${NC}"
fi
echo ""

# Disk usage
echo "Disk Usage:"
if [[ -d "$SITE_DIR" ]]; then
    echo "  Site directory: $(du -sh "$SITE_DIR" 2>/dev/null | cut -f1)"
    if [[ -d "$SITE_DIR/data" ]]; then
        echo "  Data directory: $(du -sh "$SITE_DIR/data" 2>/dev/null | cut -f1)"
    fi
    if [[ -f "$SITE_DIR/data/site.db" ]]; then
        echo "  Database size: $(du -sh "$SITE_DIR/data/site.db" 2>/dev/null | cut -f1)"
    fi
fi
echo ""

# Recent logs
echo "Recent Logs (last 10 lines):"
if docker ps --format '{{.Names}}' | grep -q "$CONTAINER_NAME"; then
    docker logs --tail 10 "$CONTAINER_NAME" 2>&1 | sed 's/^/  /'
else
    echo "  No logs available (container not running)"
fi
echo ""
