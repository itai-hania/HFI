# Hebrew FinTech Informant (HFI) - K3s Deployment Guide

This guide provides complete instructions for deploying the HFI application on K3s, a lightweight Kubernetes distribution optimized for edge computing and resource-constrained environments.

## Table of Contents

- [System Requirements](#system-requirements)
- [Architecture Overview](#architecture-overview)
- [Installation Steps](#installation-steps)
- [Local Development with Docker Compose](#local-development-with-docker-compose)
- [K3s Production Deployment](#k3s-production-deployment)
- [Operations and Maintenance](#operations-and-maintenance)
- [Troubleshooting](#troubleshooting)
- [Resource Optimization](#resource-optimization)

---

## System Requirements

### Minimum Hardware Requirements

- **CPU**: 2 cores (x86_64 or ARM64)
- **RAM**: 4GB (breakdown below)
- **Storage**: 20GB available disk space
- **OS**: Linux (Ubuntu 20.04+, Debian 10+, CentOS 7+, or compatible)

### Resource Allocation

```
K3s Control Plane:    ~500MB RAM
Scraper (CronJob):    ~800MB RAM (only during execution)
Processor:            ~300MB RAM (continuous)
Dashboard:            ~200MB RAM (continuous)
System Overhead:      ~500MB RAM
Total:                ~2.3GB RAM (continuous) + 800MB (periodic)
```

### Software Prerequisites

- **Docker** (for building images)
- **kubectl** (Kubernetes CLI)
- **curl** (for K3s installation)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        K3s Cluster                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   CronJob    │  │  Deployment  │  │  Deployment  │    │
│  │   Scraper    │  │  Processor   │  │  Dashboard   │    │
│  │ (Every 30m)  │  │  (1 replica) │  │  (1 replica) │    │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘    │
│         │                  │                  │            │
│         └──────────────────┼──────────────────┘            │
│                            │                               │
│                   ┌────────▼────────┐                      │
│                   │ PersistentVolume│                      │
│                   │   SQLite + Media│                      │
│                   │   (local-path)  │                      │
│                   └─────────────────┘                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ NodePort 30080
                            ▼
                      User Browser
```

### Components

1. **Scraper (CronJob)**: Runs every 30 minutes to fetch trending topics and tweets from X (Twitter)
2. **Processor (Deployment)**: Continuously processes pending tweets (translation + media download)
3. **Dashboard (Deployment)**: Streamlit web interface for content review and approval
4. **Shared Storage (PVC)**: SQLite database and media files accessible by all components

---

## Installation Steps

### 1. Install K3s

K3s installation is a single command that sets up a complete Kubernetes cluster:

```bash
# Install K3s with default settings
curl -sfL https://get.k3s.io | sh -

# Verify installation
sudo systemctl status k3s

# Check node status
sudo k3s kubectl get nodes
```

### 2. Configure kubectl

Set up kubectl to communicate with your K3s cluster:

```bash
# Option A: Copy kubeconfig to default location
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown $USER:$USER ~/.kube/config
chmod 600 ~/.kube/config

# Option B: Set KUBECONFIG environment variable
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

# Verify kubectl access
kubectl get nodes
kubectl version
```

### 3. Verify K3s Components

Ensure all K3s system components are running:

```bash
# Check system pods
kubectl get pods -n kube-system

# Verify local-path storage provisioner (required for PVC)
kubectl get storageclass
```

Expected output:
```
NAME                   PROVISIONER             RECLAIMPOLICY   VOLUMEBINDINGMODE
local-path (default)   rancher.io/local-path   Delete          WaitForFirstConsumer
```

---

## Local Development with Docker Compose

Before deploying to K3s, test your application locally with Docker Compose.

### 1. Build Docker Images

```bash
# Navigate to project root
cd /Users/itayy16/CursorProjects/HFI

# Build all service images
docker-compose build

# Verify images
docker images | grep hfi
```

### 2. Start Services

```bash
# Start all services in detached mode
docker-compose up -d

# View logs
docker-compose logs -f

# Check service health
docker-compose ps
```

### 3. Run the Scraper Manually

The scraper doesn't run automatically in Docker Compose to save resources:

```bash
# Execute scraper
docker-compose exec scraper python main.py

# View scraper logs
docker-compose logs scraper
```

### 4. Access the Dashboard

Open your browser to: **http://localhost:8501**

### 5. Stop Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (caution: deletes data)
docker-compose down -v
```

---

## K3s Production Deployment

### Step 1: Build and Tag Docker Images

```bash
# Navigate to project root
cd /Users/itayy16/CursorProjects/HFI

# Build images with specific tags
docker build -t hfi-scraper:latest -f src/scraper/Dockerfile src/scraper
docker build -t hfi-processor:latest -f src/processor/Dockerfile src/processor
docker build -t hfi-dashboard:latest -f src/dashboard/Dockerfile src/dashboard

# Verify images
docker images | grep hfi
```

### Step 2: Import Images to K3s

K3s uses containerd (not Docker) as its container runtime. You must import Docker images:

```bash
# Save Docker images to tar archives
docker save hfi-scraper:latest -o /tmp/hfi-scraper.tar
docker save hfi-processor:latest -o /tmp/hfi-processor.tar
docker save hfi-dashboard:latest -o /tmp/hfi-dashboard.tar

# Import to K3s containerd
sudo k3s ctr images import /tmp/hfi-scraper.tar
sudo k3s ctr images import /tmp/hfi-processor.tar
sudo k3s ctr images import /tmp/hfi-dashboard.tar

# Verify imported images
sudo k3s ctr images ls | grep hfi

# Clean up tar files
rm /tmp/hfi-*.tar
```

### Step 3: Configure Secrets

Create your secrets file from the template:

```bash
# Copy template
cp k8s/secrets.yaml.template k8s/secrets.yaml

# Edit with your credentials
nano k8s/secrets.yaml
# OR
vim k8s/secrets.yaml
```

Replace placeholder values:
- `X_USERNAME`: Your X (Twitter) burner account email
- `X_PASSWORD`: Your X (Twitter) password
- `OPENAI_API_KEY`: Your OpenAI API key

**IMPORTANT**: Add `secrets.yaml` to `.gitignore` to avoid committing credentials.

### Step 4: Update ConfigMap (Optional)

Edit the ConfigMap to add your style guide examples:

```bash
nano k8s/configmap.yaml
```

Replace the `[PLACEHOLDER]` section in `style.txt` with 5-10 examples of your best Hebrew tweets.

### Step 5: Deploy to K3s

Apply all manifests in the correct order:

```bash
# 1. Create namespace
kubectl apply -f k8s/namespace.yaml

# 2. Create secrets (must exist before deployments)
kubectl apply -f k8s/secrets.yaml

# 3. Create ConfigMap
kubectl apply -f k8s/configmap.yaml

# 4. Create PersistentVolumeClaim
kubectl apply -f k8s/pvc.yaml

# 5. Deploy processor
kubectl apply -f k8s/deployment-processor.yaml

# 6. Deploy dashboard
kubectl apply -f k8s/deployment-dashboard.yaml

# 7. Deploy scraper CronJob
kubectl apply -f k8s/cronjob-scraper.yaml

# OR apply all at once (order doesn't matter with K8s reconciliation)
kubectl apply -f k8s/
```

### Step 6: Verify Deployment

```bash
# Check all resources in hfi-system namespace
kubectl get all -n hfi-system

# Check pod status (wait for Running state)
kubectl get pods -n hfi-system

# View pod logs
kubectl logs -n hfi-system deployment/hfi-processor
kubectl logs -n hfi-system deployment/hfi-dashboard

# Check CronJob schedule
kubectl get cronjobs -n hfi-system

# View PVC status (should be Bound)
kubectl get pvc -n hfi-system
```

Expected output:
```
NAME                             READY   STATUS    RESTARTS   AGE
pod/hfi-processor-xxx            1/1     Running   0          2m
pod/hfi-dashboard-xxx            1/1     Running   0          2m

NAME                    TYPE       CLUSTER-IP      EXTERNAL-IP   PORT(S)          AGE
service/hfi-dashboard   NodePort   10.43.xxx.xxx   <none>        8501:30080/TCP   2m

NAME                            READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/hfi-processor   1/1     1            1           2m
deployment.apps/hfi-dashboard   1/1     1            1           2m

NAME                                SCHEDULE      SUSPEND   ACTIVE   LAST SCHEDULE   AGE
cronjob.batch/hfi-scraper           */30 * * * *  False     0        <none>          2m
```

### Step 7: Access the Dashboard

Find your node IP address:

```bash
# Get node IP
kubectl get nodes -o wide

# OR if running locally
echo "http://localhost:30080"
```

Open in browser: **http://<node-ip>:30080**

---

## Operations and Maintenance

### Viewing Logs

```bash
# Real-time logs for processor
kubectl logs -f -n hfi-system deployment/hfi-processor

# Real-time logs for dashboard
kubectl logs -f -n hfi-system deployment/hfi-dashboard

# View last CronJob execution
kubectl logs -n hfi-system job/hfi-scraper-<timestamp>

# View all CronJob executions
kubectl get jobs -n hfi-system
```

### Manual Scraper Execution

To trigger the scraper immediately (without waiting for CronJob):

```bash
# Create a manual job from the CronJob template
kubectl create job -n hfi-system --from=cronjob/hfi-scraper manual-scrape-$(date +%s)

# Watch job execution
kubectl get jobs -n hfi-system -w

# View job logs
kubectl logs -n hfi-system job/manual-scrape-<timestamp>
```

### Updating Application Code

When you make changes to the application code:

```bash
# 1. Rebuild Docker image
docker build -t hfi-processor:latest -f src/processor/Dockerfile src/processor

# 2. Import to K3s
docker save hfi-processor:latest -o /tmp/hfi-processor.tar
sudo k3s ctr images import /tmp/hfi-processor.tar
rm /tmp/hfi-processor.tar

# 3. Restart deployment to use new image
kubectl rollout restart -n hfi-system deployment/hfi-processor

# 4. Watch rollout status
kubectl rollout status -n hfi-system deployment/hfi-processor
```

### Scaling Services

```bash
# Scale dashboard to 2 replicas (for high availability)
kubectl scale -n hfi-system deployment/hfi-dashboard --replicas=2

# Note: Processor should stay at 1 replica (SQLite limitation)

# Verify scaling
kubectl get pods -n hfi-system
```

### Updating Secrets or ConfigMap

```bash
# Edit secrets
kubectl edit secret -n hfi-system hfi-secrets

# Edit ConfigMap
kubectl edit configmap -n hfi-system hfi-config

# Restart pods to pick up changes
kubectl rollout restart -n hfi-system deployment/hfi-processor
kubectl rollout restart -n hfi-system deployment/hfi-dashboard
```

### Backup and Restore

#### Backup SQLite Database

```bash
# Find the pod mounting the PVC
POD=$(kubectl get pod -n hfi-system -l app=hfi-processor -o jsonpath='{.items[0].metadata.name}')

# Copy database from pod to local machine
kubectl cp -n hfi-system $POD:/app/data/hfi.db ./backup-$(date +%Y%m%d).db

# Verify backup
ls -lh backup-*.db
```

#### Restore Database

```bash
# Copy database from local machine to pod
kubectl cp -n hfi-system ./backup-20260117.db $POD:/app/data/hfi.db

# Restart processor to use restored database
kubectl rollout restart -n hfi-system deployment/hfi-processor
```

### Monitoring Resource Usage

```bash
# View resource usage by pod
kubectl top pods -n hfi-system

# View resource usage by node
kubectl top nodes

# Describe pod for detailed resource info
kubectl describe pod -n hfi-system <pod-name>
```

---

## Troubleshooting

### Pods Not Starting

**Symptom**: Pods stuck in `Pending`, `ImagePullBackOff`, or `CrashLoopBackOff` state.

**Diagnosis**:
```bash
# Check pod status
kubectl get pods -n hfi-system

# Describe pod for events
kubectl describe pod -n hfi-system <pod-name>

# View pod logs
kubectl logs -n hfi-system <pod-name>
```

**Common Causes**:

1. **ImagePullBackOff**: Image not imported to K3s
   ```bash
   # Re-import image
   docker save hfi-processor:latest -o /tmp/hfi-processor.tar
   sudo k3s ctr images import /tmp/hfi-processor.tar
   ```

2. **CrashLoopBackOff**: Application error
   ```bash
   # Check logs for error messages
   kubectl logs -n hfi-system <pod-name>
   ```

3. **Pending with PVC error**: Storage issue
   ```bash
   # Check PVC status
   kubectl get pvc -n hfi-system

   # Check storage class
   kubectl get storageclass
   ```

### Database Locked Errors

**Symptom**: `database is locked` errors in processor or scraper logs.

**Cause**: Multiple processes trying to write to SQLite simultaneously.

**Solution**:
```bash
# Ensure only 1 processor replica
kubectl scale -n hfi-system deployment/hfi-processor --replicas=1

# Check for multiple scraper jobs running
kubectl get jobs -n hfi-system

# Delete old jobs if needed
kubectl delete job -n hfi-system <job-name>
```

### Dashboard Not Accessible

**Symptom**: Cannot access dashboard at http://localhost:30080

**Diagnosis**:
```bash
# Check service
kubectl get svc -n hfi-system hfi-dashboard

# Check dashboard pod logs
kubectl logs -n hfi-system deployment/hfi-dashboard

# Test from within cluster
kubectl run -n hfi-system test-curl --image=curlimages/curl --rm -it -- curl http://hfi-dashboard:8501
```

**Solution**:
```bash
# Port-forward as temporary workaround
kubectl port-forward -n hfi-system service/hfi-dashboard 8501:8501

# Access at http://localhost:8501
```

### Scraper CronJob Not Running

**Symptom**: Scraper CronJob not executing at scheduled times.

**Diagnosis**:
```bash
# Check CronJob status
kubectl get cronjobs -n hfi-system

# View CronJob details
kubectl describe cronjob -n hfi-system hfi-scraper

# Check for jobs
kubectl get jobs -n hfi-system
```

**Solution**:
```bash
# Check if CronJob is suspended
kubectl patch cronjob -n hfi-system hfi-scraper -p '{"spec":{"suspend":false}}'

# Manually trigger to test
kubectl create job -n hfi-system --from=cronjob/hfi-scraper test-scrape
```

### High Memory Usage

**Symptom**: Pods being OOMKilled (Out Of Memory).

**Diagnosis**:
```bash
# Check resource usage
kubectl top pods -n hfi-system

# Check pod events
kubectl get events -n hfi-system --sort-by='.lastTimestamp'
```

**Solution**:
```bash
# Increase memory limits in deployment
kubectl edit deployment -n hfi-system hfi-processor

# Change:
# limits:
#   memory: "512Mi"
# To:
# limits:
#   memory: "1Gi"

# Apply changes
kubectl rollout restart -n hfi-system deployment/hfi-processor
```

---

## Resource Optimization

### Reducing Memory Footprint

1. **Disable Redis** (if not used):
   ```yaml
   # In docker-compose.yml, comment out redis service
   # In deployments, remove REDIS_URL environment variable
   ```

2. **Reduce Scraper Frequency**:
   ```yaml
   # In k8s/cronjob-scraper.yaml, change schedule
   schedule: "0 */2 * * *"  # Every 2 hours instead of 30 minutes
   ```

3. **Limit Concurrent Processing**:
   ```python
   # In processor code, add sleep between batches
   # Process fewer tweets per batch
   ```

### Optimizing for Low-Resource VPS

For VPS with <4GB RAM:

```yaml
# Reduce resource requests in all deployments
resources:
  requests:
    memory: "128Mi"
    cpu: "100m"
  limits:
    memory: "256Mi"
    cpu: "500m"
```

### Monitoring and Alerts

Set up basic monitoring:

```bash
# Install metrics-server (if not present)
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# View resource usage
kubectl top nodes
kubectl top pods -n hfi-system
```

---

## Uninstalling

### Remove HFI Application

```bash
# Delete all resources
kubectl delete namespace hfi-system

# Verify deletion
kubectl get all -n hfi-system
```

### Remove K3s Completely

```bash
# Uninstall K3s
/usr/local/bin/k3s-uninstall.sh

# Verify removal
sudo systemctl status k3s
```

---

## Additional Resources

- **K3s Documentation**: https://docs.k3s.io/
- **Kubernetes Documentation**: https://kubernetes.io/docs/
- **Streamlit Documentation**: https://docs.streamlit.io/
- **Playwright Documentation**: https://playwright.dev/python/

---

## Support and Contribution

For issues, questions, or contributions:
1. Check existing logs and troubleshooting steps
2. Review Kubernetes events: `kubectl get events -n hfi-system`
3. Consult K3s and component documentation

---

**Last Updated**: 2026-01-17
**Version**: 1.0.0
