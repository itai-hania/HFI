# Replace Tailscale with Public HTTPS via Azure DNS

**Date:** 2026-03-13
**Status:** Approved
**Approach:** Azure DNS hostname + Caddy auto-HTTPS (Let's Encrypt)

---

## Problem

The current deployment uses Tailscale as the sole ingress path to the HFI app on an Azure VM. This has proven unreliable and friction-heavy:
- Tailscale must be installed on every device
- Services crash or don't start reliably
- Debugging requires SSH'ing into the VM manually
- The user wants a normal URL that works from any browser on any device

## Decision

Replace Tailscale with a public HTTPS endpoint using:
- **Azure DNS label** on the VM's public IP (free, stable hostname)
- **Caddy auto-HTTPS** with Let's Encrypt (free TLS, auto-renewal)
- **Existing JWT auth** in the app as the access control layer

Result: `https://hfi-prod.israelcentral.cloudapp.azure.com`

## What Changes

### Files Modified

| File | Change |
|------|--------|
| `deploy/Caddyfile` | Replace `:80` with Azure hostname to enable auto-HTTPS |
| `deploy/docker-compose.prod.yml` | Caddy binds `0.0.0.0:80` + `0.0.0.0:443` instead of `127.0.0.1:80` |
| `deploy/.env.prod.example` | Replace Tailscale URLs with Azure DNS hostname |
| `docs/deploy/azure-private-production-runbook.md` | Remove Tailscale sections, add HTTPS setup |

### Files Deleted

| File | Reason |
|------|--------|
| `deploy/systemd/tailscale-serve.service` | Tailscale no longer used |

### One-Time Azure CLI Commands

```bash
# Add DNS label to public IP
az network public-ip update \
  --resource-group hfi-prod-ilc-rg \
  --name hfi-prod-vm-ip \
  --dns-name hfi-prod

# Open port 80 (HTTP, for Let's Encrypt ACME + redirect)
az network nsg rule create \
  --resource-group hfi-prod-ilc-rg \
  --nsg-name hfi-prod-vm-nsg \
  --name AllowHTTP \
  --priority 1010 \
  --access Allow \
  --direction Inbound \
  --protocol Tcp \
  --destination-port-ranges 80

# Open port 443 (HTTPS, main traffic)
az network nsg rule create \
  --resource-group hfi-prod-ilc-rg \
  --nsg-name hfi-prod-vm-nsg \
  --name AllowHTTPS \
  --priority 1020 \
  --access Allow \
  --direction Inbound \
  --protocol Tcp \
  --destination-port-ranges 443
```

### One-Time Tailscale Removal (SSH to VM)

```bash
sudo systemctl stop tailscale-serve
sudo systemctl disable tailscale-serve
sudo tailscale down
sudo apt remove -y tailscale
sudo rm /etc/systemd/system/tailscale-serve.service
sudo systemctl daemon-reload
```

### .env.prod Updates (on VM)

```bash
FRONTEND_BASE_URL=https://hfi-prod.israelcentral.cloudapp.azure.com
CORS_ORIGINS=https://hfi-prod.israelcentral.cloudapp.azure.com
```

## What Does NOT Change

- `deploy/scripts/deploy.sh` -- no changes needed
- `.github/workflows/deploy-prod.yml` -- no changes needed
- All other systemd units (backup, health check, restore check)
- All application code (API, frontend, processor, telegram-bot)
- All Docker images and build process
- CI/CD pipeline (merge to main -> auto-deploy)

## Architecture After

```
User (any browser)
    |
    | HTTPS :443
    v
Azure NSG (allow 80, 443, 22)
    |
    v
Caddy (auto-HTTPS via Let's Encrypt)
    |
    |-- /api*    -> api:8000
    |-- /health  -> api:8000
    |-- /*       -> frontend:3000
    v
Docker Compose internal network (hfi-private)
    |-- api (FastAPI + JWT auth)
    |-- frontend (Next.js)
    |-- processor (GPT-4o translation)
    |-- telegram-bot (briefs + alerts)
```

## Security

- **JWT auth** protects all API endpoints and the frontend login
- **HTTPS everywhere** via Caddy + Let's Encrypt (HTTP auto-redirects)
- **Azure NSG** limits inbound to ports 22 (SSH), 80, 443 only
- **No Tailscale dependency** -- simpler attack surface
- `.env.prod` stays `chmod 600` on the VM

## Rollback

If something goes wrong:
1. Re-close ports 80/443 in NSG: `az network nsg rule delete --name AllowHTTP/AllowHTTPS`
2. Revert the file changes in git
3. Re-install Tailscale if needed (but shouldn't be necessary)

## Cost Impact

- No change (~$20-26/month Azure VM)
- Removing Tailscale eliminates a free-tier dependency (simplification)
- Let's Encrypt certificates are free
