# Deploying Triptic to Fly.io

This guide walks you through deploying Triptic to Fly.io with persistent storage.

## Prerequisites

1. **Install Fly.io CLI:**
   ```bash
   curl -L https://fly.io/install.sh | sh
   ```

2. **Sign up / Login:**
   ```bash
   fly auth signup  # or: fly auth login
   ```

## Initial Setup

### 1. Configure Your App Name

Edit `fly.toml` and change the app name to something unique:

```toml
app = "your-unique-triptic-name"  # Must be globally unique on Fly.io
```

### 2. Choose Your Region

Find the region closest to you:
```bash
fly platform regions
```

Update `fly.toml`:
```toml
primary_region = "sjc"  # e.g., sjc (San Jose), iad (Virginia), lhr (London)
```

### 3. Launch Your App

```bash
fly launch --no-deploy
```

This creates your app on Fly.io without deploying yet.

### 4. Create Persistent Volume

Create a volume for storing the SQLite database and images:

```bash
fly volumes create triptic_data --size 3 --region sjc
```

Replace `sjc` with your chosen region from step 2.

**Important:** The volume name `triptic_data` must match the `source` in `fly.toml` under `[mounts]`.

### 5. Set Environment Variables (Optional)

If you're using the image generation features:

```bash
fly secrets set GEMINI_API_KEY=your_api_key_here
```

### 6. Deploy!

```bash
fly deploy
```

This will:
- Build the Docker image
- Push it to Fly.io
- Create a machine with persistent storage
- Start your app

### 7. Open Your App

```bash
fly open
```

Or visit: `https://your-app-name.fly.dev`

## Important URLs

After deployment, access your app at:

- **Wall View:** `https://your-app.fly.dev/wall.html`
- **Playlists:** `https://your-app.fly.dev/playlists.html`
- **Settings:** `https://your-app.fly.dev/settings.html`
- **Individual Screens:**
  - Left: `https://your-app.fly.dev/#left`
  - Center: `https://your-app.fly.dev/#center`
  - Right: `https://your-app.fly.dev/#right`

## Updating Your Deployment

Whenever you make changes:

```bash
git add .
git commit -m "Your changes"
fly deploy
```

## Monitoring

### View Logs
```bash
fly logs
```

### Check Status
```bash
fly status
```

### SSH into Machine
```bash
fly ssh console
```

### Check Volume
```bash
fly volumes list
```

## Scaling

### Increase Storage
```bash
fly volumes extend triptic_data --size 10  # Extend to 10GB
```

### Increase RAM
Edit `fly.toml`:
```toml
[[vm]]
  size = "shared-cpu-2x"  # 512MB RAM ($5/month)
  memory = "512mb"
```

Then: `fly deploy`

## Cost Optimization

**Free Tier Includes:**
- 3 shared-cpu-1x VMs (256MB RAM)
- 3GB persistent storage
- 160GB outbound transfer

**Your app will stay free if:**
- You use 1 VM with 256MB RAM
- Keep storage under 3GB
- Don't exceed bandwidth limits

**Auto-scaling to zero:**
The app is configured to scale to zero when idle:
```toml
auto_stop_machines = "stop"
min_machines_running = 0
```

## Troubleshooting

### App won't start
Check logs:
```bash
fly logs
```

### Database errors
Ensure volume is mounted:
```bash
fly ssh console
ls -la /data
```

### Out of storage
Check usage:
```bash
fly ssh console
df -h /data
```

Extend if needed:
```bash
fly volumes extend triptic_data --size 5
```

### Health check failing
Increase grace period in `fly.toml`:
```toml
[[http_service.checks]]
  grace_period = "30s"  # Give app more time to start
```

## Database Backup

### Manual Backup
```bash
fly ssh console
tar -czf /tmp/backup.tar.gz /data
exit

fly ssh sftp get /tmp/backup.tar.gz ./backup-$(date +%Y%m%d).tar.gz
```

### Restore Backup
```bash
fly ssh sftp shell
put ./backup-20250101.tar.gz /tmp/backup.tar.gz
exit

fly ssh console
cd /data
tar -xzf /tmp/backup.tar.gz --strip-components=1
exit

fly apps restart
```

## Migration from Local

If you have local data to migrate:

1. **Backup local data:**
   ```bash
   tar -czf triptic-backup.tar.gz ~/.triptic/
   ```

2. **Upload to Fly.io:**
   ```bash
   fly ssh sftp shell
   put ./triptic-backup.tar.gz /tmp/backup.tar.gz
   exit
   ```

3. **Restore on Fly.io:**
   ```bash
   fly ssh console
   cd /data
   tar -xzf /tmp/backup.tar.gz --strip-components=2
   ls -la  # Verify files are there
   exit
   ```

4. **Restart app:**
   ```bash
   fly apps restart
   ```

## Support

- Fly.io Docs: https://fly.io/docs/
- Fly.io Community: https://community.fly.io/
- Triptic Issues: https://github.com/yourusername/triptic/issues

## Next Steps

- Set up a custom domain: `fly certs add yourdomain.com`
- Enable metrics: `fly dashboard`
- Set up alerts: https://fly.io/docs/reference/metrics/
