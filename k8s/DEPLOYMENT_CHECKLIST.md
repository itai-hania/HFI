# HFI K3s Deployment Checklist

Quick reference checklist for deploying HFI to K3s. Follow this step-by-step guide for a successful deployment.

---

## Pre-Deployment Checklist

### System Requirements
- [ ] Linux server with at least 4GB RAM and 2 CPU cores
- [ ] 20GB+ disk space available
- [ ] Root/sudo access to the server
- [ ] Internet connectivity

### Software Prerequisites
- [ ] Docker installed and running
  ```bash
  docker --version  # Should show Docker version
  ```
- [ ] K3s installed
  ```bash
  curl -sfL https://get.k3s.io | sh -
  kubectl get nodes  # Should show node in Ready state
  ```
- [ ] kubectl configured
  ```bash
  export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
  # Or: mkdir -p ~/.kube && sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
  ```

### Configuration Files
- [ ] Secrets configured in `k8s/secrets.yaml`
  - [ ] X_USERNAME filled in (replace `<REPLACE_ME>`)
  - [ ] X_PASSWORD filled in (replace `<REPLACE_ME>`)
  - [ ] OPENAI_API_KEY filled in (replace `<REPLACE_ME>`)
  - [ ] No `<REPLACE_ME>` placeholders remain

- [ ] ConfigMap reviewed in `k8s/configmap.yaml`
  - [ ] Glossary terms appropriate for your use case
  - [ ] Style examples reflect your desired tone

### Validation
- [ ] Run pre-deployment validation script:
  ```bash
  cd /Users/itayy16/CursorProjects/HFI
  ./k8s/validate-deployment.sh
  ```
- [ ] All critical checks passed (0 failures)
- [ ] Review and address any warnings

---

## Deployment Checklist

### Option A: Automated Deployment (Recommended)

- [ ] Navigate to project root
  ```bash
  cd /Users/itayy16/CursorProjects/HFI
  ```

- [ ] Run deployment script
  ```bash
  ./k8s/deploy.sh
  # Or with Redis: ./k8s/deploy.sh --with-redis
  ```

- [ ] Wait for deployment to complete (typically 5-10 minutes)

- [ ] Review deployment output for any errors

### Option B: Manual Deployment (Advanced)

#### Step 1: Build Docker Images
- [ ] Build scraper image
  ```bash
  docker build -t hfi-scraper:latest -f src/scraper/Dockerfile .
  ```
- [ ] Build processor image
  ```bash
  docker build -t hfi-processor:latest -f src/processor/Dockerfile .
  ```
- [ ] Build dashboard image
  ```bash
  docker build -t hfi-dashboard:latest -f src/dashboard/Dockerfile .
  ```
- [ ] Verify images built successfully
  ```bash
  docker images | grep hfi
  ```

#### Step 2: Import Images to K3s
- [ ] Save images to tar files
  ```bash
  docker save hfi-scraper:latest -o /tmp/hfi-scraper.tar
  docker save hfi-processor:latest -o /tmp/hfi-processor.tar
  docker save hfi-dashboard:latest -o /tmp/hfi-dashboard.tar
  ```
- [ ] Import to K3s containerd
  ```bash
  sudo k3s ctr images import /tmp/hfi-scraper.tar
  sudo k3s ctr images import /tmp/hfi-processor.tar
  sudo k3s ctr images import /tmp/hfi-dashboard.tar
  ```
- [ ] Verify import
  ```bash
  sudo k3s ctr images ls | grep hfi
  ```
- [ ] Clean up tar files
  ```bash
  rm /tmp/hfi-*.tar
  ```

#### Step 3: Apply Kubernetes Manifests
- [ ] Create namespace
  ```bash
  kubectl apply -f k8s/namespace.yaml
  ```
- [ ] Create secrets
  ```bash
  kubectl apply -f k8s/secrets.yaml
  ```
- [ ] Create ConfigMap
  ```bash
  kubectl apply -f k8s/configmap.yaml
  ```
- [ ] Create PVC
  ```bash
  kubectl apply -f k8s/pvc.yaml
  ```
- [ ] Deploy processor
  ```bash
  kubectl apply -f k8s/deployment-processor.yaml
  ```
- [ ] Deploy dashboard
  ```bash
  kubectl apply -f k8s/deployment-dashboard.yaml
  ```
- [ ] Deploy scraper CronJob
  ```bash
  kubectl apply -f k8s/cronjob-scraper.yaml
  ```
- [ ] (Optional) Deploy Redis
  ```bash
  kubectl apply -f k8s/deployment-redis.yaml
  ```

---

## Post-Deployment Verification Checklist

### Automated Verification
- [ ] Run verification script
  ```bash
  ./k8s/verify-deployment.sh
  ```
- [ ] All critical checks passed
- [ ] Review and address any warnings

### Manual Verification

#### Namespace & Resources
- [ ] Namespace exists and active
  ```bash
  kubectl get namespace hfi-system
  ```
- [ ] Secrets created
  ```bash
  kubectl get secrets -n hfi-system
  ```
- [ ] ConfigMap created
  ```bash
  kubectl get configmap -n hfi-system
  ```

#### Storage
- [ ] PVC bound successfully
  ```bash
  kubectl get pvc -n hfi-system
  # Status should be: Bound
  ```

#### Deployments & Pods
- [ ] Processor deployment ready
  ```bash
  kubectl get deployment hfi-processor -n hfi-system
  # READY should show: 1/1
  ```
- [ ] Dashboard deployment ready
  ```bash
  kubectl get deployment hfi-dashboard -n hfi-system
  # READY should show: 1/1
  ```
- [ ] All pods running
  ```bash
  kubectl get pods -n hfi-system
  # All pods should show: Running
  ```

#### Services
- [ ] Dashboard service exposed
  ```bash
  kubectl get svc hfi-dashboard -n hfi-system
  # TYPE should show: NodePort
  ```
- [ ] NodePort noted (should be 30080)

#### CronJob
- [ ] Scraper CronJob created
  ```bash
  kubectl get cronjobs -n hfi-system
  # Should show: hfi-scraper with schedule
  ```

#### Health Checks
- [ ] Processor health check passes
  ```bash
  kubectl exec -n hfi-system deployment/hfi-processor -- python -c "import sys; sys.exit(0)"
  ```
- [ ] Dashboard health check passes
  ```bash
  kubectl exec -n hfi-system deployment/hfi-dashboard -- curl -f http://localhost:8501/_stcore/health
  ```

#### Logs
- [ ] No critical errors in processor logs
  ```bash
  kubectl logs -n hfi-system deployment/hfi-processor --tail=50
  ```
- [ ] No critical errors in dashboard logs
  ```bash
  kubectl logs -n hfi-system deployment/hfi-dashboard --tail=50
  ```

---

## Access & First Run Checklist

### Dashboard Access
- [ ] Identify access URL
  ```bash
  echo "http://localhost:30080"
  # Or get node IP: kubectl get nodes -o wide
  ```
- [ ] Open dashboard in browser
- [ ] Dashboard loads successfully
- [ ] No errors displayed on dashboard

### First Scraper Run
- [ ] Trigger scraper manually (don't wait for CronJob)
  ```bash
  kubectl create job -n hfi-system --from=cronjob/hfi-scraper manual-scrape-$(date +%s)
  ```
- [ ] Watch scraper job logs
  ```bash
  kubectl get jobs -n hfi-system -w
  # Wait for job to complete
  ```
- [ ] Check scraper logs for success
  ```bash
  SCRAPER_POD=$(kubectl get pods -n hfi-system -l app=hfi-scraper --sort-by=.metadata.creationTimestamp -o jsonpath='{.items[-1].metadata.name}')
  kubectl logs -n hfi-system $SCRAPER_POD
  ```
- [ ] Verify tweets scraped (check dashboard or database)

### Processor Verification
- [ ] Check processor is processing tweets
  ```bash
  kubectl logs -f -n hfi-system deployment/hfi-processor
  # Should see: "Checking for pending tweets..." messages
  ```
- [ ] Verify tweets are being translated (check dashboard)

---

## Operational Checklist

### Daily Operations
- [ ] Monitor dashboard for new content
- [ ] Review and approve translated tweets
- [ ] Check for any pod restarts
  ```bash
  kubectl get pods -n hfi-system
  # RESTARTS column should be 0 or low
  ```

### Weekly Maintenance
- [ ] Review pod logs for errors
  ```bash
  kubectl logs -n hfi-system deployment/hfi-processor --tail=100 | grep -i error
  kubectl logs -n hfi-system deployment/hfi-dashboard --tail=100 | grep -i error
  ```
- [ ] Check resource usage
  ```bash
  kubectl top pods -n hfi-system
  kubectl top nodes
  ```
- [ ] Backup database
  ```bash
  POD=$(kubectl get pod -n hfi-system -l app=hfi-processor -o jsonpath='{.items[0].metadata.name}')
  kubectl cp -n hfi-system $POD:/app/data/hfi.db ./backups/hfi-$(date +%Y%m%d).db
  ```

### Monthly Maintenance
- [ ] Update Docker images with latest code
  ```bash
  docker build -t hfi-processor:latest -f src/processor/Dockerfile .
  docker save hfi-processor:latest -o /tmp/hfi-processor.tar
  sudo k3s ctr images import /tmp/hfi-processor.tar
  kubectl rollout restart -n hfi-system deployment/hfi-processor
  ```
- [ ] Review and optimize scraper schedule if needed
  ```bash
  kubectl edit cronjob hfi-scraper -n hfi-system
  ```
- [ ] Clean up old scraper jobs
  ```bash
  kubectl delete job -n hfi-system $(kubectl get jobs -n hfi-system -l app=hfi-scraper --sort-by=.metadata.creationTimestamp -o jsonpath='{.items[:-3].metadata.name}')
  ```

---

## Troubleshooting Checklist

### Pods Not Starting
- [ ] Check pod status
  ```bash
  kubectl get pods -n hfi-system
  ```
- [ ] Describe problematic pod
  ```bash
  kubectl describe pod <pod-name> -n hfi-system
  ```
- [ ] Check events
  ```bash
  kubectl get events -n hfi-system --sort-by='.lastTimestamp'
  ```

### Image Issues
- [ ] Verify images in K3s
  ```bash
  sudo k3s ctr images ls | grep hfi
  ```
- [ ] Re-import if missing
  ```bash
  docker save hfi-processor:latest -o /tmp/hfi-processor.tar
  sudo k3s ctr images import /tmp/hfi-processor.tar
  ```

### Dashboard Not Accessible
- [ ] Verify pod is running
  ```bash
  kubectl get pods -n hfi-system -l app=hfi-dashboard
  ```
- [ ] Check service
  ```bash
  kubectl get svc hfi-dashboard -n hfi-system
  ```
- [ ] Try port-forward as workaround
  ```bash
  kubectl port-forward -n hfi-system service/hfi-dashboard 8501:8501
  # Then access: http://localhost:8501
  ```

### Database Issues
- [ ] Check PVC binding
  ```bash
  kubectl get pvc -n hfi-system
  ```
- [ ] Verify processor can access database
  ```bash
  POD=$(kubectl get pod -n hfi-system -l app=hfi-processor -o jsonpath='{.items[0].metadata.name}')
  kubectl exec -n hfi-system $POD -- ls -lh /app/data/
  ```

---

## Rollback Checklist

### Emergency Rollback
- [ ] Stop accepting new scrapes (suspend CronJob)
  ```bash
  kubectl patch cronjob hfi-scraper -n hfi-system -p '{"spec":{"suspend":true}}'
  ```
- [ ] Restore database from backup
  ```bash
  POD=$(kubectl get pod -n hfi-system -l app=hfi-processor -o jsonpath='{.items[0].metadata.name}')
  kubectl cp ./backups/hfi-20260119.db -n hfi-system $POD:/app/data/hfi.db
  ```
- [ ] Restart deployments
  ```bash
  kubectl rollout restart -n hfi-system deployment/hfi-processor
  kubectl rollout restart -n hfi-system deployment/hfi-dashboard
  ```
- [ ] Resume CronJob when ready
  ```bash
  kubectl patch cronjob hfi-scraper -n hfi-system -p '{"spec":{"suspend":false}}'
  ```

---

## Uninstall Checklist

### Complete Removal
- [ ] Delete namespace (removes all resources)
  ```bash
  kubectl delete namespace hfi-system
  ```
- [ ] Verify deletion
  ```bash
  kubectl get all -n hfi-system
  # Should show: No resources found
  ```
- [ ] Remove Docker images
  ```bash
  docker rmi hfi-scraper:latest hfi-processor:latest hfi-dashboard:latest
  ```
- [ ] Remove K3s images
  ```bash
  sudo k3s ctr images rm docker.io/library/hfi-scraper:latest
  sudo k3s ctr images rm docker.io/library/hfi-processor:latest
  sudo k3s ctr images rm docker.io/library/hfi-dashboard:latest
  ```
- [ ] Clean up local storage (if desired)
  ```bash
  # Warning: This deletes all data
  sudo rm -rf /var/lib/rancher/k3s/storage/pvc-*
  ```

---

## Quick Reference Commands

```bash
# View all resources
kubectl get all -n hfi-system

# Check pod logs
kubectl logs -f -n hfi-system deployment/hfi-processor
kubectl logs -f -n hfi-system deployment/hfi-dashboard

# Execute shell in pod
kubectl exec -it -n hfi-system deployment/hfi-processor -- /bin/bash

# Restart deployment
kubectl rollout restart -n hfi-system deployment/hfi-processor

# Manual scraper trigger
kubectl create job -n hfi-system --from=cronjob/hfi-scraper manual-$(date +%s)

# Port-forward dashboard
kubectl port-forward -n hfi-system service/hfi-dashboard 8501:8501

# Backup database
POD=$(kubectl get pod -n hfi-system -l app=hfi-processor -o jsonpath='{.items[0].metadata.name}')
kubectl cp -n hfi-system $POD:/app/data/hfi.db ./backup-$(date +%Y%m%d).db

# View events
kubectl get events -n hfi-system --sort-by='.lastTimestamp'

# Check resource usage
kubectl top pods -n hfi-system
kubectl top nodes
```

---

## Documentation References

- **Full Deployment Guide:** `k8s/README.md`
- **Validation Script:** `k8s/validate-deployment.sh`
- **Verification Script:** `k8s/verify-deployment.sh`
- **Deployment Summary:** `/K8S_DEPLOYMENT_SUMMARY.md`
- **Implementation Plan:** `/IMPLEMENTATION_PLAN.md`

---

**Last Updated:** 2026-01-19
**Version:** 1.0
**Status:** Production-Ready ✅
