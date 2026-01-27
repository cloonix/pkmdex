# Quick Start - Docker Deployment

## Prerequisites

- Docker and Docker Compose installed
- Domain name pointing to your server (optional, for HTTPS)
- Ports 80 and 443 open (for reverse proxy)

## Deployment Steps

### 1. Generate API Key

```bash
# Generate a secure API key
export PKMDEX_API_KEY=$(openssl rand -hex 32)

# Save it somewhere safe - you'll need it for CLI configuration
echo "API Key: $PKMDEX_API_KEY"
```

### 2. Create Environment File

```bash
# Copy example file
cp .env.example .env

# Edit and set your API key
nano .env
```

Set `PKMDEX_API_KEY` to the key you generated above.

### 3. Start Container

```bash
# Pull and start (using pre-built image from GitHub)
docker-compose up -d

# Or build locally
docker-compose build
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

The web app should now be running at http://localhost:8000

### 4. Configure Reverse Proxy (Optional)

#### Nginx Example

Create `/etc/nginx/sites-available/pkmdex`:

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
        
        # Increase timeout for sync operations
        proxy_read_timeout 300s;
        proxy_connect_timeout 300s;
    }
    
    # Increase max upload size for large collections
    client_max_body_size 10M;
}
```

Enable and restart:

```bash
sudo ln -s /etc/nginx/sites-available/pkmdex /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

#### Add SSL with Let's Encrypt

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

### 5. Configure CLI to Sync

On your local computer:

```bash
# Install pkmdex CLI (if not already installed)
pip install -e .

# Configure web API endpoint
pkm config set web_api_url https://your-domain.com/api/sync

# Set API key (must match PKMDEX_API_KEY from step 1)
pkm config set web_api_key <your-api-key>

# Verify configuration
pkm config show
```

### 6. Test Sync

```bash
# Export and push to web
pkm export --push

# You should see:
# ✓ Exported collection to: ...
# Pushing to https://your-domain.com/api/sync...
# ✓ Synced to web app successfully
```

### 7. Access Web Interface

Open your browser to:
- Local: http://localhost:8000
- Remote: https://your-domain.com

You should see your collection in the gallery!

## Container Management

### View Logs

```bash
# Follow logs in real-time
docker-compose logs -f

# View last 100 lines
docker-compose logs --tail=100
```

### Restart Container

```bash
docker-compose restart
```

### Stop Container

```bash
docker-compose down
```

### Update to Latest Version

```bash
# Pull latest code
git pull origin alpine

# Pull latest image
docker-compose pull

# Restart with new image
docker-compose down
docker-compose up -d
```

### Backup Database

```bash
# Database is in ./data/pokedex.db
cp data/pokedex.db data/pokedex.db.backup

# Or use Docker volume backup
docker run --rm -v pkmdex_data:/data -v $(pwd):/backup \
  alpine tar czf /backup/pkmdex-backup.tar.gz /data
```

### Restore Database

```bash
# Stop container
docker-compose down

# Restore database file
cp data/pokedex.db.backup data/pokedex.db

# Start container
docker-compose up -d
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose logs

# Common issues:
# - Missing PKMDEX_API_KEY: Set it in .env
# - Port conflict: Change PKMDEX_PORT in .env
# - Permission issues: Check data/ directory permissions
```

### Can't Sync from CLI

```bash
# Check configuration
pkm config show

# Verify web API is accessible
curl -I https://your-domain.com/api/stats

# Test authentication
curl -X POST https://your-domain.com/api/sync \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{}'

# Should return 422 (validation error) not 403 (auth error)
```

### Database Permissions

```bash
# Fix permissions on data directory
sudo chown -R $USER:$USER data/
chmod 755 data/
```

### Check Container Health

```bash
# View health status
docker inspect pkmdex-web | grep -A 10 Health

# Manual health check
curl http://localhost:8000/api/stats
```

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PKMDEX_API_KEY` | **Yes** | - | API key for sync authentication |
| `PKMDEX_PORT` | No | 8000 | Port to expose the web app |
| `PKMDEX_DATA_DIR` | No | ./data | Directory for database storage |

## Security Checklist

- [ ] Use a strong API key (32+ random characters)
- [ ] Enable HTTPS (Let's Encrypt)
- [ ] Configure firewall (only 80/443 open)
- [ ] Set up rate limiting in nginx
- [ ] Keep Docker images updated
- [ ] Regularly backup database
- [ ] Never commit .env to git
- [ ] Use nginx as reverse proxy (don't expose port 8000)

## Automated Sync (Optional)

### Using Cron

```bash
# Edit crontab
crontab -e

# Add hourly sync
0 * * * * /usr/local/bin/pkm export --push --quiet
```

### Using Systemd Timer

Create `~/.config/systemd/user/pkmdex-sync.timer`:

```ini
[Unit]
Description=Sync Pokemon cards to web hourly

[Timer]
OnCalendar=hourly
Persistent=true

[Install]
WantedBy=timers.target
```

Create `~/.config/systemd/user/pkmdex-sync.service`:

```ini
[Unit]
Description=Export Pokemon cards and push to web

[Service]
Type=oneshot
ExecStart=/usr/local/bin/pkm export --push --quiet
```

Enable:

```bash
systemctl --user enable pkmdex-sync.timer
systemctl --user start pkmdex-sync.timer
```

## Support

- Documentation: See DEPLOYMENT.md for detailed information
- Issues: https://github.com/cloonix/pkmdex/issues
- Logs: `docker-compose logs -f`

## Next Steps

1. ✅ Deploy container
2. ✅ Configure reverse proxy + SSL
3. ✅ Configure CLI sync
4. ✅ Test sync
5. Optional: Set up automated sync
6. Optional: Configure monitoring/alerts

Enjoy your Pokemon card collection web interface! 🎴
