# HFI Azure Private Production Runbook

Date: 2026-03-12
Scope: single-VM private deployment (Tailscale-only ingress) in `israelcentral`.

## 1. What You Will Run

- Runtime: Docker Compose from `deploy/docker-compose.prod.yml`
- Always on: `proxy`, `frontend`, `api`, `processor`, `telegram-bot`
- Manual only: `scraper` (run on demand)
- Private access: `tailscale serve` HTTPS -> `127.0.0.1:80`
- CI/CD: GitHub Actions self-hosted runner on the VM

## 2. Prerequisites

- Azure subscription + `az` CLI logged in
- GitHub repo admin access (to register self-hosted runner)
- Tailscale tailnet + reusable auth key
- A local SSH public key (`~/.ssh/id_ed25519.pub`)

## 3. Provision Azure Resources

Run from your local machine:

```bash
# Variables
RG=hfi-prod-ilc-rg
LOCATION=israelcentral
VM_NAME=hfi-prod-vm
ADMIN_USER=azureuser

az group create --name "$RG" --location "$LOCATION"

az vm create \
  --resource-group "$RG" \
  --name "$VM_NAME" \
  --image Ubuntu2204 \
  --size Standard_B1ms \
  --os-disk-size-gb 32 \
  --storage-sku StandardSSD_LRS \
  --admin-username "$ADMIN_USER" \
  --ssh-key-values ~/.ssh/id_ed25519.pub \
  --public-ip-sku Standard \
  --nsg-rule SSH
```

Get the VM public IP:

```bash
VM_IP=$(az vm show -d -g "$RG" -n "$VM_NAME" --query publicIps -o tsv)
echo "$VM_IP"
```

## 4. Bootstrap VM Runtime

SSH into the VM:

```bash
ssh azureuser@"$VM_IP"
```

Install dependencies:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git jq python3 python3-pip gzip

# Docker Engine + Compose plugin
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"
newgrp docker

docker --version
docker compose version
```

Create workspace and clone:

```bash
sudo mkdir -p /opt/hfi
sudo chown -R "$USER":"$USER" /opt/hfi
cd /opt/hfi
git clone <YOUR_REPO_URL> app
cd app
```

## 5. Configure Production Environment

```bash
cp deploy/.env.prod.example .env.prod
chmod 600 .env.prod
```

Edit `.env.prod` and set at least:

- `ENVIRONMENT=production`
- `DASHBOARD_PASSWORD`
- `JWT_SECRET`
- `OPENAI_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `FRONTEND_BASE_URL` (your Tailscale HTTPS URL)
- `CORS_ORIGINS` (same Tailscale HTTPS URL)
- `NEXT_PUBLIC_API_URL=/api`
- `API_BASE_URL=http://api:8000`
- `API_ENFORCE_HTTPS_REDIRECT=false`
- `HOST_DATA_DIR=/opt/hfi/data`

## 6. Set Up Tailscale Private Access

Install and join tailnet on the VM:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up --auth-key <TAILSCALE_AUTH_KEY> --ssh
tailscale status
```

Enable private HTTPS publishing:

```bash
sudo tailscale serve --bg --https=443 http://127.0.0.1:80
tailscale serve status
```

Find your private URL:

```bash
tailscale status --self
```

Use that URL for both `FRONTEND_BASE_URL` and `CORS_ORIGINS` in `.env.prod`.

## 7. First Deployment (Manual)

```bash
cd /opt/hfi/app
ENV_FILE=/opt/hfi/app/.env.prod deploy/scripts/deploy.sh
```

Verify:

```bash
docker exec hfi-api python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5).read().decode())"
curl -I http://127.0.0.1/
docker compose --env-file .env.prod -f deploy/docker-compose.prod.yml ps
```

## 8. Enable Auto-Restart on Reboot (systemd)

```bash
sudo cp deploy/systemd/*.service /etc/systemd/system/
sudo cp deploy/systemd/*.timer /etc/systemd/system/
sudo systemctl daemon-reload

sudo systemctl enable --now hfi-prod.service
sudo systemctl enable --now tailscale-serve.service
sudo systemctl enable --now hfi-backup.timer
sudo systemctl enable --now hfi-restore-check.timer
sudo systemctl enable --now hfi-host-health.timer

sudo systemctl status hfi-prod.service
sudo systemctl list-timers --all | grep hfi-
```

## 9. Configure GitHub Actions Self-Hosted Runner

On GitHub, generate a Linux self-hosted runner token for this repo. Then on VM:

```bash
mkdir -p /opt/actions-runner && cd /opt/actions-runner

# Use the latest runner package from GitHub docs if version changes
curl -o actions-runner-linux-x64-2.322.0.tar.gz -L \
  https://github.com/actions/runner/releases/download/v2.322.0/actions-runner-linux-x64-2.322.0.tar.gz
tar xzf actions-runner-linux-x64-2.322.0.tar.gz

./config.sh \
  --url https://github.com/<OWNER>/<REPO> \
  --token <RUNNER_TOKEN> \
  --name hfi-prod-vm \
  --labels hfi-prod \
  --work _work

sudo ./svc.sh install
sudo ./svc.sh start
sudo ./svc.sh status
```

The workflow `.github/workflows/deploy-prod.yml` will now deploy on every push to `main`.

## 10. Backups to Azure Blob (Optional but Recommended)

Create storage resources (run locally or on VM with `az login`):

```bash
RG=hfi-prod-ilc-rg
STORAGE_ACCOUNT=<globally-unique-storage-name>
CONTAINER=hfi-db-backups

az storage account create \
  --resource-group "$RG" \
  --name "$STORAGE_ACCOUNT" \
  --location israelcentral \
  --sku Standard_LRS

az storage container create \
  --account-name "$STORAGE_ACCOUNT" \
  --name "$CONTAINER" \
  --auth-mode login

SAS=$(az storage container generate-sas \
  --account-name "$STORAGE_ACCOUNT" \
  --name "$CONTAINER" \
  --permissions acdlrw \
  --expiry 2030-01-01T00:00:00Z \
  --https-only \
  --output tsv)

echo "$SAS"
```

Add to `.env.prod` on VM:

```bash
AZURE_STORAGE_ACCOUNT=<storage_account>
AZURE_STORAGE_CONTAINER=hfi-db-backups
AZURE_STORAGE_SAS_TOKEN=<sas_token>
AZURE_BLOB_RETENTION_DAYS=30
```

Test backup now:

```bash
ENV_FILE=/opt/hfi/app/.env.prod deploy/scripts/backup_db.sh
```

## 11. Operations Commands

Deploy current HEAD:

```bash
ENV_FILE=/opt/hfi/app/.env.prod deploy/scripts/deploy.sh
```

Run scraper manually (one-shot):

```bash
ENV_FILE=/opt/hfi/app/.env.prod deploy/scripts/run_scraper_manual.sh
```

Rollback to previous successful release:

```bash
ENV_FILE=/opt/hfi/app/.env.prod deploy/scripts/rollback.sh
```

Rollback to explicit SHA:

```bash
ENV_FILE=/opt/hfi/app/.env.prod deploy/scripts/rollback.sh <git_sha>
```

Run monthly restore drill manually:

```bash
ENV_FILE=/opt/hfi/app/.env.prod deploy/scripts/restore_check.sh
```

Check host guardrails manually:

```bash
ENV_FILE=/opt/hfi/app/.env.prod deploy/scripts/host_health_check.sh
```

## 12. Acceptance Checklist

- App opens from a tailnet device at your Tailscale URL
- App is not reachable from public internet
- `docker exec hfi-api ... /health ...` returns `status=healthy`
- Telegram bot answers `/start`, `/brief`, `/write`
- Push to `main` triggers successful deployment workflow
- Reboot restores stack (`hfi-prod.service`) and Tailscale serve
- Latest DB backup exists locally and in Blob (if configured)
