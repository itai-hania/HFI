# HFI Azure Production Plan (Private, Single-VM, Budget-Capped)

Date: 2026-03-12
Status: Approved planning document

## Summary

- Deploy on one Azure VM in `israelcentral` using Docker Compose.
- Keep the app private via Tailscale (no public app exposure).
- Keep `frontend`, `api`, `processor`, and `telegram-bot` always on.
- Keep scraper manual for v1 (scraper = X/Twitter + RSS/news ingestion).
- Use GitHub Actions with a self-hosted runner on the VM, so every push to `main` deploys automatically.
- Target Azure spend: about `$20` to `$26` per month (OpenAI API usage excluded).

## Goals and Success Criteria

### Goals

- Production-grade deployment on Azure with minimal monthly cost.
- Private access only for the owner.
- Always-on service runtime for app and Telegram workflows.
- Zero-touch deployment on push to `main`.

### Success Criteria

- App is reachable only through private Tailscale access.
- Telegram bot works continuously (`/start`, `/brief`, `/write` flow).
- Every push to `main` updates deployment automatically.
- VM reboot restores the whole stack automatically.
- Nightly database backups are created and restorable.

## Minimal Target Architecture

### Azure Resources

- Resource Group: `hfi-prod-ilc-rg`
- Region: `israelcentral`
- VM: `Standard_B1ms` (Linux)
- Disk: Standard SSD `E4` (32 GiB) initial size
- Storage Account + Blob container for database backups
- NSG: no public application ingress

### Runtime on VM

- Docker Engine + Docker Compose
- Reverse proxy (Caddy or Nginx) routing:
  - `/` -> frontend
  - `/api` -> api
- Tailscale installed on VM and user devices
- Services:
  - always-on: `frontend`, `api`, `processor`, `telegram-bot`
  - manual: `scraper`

## Budget Envelope (Azure Only)

Price snapshot date: 2026-03-12 (Azure Retail Prices API).

- VM `B1ms` in `israelcentral`: `$0.024/hour` (~`$17.52/month`)
- Disk `E4 LRS`: `$2.88/month`
- Base subtotal: ~`$20.40/month`
- Typical headroom (backup storage + moderate egress): `$3` to `$6`
- Expected Azure total: ~`$20` to `$26` monthly

Important:
- OpenAI usage cost is separate and can exceed infra cost if usage grows.

## Phase Plan

## Phase 1: Repository Deployment Assets

1. Add `deploy/docker-compose.prod.yml`.
- Remove Redis from prod stack (not required by current runtime code).
- Keep scraper in a manual profile (not auto-start).
- Add restart policies for always-on services.
- Mount persistent host path for `/app/data`.

2. Add reverse-proxy config.
- File: `deploy/Caddyfile` (or `deploy/nginx.conf`).
- Route `/api` to API container and all other paths to frontend.

3. Add deploy scripts.
- `deploy/scripts/deploy.sh`: build, recreate, and health checks.
- `deploy/scripts/rollback.sh`: redeploy previous known-good revision.
- `deploy/scripts/run_scraper_manual.sh`: run scraper one-shot when needed.

## Phase 2: Production Configuration Hardening

1. Create VM-only env file (`.env.prod`, not committed).
- Required:
  - `ENVIRONMENT=production`
  - `DASHBOARD_PASSWORD`
  - `JWT_SECRET`
  - `OPENAI_API_KEY`
  - `TELEGRAM_BOT_TOKEN`
  - `TELEGRAM_CHAT_ID`
  - `API_BASE_URL`
  - `FRONTEND_BASE_URL`
  - `CORS_ORIGINS`
  - `APP_VERSION` (injected by CI)

2. Align frontend/API URLs for private ingress.
- Frontend API base URL uses `/api` behind proxy.
- `CORS_ORIGINS` includes only the Tailscale HTTPS origin.

3. Lock secrets and runtime permissions.
- Env file permissions `600`.
- Avoid exposing container ports publicly.
- Keep production docs/openapi disabled (already supported).

## Phase 3: Azure Provisioning

1. Provision VM.
- Ubuntu 22.04 LTS
- `Standard_B1ms`
- Standard SSD `E4`

2. Install software.
- Docker + Compose plugin
- Tailscale
- GitHub self-hosted runner

3. Boot-time resilience.
- systemd unit for compose stack.
- systemd unit for Tailscale serve.
- auto-start after reboot.

## Phase 4: Private Access with Tailscale

1. Join VM to tailnet using auth key.
2. Enable MagicDNS for stable naming.
3. Publish app privately with Tailscale serve HTTPS.
4. Validate:
- tailnet device: access works.
- non-tailnet/public internet: access denied.

## Phase 5: CI/CD on Push to main

1. Add workflow file `.github/workflows/deploy-prod.yml`.
2. Trigger on `push` to `main`.
3. Run on self-hosted runner on the VM.
4. Steps:
- checkout code
- set `APP_VERSION` from commit SHA
- run compose deploy (`up -d --build`)
- run smoke checks:
  - API `/health`
  - frontend root response
  - telegram-bot process healthy
- clean old images safely

5. Add rollback mechanism.
- Keep last successful revision tag/sha.
- One-command rollback script redeploys that revision.

## Phase 6: Backup, Restore, and Ops Guardrails

1. Nightly SQLite backups.
- Backup `/app/data/hfi.db`
- compress and upload to Blob Storage
- retain 14 to 30 days

2. Restore validation.
- monthly restore drill to temp DB file
- verify API can start and read data

3. Operational limits.
- Docker log rotation
- disk threshold alerts
- memory monitoring on VM
- if repeated OOM, upgrade VM to `B2s`

## Important Interface and Contract Changes

1. API response enhancement:
- add `build_version` field in root/health responses from `APP_VERSION`.

2. Environment contract additions:
- production requires `APP_VERSION` in deployment pipeline.
- production CORS restricted to private Tailscale origin.

3. Deployment contract:
- `deploy/docker-compose.prod.yml` becomes canonical production entrypoint.

## Test and Acceptance Scenarios

1. Deployment trigger:
- push commit to `main`
- pipeline deploys automatically
- app reports new build version

2. Private ingress:
- app opens from approved tailnet device
- public internet cannot access app

3. Authentication and startup checks:
- valid login works
- invalid password returns 401
- missing required production env causes fail-fast startup

4. Runtime health:
- frontend and API stable for 24h
- processor loop stable for 24h
- telegram bot handles commands and schedule

5. Data safety:
- latest backup exists in Blob
- restore test succeeds

6. Reboot behavior:
- VM reboot restores all always-on services automatically

## Assumptions and Defaults

- Region fixed to `israelcentral`.
- Private access fixed to Tailscale only.
- Telegram bot always-on from day one.
- Deployment model fixed to self-hosted runner.
- Scraper runs manually in v1.
- Single-instance deployment (no HA/failover initially).
- Budget scope excludes OpenAI API spend.

## Risks and Early Mitigations

1. Memory pressure on `B1ms`.
- Mitigation: scraper manual mode, conservative service limits, upgrade path to `B2s`.

2. Single-point-of-failure architecture.
- Mitigation: fast restore scripts + nightly backups + scripted redeploy.

3. Secret misconfiguration in production.
- Mitigation: fail-fast startup and pre-deploy env validation in CI.

## Future Upgrade Path (When Needed)

1. Enable scheduled scraper runs (hourly) once stability is confirmed.
2. Move from SQLite to managed Postgres for higher reliability.
3. Consider Azure Container Apps or AKS only after budget and scale increase.

## References

- Azure Retail Prices API: <https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices>
- Azure B-series VMs: <https://learn.microsoft.com/en-us/azure/virtual-machines/sizes/general-purpose/bv1-series>
- GitHub Actions self-hosted runners: <https://docs.github.com/en/actions/hosting-your-own-runners>
- Tailscale Serve: <https://tailscale.com/kb/1312/serve>
