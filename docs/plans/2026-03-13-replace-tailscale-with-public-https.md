# Replace Tailscale with Public HTTPS Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace Tailscale private tunnel with Caddy auto-HTTPS using Azure DNS hostname, so the app is accessible from any browser at `https://hfi-prod.israelcentral.cloudapp.azure.com`.

**Architecture:** Caddy serves as the reverse proxy with automatic Let's Encrypt TLS. Azure NSG opens ports 80+443. The VM's public IP gets an Azure DNS label for a stable free hostname. Existing JWT auth protects the app. Tailscale is fully removed.

**Tech Stack:** Caddy 2.8, Docker Compose, Azure CLI, Let's Encrypt, systemd

**Design Doc:** `docs/plans/2026-03-13-replace-tailscale-with-public-https-design.md`

---

### Task 1: Update Caddyfile for auto-HTTPS

**Files:**
- Modify: `deploy/Caddyfile`

**Step 1: Update the Caddyfile**

Replace the entire content of `deploy/Caddyfile` with:

```caddyfile
hfi-prod.israelcentral.cloudapp.azure.com {
    encode gzip zstd

    @health path /health
    handle @health {
        reverse_proxy api:8000
    }

    @api path /api*
    handle @api {
        reverse_proxy api:8000
    }

    handle {
        reverse_proxy frontend:3000
    }
}
```

Key change: replacing `:80` with the full hostname tells Caddy to:
- Listen on ports 80 and 443
- Obtain a Let's Encrypt TLS certificate automatically
- Redirect all HTTP traffic to HTTPS
- Auto-renew the certificate every 60 days

**Step 2: Commit**

```bash
git add deploy/Caddyfile
git commit -m "feat(deploy): enable Caddy auto-HTTPS with Azure DNS hostname

Replace bare :80 listener with full hostname so Caddy automatically
obtains and renews Let's Encrypt TLS certificates."
```

---

### Task 2: Update Docker Compose to expose HTTPS ports

**Files:**
- Modify: `deploy/docker-compose.prod.yml`

**Step 1: Update the proxy service ports**

In `deploy/docker-compose.prod.yml`, change the `proxy` service's `ports` section.

Before:
```yaml
    ports:
      - "127.0.0.1:80:80"
```

After:
```yaml
    ports:
      - "80:80"
      - "443:443"
```

This exposes both HTTP (for Let's Encrypt ACME challenge + redirect) and HTTPS (main traffic) to the public internet. Previously only `127.0.0.1:80` was exposed because Tailscale handled external access.

No other changes to docker-compose.prod.yml are needed. The `caddy_data` volume already exists and will store the TLS certificates.

**Step 2: Commit**

```bash
git add deploy/docker-compose.prod.yml
git commit -m "feat(deploy): expose ports 80+443 publicly for direct HTTPS access

Remove 127.0.0.1 binding (was Tailscale-only). Caddy now serves
HTTPS directly to the internet."
```

---

### Task 3: Update .env.prod.example with new URL patterns

**Files:**
- Modify: `deploy/.env.prod.example`

**Step 1: Replace Tailscale URL references**

In `deploy/.env.prod.example`, change lines 27-29.

Before:
```bash
# FRONTEND_BASE_URL and CORS_ORIGINS must be your Tailscale HTTPS URL.
FRONTEND_BASE_URL=https://hfi-prod.tailnet-xyz.ts.net
CORS_ORIGINS=https://hfi-prod.tailnet-xyz.ts.net
```

After:
```bash
# FRONTEND_BASE_URL and CORS_ORIGINS use the Azure DNS hostname.
FRONTEND_BASE_URL=https://hfi-prod.israelcentral.cloudapp.azure.com
CORS_ORIGINS=https://hfi-prod.israelcentral.cloudapp.azure.com
```

**Step 2: Commit**

```bash
git add deploy/.env.prod.example
git commit -m "docs(deploy): update env example with Azure DNS hostname

Replace Tailscale URL placeholders with Azure DNS hostname pattern."
```

---

### Task 4: Delete Tailscale systemd service file

**Files:**
- Delete: `deploy/systemd/tailscale-serve.service`

**Step 1: Remove the file**

```bash
git rm deploy/systemd/tailscale-serve.service
```

**Step 2: Commit**

```bash
git commit -m "chore(deploy): remove tailscale-serve systemd unit

Tailscale is no longer used for ingress. Caddy handles HTTPS directly."
```

---

### Task 5: Update the production runbook

**Files:**
- Modify: `docs/deploy/azure-private-production-runbook.md`

**Step 1: Rewrite the runbook**

Replace the entire content of `docs/deploy/azure-private-production-runbook.md` with the updated version below. Key changes:
- Title: "Private" -> remove (it's now public with auth)
- Section 2: Remove Tailscale auth key prerequisite
- Section 3: Add DNS label + NSG rules for ports 80/443
- Section 5: Replace Tailscale URL instructions with Azure DNS hostname
- Section 6: DELETE entirely (was "Set Up Tailscale Private Access")
- Section 8: Remove `tailscale-serve.service` from systemd setup
- Section 12: Update acceptance checklist (reachable from public internet, HTTPS works)

Full replacement content:

```markdown
# HFI Azure Production Runbook

Date: 2026-03-13
Scope: single-VM deployment with Caddy auto-HTTPS in `israelcentral`.

## 1. What You Will Run

- Runtime: Docker Compose from `deploy/docker-compose.prod.yml`
- Always on: `proxy`, `frontend`, `api`, `processor`, `telegram-bot`
- Manual only: `scraper` (run on demand)
- HTTPS: Caddy auto-TLS via Let's Encrypt on Azure DNS hostname
- CI/CD: GitHub Actions self-hosted runner on the VM

## 2. Prerequisites

- Azure subscription + `az` CLI logged in
- GitHub repo admin access (to register self-hosted runner)
- A local SSH public key (`~/.ssh/id_ed25519.pub`)

## 3. Provision Azure Resources

Run from your local machine:

\```bash
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
\```

Get the VM public IP:

\```bash
VM_IP=$(az vm show -d -g "$RG" -n "$VM_NAME" --query publicIps -o tsv)
echo "$VM_IP"
\```

Add a DNS label and open HTTPS ports:

\```bash
# Stable hostname: hfi-prod.israelcentral.cloudapp.azure.com
az network public-ip update \
  --resource-group "$RG" \
  --name "${VM_NAME}PublicIP" \
  --dns-name hfi-prod

# Allow HTTP (Let's Encrypt ACME challenge + redirect to HTTPS)
az network nsg rule create \
  --resource-group "$RG" \
  --nsg-name "${VM_NAME}NSG" \
  --name AllowHTTP \
  --priority 1010 \
  --access Allow \
  --direction Inbound \
  --protocol Tcp \
  --destination-port-ranges 80

# Allow HTTPS (main app traffic)
az network nsg rule create \
  --resource-group "$RG" \
  --nsg-name "${VM_NAME}NSG" \
  --name AllowHTTPS \
  --priority 1020 \
  --access Allow \
  --direction Inbound \
  --protocol Tcp \
  --destination-port-ranges 443
\```

Verify DNS resolves:

\```bash
nslookup hfi-prod.israelcentral.cloudapp.azure.com
\```

## 4. Bootstrap VM Runtime

SSH into the VM:

\```bash
ssh azureuser@"$VM_IP"
\```

Install dependencies:

\```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git jq python3 python3-pip gzip

# Docker Engine + Compose plugin
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"
newgrp docker

docker --version
docker compose version
\```

Create workspace and clone:

\```bash
sudo mkdir -p /opt/hfi
sudo chown -R "$USER":"$USER" /opt/hfi
cd /opt/hfi
git clone <YOUR_REPO_URL> app
cd app
\```

## 5. Configure Production Environment

\```bash
cp deploy/.env.prod.example .env.prod
chmod 600 .env.prod
\```

Edit `.env.prod` and set at least:

- `ENVIRONMENT=production`
- `DASHBOARD_PASSWORD`
- `JWT_SECRET`
- `OPENAI_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `FRONTEND_BASE_URL=https://hfi-prod.israelcentral.cloudapp.azure.com`
- `CORS_ORIGINS=https://hfi-prod.israelcentral.cloudapp.azure.com`
- `NEXT_PUBLIC_API_URL=/api`
- `API_BASE_URL=http://api:8000`
- `API_ENFORCE_HTTPS_REDIRECT=false`
- `HOST_DATA_DIR=/opt/hfi/data`

## 6. First Deployment (Manual)

\```bash
cd /opt/hfi/app
ENV_FILE=/opt/hfi/app/.env.prod deploy/scripts/deploy.sh
\```

Verify:

\```bash
docker exec hfi-api python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5).read().decode())"
curl -I https://hfi-prod.israelcentral.cloudapp.azure.com/health
docker compose --env-file .env.prod -f deploy/docker-compose.prod.yml ps
\```

## 7. Enable Auto-Restart on Reboot (systemd)

\```bash
sudo cp deploy/systemd/*.service /etc/systemd/system/
sudo cp deploy/systemd/*.timer /etc/systemd/system/
sudo systemctl daemon-reload

sudo systemctl enable --now hfi-prod.service
sudo systemctl enable --now hfi-backup.timer
sudo systemctl enable --now hfi-restore-check.timer
sudo systemctl enable --now hfi-host-health.timer

sudo systemctl status hfi-prod.service
sudo systemctl list-timers --all | grep hfi-
\```

## 8. Configure GitHub Actions Self-Hosted Runner

On GitHub, generate a Linux self-hosted runner token for this repo. Then on VM:

\```bash
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
\```

The workflow `.github/workflows/deploy-prod.yml` will now deploy on every push to `main`.

## 9. Backups to Azure Blob (Optional but Recommended)

Create storage resources (run locally or on VM with `az login`):

\```bash
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
\```

Add to `.env.prod` on VM:

\```bash
AZURE_STORAGE_ACCOUNT=<storage_account>
AZURE_STORAGE_CONTAINER=hfi-db-backups
AZURE_STORAGE_SAS_TOKEN=<sas_token>
AZURE_BLOB_RETENTION_DAYS=30
\```

Test backup now:

\```bash
ENV_FILE=/opt/hfi/app/.env.prod deploy/scripts/backup_db.sh
\```

## 10. Operations Commands

Deploy current HEAD:

\```bash
ENV_FILE=/opt/hfi/app/.env.prod deploy/scripts/deploy.sh
\```

Run scraper manually (one-shot):

\```bash
ENV_FILE=/opt/hfi/app/.env.prod deploy/scripts/run_scraper_manual.sh
\```

Rollback to previous successful release:

\```bash
ENV_FILE=/opt/hfi/app/.env.prod deploy/scripts/rollback.sh
\```

Rollback to explicit SHA:

\```bash
ENV_FILE=/opt/hfi/app/.env.prod deploy/scripts/rollback.sh <git_sha>
\```

Run monthly restore drill manually:

\```bash
ENV_FILE=/opt/hfi/app/.env.prod deploy/scripts/restore_check.sh
\```

Check host guardrails manually:

\```bash
ENV_FILE=/opt/hfi/app/.env.prod deploy/scripts/host_health_check.sh
\```

## 11. Acceptance Checklist

- App opens at `https://hfi-prod.israelcentral.cloudapp.azure.com` from any browser
- HTTPS certificate is valid (padlock icon in browser)
- Login page appears, JWT auth works with dashboard password
- `curl https://hfi-prod.israelcentral.cloudapp.azure.com/health` returns `status=healthy`
- Telegram bot answers `/start`, `/brief`, `/write`
- Push to `main` triggers successful deployment workflow
- Reboot restores stack via `hfi-prod.service`
- Latest DB backup exists locally and in Blob (if configured)
```

**Step 2: Commit**

```bash
git add docs/deploy/azure-private-production-runbook.md
git commit -m "docs(deploy): rewrite runbook for public HTTPS (remove Tailscale)

Replace Tailscale-based private deployment with Caddy auto-HTTPS
using Azure DNS hostname. Add DNS label + NSG port setup instructions."
```

---

### Task 6: Run Azure CLI commands (manual — user action)

> **This task requires the user to run commands.** Claude cannot SSH into the VM or run Azure CLI commands.

**Step 1: Add DNS label to the VM's public IP**

The user needs to determine the actual name of their public IP and NSG resources. Run from local machine (or Azure Cloud Shell):

```bash
# List public IPs in the resource group to find the exact name
az network public-ip list --resource-group hfi-prod-ilc-rg --output table

# List NSGs to find the exact name
az network nsg list --resource-group hfi-prod-ilc-rg --output table
```

Then run with the actual resource names:

```bash
az network public-ip update \
  --resource-group hfi-prod-ilc-rg \
  --name <PUBLIC_IP_NAME> \
  --dns-name hfi-prod
```

**Step 2: Open HTTP + HTTPS ports in NSG**

```bash
az network nsg rule create \
  --resource-group hfi-prod-ilc-rg \
  --nsg-name <NSG_NAME> \
  --name AllowHTTP \
  --priority 1010 \
  --access Allow \
  --direction Inbound \
  --protocol Tcp \
  --destination-port-ranges 80

az network nsg rule create \
  --resource-group hfi-prod-ilc-rg \
  --nsg-name <NSG_NAME> \
  --name AllowHTTPS \
  --priority 1020 \
  --access Allow \
  --direction Inbound \
  --protocol Tcp \
  --destination-port-ranges 443
```

**Step 3: Verify DNS resolves**

```bash
nslookup hfi-prod.israelcentral.cloudapp.azure.com
```

Expected: resolves to the VM's public IP.

---

### Task 7: Remove Tailscale from VM (manual — user action)

> **This task requires the user to SSH into the VM.**

**Step 1: SSH into the VM**

```bash
ssh azureuser@<VM_IP>
```

**Step 2: Stop and remove Tailscale**

```bash
sudo systemctl stop tailscale-serve
sudo systemctl disable tailscale-serve
sudo tailscale down
sudo apt remove -y tailscale
sudo rm -f /etc/systemd/system/tailscale-serve.service
sudo systemctl daemon-reload
```

**Step 3: Update .env.prod on the VM**

```bash
sudo nano /opt/hfi/app/.env.prod
```

Change these two lines:
```bash
FRONTEND_BASE_URL=https://hfi-prod.israelcentral.cloudapp.azure.com
CORS_ORIGINS=https://hfi-prod.israelcentral.cloudapp.azure.com
```

---

### Task 8: Deploy and verify

> **After Tasks 1-5 are merged to `main` and Tasks 6-7 are done manually.**

**Step 1: Push changes to main**

The CI/CD pipeline (`.github/workflows/deploy-prod.yml`) will automatically:
1. Checkout the code on the VM
2. Run `deploy/scripts/deploy.sh`
3. Build new Docker images with the updated Caddyfile and compose ports
4. Bring up the stack
5. Run smoke checks

**Step 2: Verify HTTPS works (from any device)**

Open in a browser:
```
https://hfi-prod.israelcentral.cloudapp.azure.com
```

Expected: login page appears with valid HTTPS certificate (padlock icon).

**Step 3: Verify API health**

```bash
curl -s https://hfi-prod.israelcentral.cloudapp.azure.com/health | python3 -m json.tool
```

Expected: `{"status": "healthy", "build_version": "..."}`.

**Step 4: Verify Telegram bot**

Send `/start` to the Telegram bot. Expected: bot responds.

**Step 5: Test from phone**

Open `https://hfi-prod.israelcentral.cloudapp.azure.com` on phone browser. Expected: same login page, valid HTTPS.

---

### Task 9: Update CLAUDE.md references

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Update deployment references**

In `CLAUDE.md`, update any references to Tailscale URLs in the deployment sections to use `https://hfi-prod.israelcentral.cloudapp.azure.com`. Also update the "How do I deploy this?" section to reference Caddy auto-HTTPS instead of Tailscale.

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md deployment references for public HTTPS"
```
