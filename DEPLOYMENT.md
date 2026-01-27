# Deployment Guide: Pokemon Card Collection Web App

## Quick Start with Docker

### 1. Build the Docker Image

```bash
docker build -t pkmdex-web .
```

### 2. Run with Docker Compose

```bash
# Set your API key
export PKMDEX_API_KEY="your-secret-key-here"

# Start the container
docker-compose up -d
```

The web app will be available at `http://localhost:8000`

### 3. Configure CLI to Push to Web

```bash
# Set web API URL (use your actual domain)
pkm config set web_api_url https://your-domain.com/api/sync

# Set API key (must match PKMDEX_API_KEY in docker)
pkm config set web_api_key your-secret-key-here

# Test the sync
pkm export --push
```

## Production Deployment

### Environment Variables

- `PKMDEX_API_KEY`: **Required**. Secret key for API authentication.

### Volume Mounts

The container uses `/data` for the database. Mount a volume to persist data:

```yaml
volumes:
  - ./data:/data
```

### Reverse Proxy Setup

Example nginx configuration:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

For SSL with Let's Encrypt:

```bash
# Install certbot
apt install certbot python3-certbot-nginx

# Get certificate
certbot --nginx -d your-domain.com

# Nginx will auto-configure SSL
```

### Security Recommendations

1. **Use a strong API key**: Generate with `openssl rand -hex 32`
2. **Use HTTPS**: Always use SSL/TLS in production
3. **Firewall**: Only expose port 80/443, not 8000 directly
4. **Rate limiting**: Configure in your reverse proxy
5. **Keep API key secret**: Never commit to git

### Monitoring

Check container logs:

```bash
docker-compose logs -f pkmdex-web
```

Check container status:

```bash
docker-compose ps
```

### Updating

```bash
# Pull latest code
git pull origin alpine

# Rebuild and restart
docker-compose down
docker-compose build
docker-compose up -d
```

## CLI Sync Workflow

### Manual Sync

```bash
# Export and push to web
pkm export --push
```

### Automated Sync (Optional)

Using systemd timer (Linux):

```bash
# Create timer unit: ~/.config/systemd/user/pkmdex-sync.timer
[Unit]
Description=Sync Pokemon cards to web app hourly

[Timer]
OnCalendar=hourly
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
# Create service unit: ~/.config/systemd/user/pkmdex-sync.service
[Unit]
Description=Export Pokemon cards and push to web

[Service]
Type=oneshot
ExecStart=/usr/local/bin/pkm export --push --quiet
```

```bash
# Enable and start
systemctl --user enable pkmdex-sync.timer
systemctl --user start pkmdex-sync.timer
```

Using cron (any Unix):

```bash
# Edit crontab
crontab -e

# Add hourly sync (runs at minute 0 of every hour)
0 * * * * /usr/local/bin/pkm export --push --quiet
```

## Troubleshooting

### Authentication Errors

```
Error pushing to web API (HTTP 403)
```

**Solution**: Verify API keys match:
- CLI config: `pkm config get web_api_key`
- Docker env: Check `PKMDEX_API_KEY` in docker-compose.yml

### Connection Errors

```
Error connecting to web API: Name or service not known
```

**Solution**: Check web_api_url is correct:
```bash
pkm config get web_api_url
```

### Empty Collection in Web

**Solution**: Initial sync required:
```bash
pkm export --push
```

### Database Permissions

If database errors occur, check volume permissions:

```bash
# On host
chmod 755 ./data
```

## API Reference

### GET /api/stats

Returns collection statistics.

```bash
curl https://your-domain.com/api/stats
```

### GET /api/cards?language=de&set_id=me01

Returns card data with filters.

```bash
curl 'https://your-domain.com/api/cards?language=de'
```

### POST /api/sync

Sync collection from CLI export. Requires authentication.

```bash
curl -X POST https://your-domain.com/api/sync \
  -H "X-API-Key: your-secret-key" \
  -H "Content-Type: application/json" \
  -d @export.json
```

## Architecture

```
┌─────────────────────────────────────────┐
│  Local Computer(s) with Syncthing       │
│  ┌──────────────────────────────────┐  │
│  │  pkmdex CLI                      │  │
│  │  ~/.local/share/pkmdex/          │  │
│  │  - pokedex.db (synced)           │  │
│  │  - pkm add/list/search commands  │  │
│  └──────────────┬───────────────────┘  │
│                 │                        │
│                 │ pkm export --push      │
└─────────────────┼────────────────────────┘
                  │
                  │ HTTPS POST /api/sync
                  ▼
┌─────────────────────────────────────────┐
│  VPS / Server (Docker)                  │
│  ┌──────────────────────────────────┐  │
│  │  pkmdex-web container            │  │
│  │  - FastAPI app                   │  │
│  │  - Alpine.js frontend            │  │
│  │  - /data/pokedex.db (separate)   │  │
│  └──────────────────────────────────┘  │
│                                         │
│  https://your-domain.com                │
└─────────────────────────────────────────┘
```

## Features

### Web Interface

- **Dashboard**: Collection statistics
- **Gallery**: Card thumbnails (125px webp)
- **Modal**: High-quality card details
- **Filters**: Language and set selection
- **Analytics**: Coming soon (set completion, rarity charts, etc.)

### CLI Features

- `pkm config set web_api_url <url>` - Configure web endpoint
- `pkm config set web_api_key <key>` - Set API key
- `pkm export --push` - Export and sync to web
- `pkm export --push --quiet` - Silent sync (for automation)

## Support

For issues or questions:
- GitHub: https://github.com/cloonix/pkmdex
- Check logs: `docker-compose logs -f`
