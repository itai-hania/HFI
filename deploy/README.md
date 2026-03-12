# Production Deployment Assets

This folder contains the private-production deployment assets for Azure single-VM runtime.

## Files

- `docker-compose.prod.yml`: canonical production stack entrypoint.
- `Caddyfile`: reverse proxy (`/api` -> API, `/` -> frontend).
- `.env.prod.example`: production env template.
- `scripts/deploy.sh`: build + deploy + smoke checks + release tracking.
- `scripts/rollback.sh`: redeploy previous known-good SHA.
- `scripts/run_scraper_manual.sh`: manual one-shot scraper run.
- `scripts/backup_db.sh`: SQLite backup and optional Azure Blob upload.
- `scripts/restore_check.sh`: restore drill from backup and API-read validation.
- `scripts/host_health_check.sh`: disk/memory/service guardrail checks.
- `systemd/`: systemd units and timers for boot resilience + scheduled ops.

## Quick Usage

```bash
# VM first-time setup
cp deploy/.env.prod.example .env.prod
chmod 600 .env.prod

# Deploy current code
ENV_FILE=$PWD/.env.prod deploy/scripts/deploy.sh

# Run scraper manually when needed
ENV_FILE=$PWD/.env.prod deploy/scripts/run_scraper_manual.sh

# Roll back to previous successful release
ENV_FILE=$PWD/.env.prod deploy/scripts/rollback.sh

# Run backup now (nightly runs should use timer)
ENV_FILE=$PWD/.env.prod deploy/scripts/backup_db.sh
```
