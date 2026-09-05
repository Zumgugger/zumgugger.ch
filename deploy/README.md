# Deployment Documentation

This directory contains all deployment scripts and configuration templates for WebsiteCMS.

## Directory Structure

```
deploy/
├── README.md           # This file
├── apache/
│   └── vhost.conf      # Apache virtual host template
├── systemd/
│   └── websitecms.service  # Systemd service template
└── scripts/
    ├── deploy.sh       # Main deployment script
    ├── setup-vhost.sh  # Apache vhost setup
    ├── setup-ssl.sh    # SSL/Certbot configuration
    ├── allocate-port.sh # Port allocation for multi-site
    ├── backup.sh       # Database backup script
    ├── restore.sh      # Database restore script
    ├── start.sh        # Start service
    ├── stop.sh         # Stop service
    ├── restart.sh      # Restart service
    └── status.sh       # Check service status
```

## Prerequisites

- Ubuntu 20.04+ or Debian 11+
- Docker and Docker Compose installed
- Apache2 installed
- Certbot installed (for SSL)
- Root or sudo access

## Quick Deployment

```bash
# Clone the repository to the target server
git clone <repository-url> /tmp/websitecms

# Run the deployment script
sudo ./deploy/scripts/deploy.sh --domain example.com --sitename mysite

# Or with custom port
sudo ./deploy/scripts/deploy.sh --domain example.com --sitename mysite --port 30001
```

## Manual Deployment Steps

### 1. Prepare the Server

```bash
# Install dependencies
sudo apt update
sudo apt install -y docker.io docker-compose apache2 certbot python3-certbot-apache

# Enable required Apache modules
sudo a2enmod proxy proxy_http rewrite headers ssl

# Start Docker
sudo systemctl enable docker
sudo systemctl start docker
```

### 2. Deploy the Site

```bash
# Create site directory
SITENAME="mysite"
sudo mkdir -p /var/www/${SITENAME}

# Copy application files
sudo cp -r . /var/www/${SITENAME}/
cd /var/www/${SITENAME}

# Create .env from example
sudo cp .env.example .env
sudo nano .env  # Edit configuration

# Set permissions
sudo chown -R root:www-data /var/www/${SITENAME}
sudo chmod -R 755 /var/www/${SITENAME}
sudo chown -R 1000:1000 /var/www/${SITENAME}/data
sudo chmod -R 775 /var/www/${SITENAME}/data
```

### 3. Configure Apache

```bash
# Generate vhost config
DOMAIN="example.com"
PORT="30000"
sudo ./deploy/scripts/setup-vhost.sh --domain ${DOMAIN} --sitename ${SITENAME} --port ${PORT}

# Enable the site
sudo a2ensite ${SITENAME}.conf
sudo apachectl configtest
sudo systemctl reload apache2
```

### 4. Configure SSL

```bash
# Obtain SSL certificate
sudo certbot --apache -d ${DOMAIN} -d www.${DOMAIN}
```

### 5. Start the Service

```bash
# Install and start systemd service
sudo ./deploy/scripts/start.sh ${SITENAME}
```

## Environment Variables

See `.env.example` for all available environment variables. Key production settings:

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Session encryption key | **Required** |
| `DEBUG` | Debug mode | `false` |
| `LOG_LEVEL` | Logging level | `WARNING` |
| `SMTP_*` | Email configuration | Required for contact form |
| `SMS_ENABLED` | Enable SMS notifications | `false` |
| `CAPTCHA_ENABLED` | Enable Turnstile CAPTCHA | `false` |
| `MAINTENANCE_MODE` | Show maintenance page | `false` |

## Backup & Recovery

### Automated Backups

Backups are configured to run hourly via cron:

```bash
# Add to crontab
sudo crontab -e
# Add line:
0 * * * * /var/www/mysite/deploy/scripts/backup.sh /var/www/mysite
```

### Manual Backup

```bash
sudo ./deploy/scripts/backup.sh /var/www/mysite
```

### Restore from Backup

```bash
sudo ./deploy/scripts/restore.sh /var/www/mysite /var/www/mysite/data/backups/backup_20260203_120000.db
```

## Monitoring

### Health Check

```bash
curl http://localhost:30000/health
# Returns: {"status": "ok", "db": "connected"}
```

### Service Status

```bash
sudo ./deploy/scripts/status.sh mysite
```

### View Logs

```bash
# Docker logs
docker logs websitecms-mysite

# Or via journalctl (if using systemd)
sudo journalctl -u websitecms-mysite.service -f
```

## Troubleshooting

### Container won't start

1. Check logs: `docker logs websitecms-mysite`
2. Verify .env file exists and has correct values
3. Check port availability: `netstat -tlnp | grep 30000`

### SSL certificate issues

1. Verify DNS points to server: `dig +short example.com`
2. Check Certbot logs: `sudo certbot certificates`
3. Renew manually: `sudo certbot renew --dry-run`

### Database issues

1. Check file permissions: `ls -la /var/www/mysite/data/`
2. Verify SQLite file: `sqlite3 /var/www/mysite/data/site.db ".tables"`

## Multi-Site Deployment

To deploy multiple sites on the same server:

1. Each site gets a unique port (30000-30999 range)
2. Use `allocate-port.sh` to find available ports
3. Each site has its own systemd service unit

```bash
# Deploy first site
sudo ./deploy/scripts/deploy.sh --domain site1.com --sitename site1 --port 30000

# Deploy second site
sudo ./deploy/scripts/deploy.sh --domain site2.com --sitename site2 --port 30001
```
