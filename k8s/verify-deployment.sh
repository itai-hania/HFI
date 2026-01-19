#!/usr/bin/env bash
# ================================================================
# HFI Post-Deployment Verification Script
# ================================================================
# This script verifies that HFI was deployed successfully to K3s.
# It checks:
# - All pods are running
# - Services are accessible
# - PVCs are bound
# - Health checks pass
# - Inter-service connectivity
# - Dashboard accessibility
#
# Usage: ./k8s/verify-deployment.sh
# ================================================================

set -e  # Exit on error
set -u  # Exit on undefined variable

# ================================================================
# Configuration
# ================================================================

NAMESPACE="hfi-system"
TIMEOUT=120  # seconds to wait for pods to be ready

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Counters
PASSED=0
FAILED=0
WARNINGS=0

# ================================================================
# Helper Functions
# ================================================================

print_header() {
    echo -e "\n${BLUE}================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
    ((PASSED++))
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
    ((WARNINGS++))
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
    ((FAILED++))
}

print_info() {
    echo -e "${BLUE}→ $1${NC}"
}

# ================================================================
# Verification Checks
# ================================================================

check_namespace() {
    print_header "Checking Namespace"

    if kubectl get namespace "$NAMESPACE" &> /dev/null; then
        NAMESPACE_STATUS=$(kubectl get namespace "$NAMESPACE" -o jsonpath='{.status.phase}')
        if [ "$NAMESPACE_STATUS" = "Active" ]; then
            print_success "Namespace ${NAMESPACE} exists and is Active"
        else
            print_error "Namespace ${NAMESPACE} exists but status is: ${NAMESPACE_STATUS}"
        fi
    else
        print_error "Namespace ${NAMESPACE} not found"
    fi
}

check_secrets() {
    print_header "Checking Secrets"

    if kubectl get secret hfi-secrets -n "$NAMESPACE" &> /dev/null; then
        print_success "Secret hfi-secrets exists"

        # Check if secret has required keys
        SECRET_KEYS=$(kubectl get secret hfi-secrets -n "$NAMESPACE" -o jsonpath='{.data}' | grep -o '"[^"]*"' | tr -d '"' | sort)
        REQUIRED_KEYS=("DATABASE_URL" "OPENAI_API_KEY" "X_PASSWORD" "X_USERNAME")

        for key in "${REQUIRED_KEYS[@]}"; do
            if echo "$SECRET_KEYS" | grep -q "^${key}$"; then
                print_success "Secret key exists: ${key}"
            else
                print_error "Secret key missing: ${key}"
            fi
        done
    else
        print_error "Secret hfi-secrets not found"
    fi
}

check_configmap() {
    print_header "Checking ConfigMap"

    if kubectl get configmap hfi-config -n "$NAMESPACE" &> /dev/null; then
        print_success "ConfigMap hfi-config exists"

        # Check ConfigMap data keys
        if kubectl get configmap hfi-config -n "$NAMESPACE" -o jsonpath='{.data.glossary\.json}' | grep -q "Short Squeeze"; then
            print_success "ConfigMap contains glossary.json with data"
        else
            print_warning "ConfigMap glossary.json may be empty or invalid"
        fi

        if kubectl get configmap hfi-config -n "$NAMESPACE" -o jsonpath='{.data.style\.txt}' | grep -q "Example"; then
            print_success "ConfigMap contains style.txt with data"
        else
            print_warning "ConfigMap style.txt may be empty or invalid"
        fi
    else
        print_error "ConfigMap hfi-config not found"
    fi
}

check_pvcs() {
    print_header "Checking PersistentVolumeClaims"

    # Check hfi-data-pvc
    if kubectl get pvc hfi-data-pvc -n "$NAMESPACE" &> /dev/null; then
        PVC_STATUS=$(kubectl get pvc hfi-data-pvc -n "$NAMESPACE" -o jsonpath='{.status.phase}')
        PVC_SIZE=$(kubectl get pvc hfi-data-pvc -n "$NAMESPACE" -o jsonpath='{.status.capacity.storage}')

        if [ "$PVC_STATUS" = "Bound" ]; then
            print_success "PVC hfi-data-pvc is Bound (${PVC_SIZE})"
        else
            print_error "PVC hfi-data-pvc status: ${PVC_STATUS}"
        fi
    else
        print_error "PVC hfi-data-pvc not found"
    fi

    # Check Redis PVC if it exists
    if kubectl get pvc hfi-redis-pvc -n "$NAMESPACE" &> /dev/null; then
        REDIS_PVC_STATUS=$(kubectl get pvc hfi-redis-pvc -n "$NAMESPACE" -o jsonpath='{.status.phase}')
        if [ "$REDIS_PVC_STATUS" = "Bound" ]; then
            print_success "PVC hfi-redis-pvc is Bound (optional)"
        else
            print_warning "PVC hfi-redis-pvc status: ${REDIS_PVC_STATUS} (optional)"
        fi
    fi
}

check_deployments() {
    print_header "Checking Deployments"

    DEPLOYMENTS=("hfi-processor" "hfi-dashboard")

    for deployment in "${DEPLOYMENTS[@]}"; do
        if kubectl get deployment "$deployment" -n "$NAMESPACE" &> /dev/null; then
            DESIRED=$(kubectl get deployment "$deployment" -n "$NAMESPACE" -o jsonpath='{.spec.replicas}')
            READY=$(kubectl get deployment "$deployment" -n "$NAMESPACE" -o jsonpath='{.status.readyReplicas}')
            READY=${READY:-0}

            if [ "$DESIRED" -eq "$READY" ]; then
                print_success "Deployment ${deployment}: ${READY}/${DESIRED} replicas ready"
            else
                print_error "Deployment ${deployment}: ${READY}/${DESIRED} replicas ready"
            fi
        else
            print_error "Deployment ${deployment} not found"
        fi
    done

    # Check Redis deployment if it exists
    if kubectl get deployment hfi-redis -n "$NAMESPACE" &> /dev/null; then
        REDIS_DESIRED=$(kubectl get deployment hfi-redis -n "$NAMESPACE" -o jsonpath='{.spec.replicas}')
        REDIS_READY=$(kubectl get deployment hfi-redis -n "$NAMESPACE" -o jsonpath='{.status.readyReplicas}')
        REDIS_READY=${REDIS_READY:-0}

        if [ "$REDIS_DESIRED" -eq "$REDIS_READY" ]; then
            print_success "Deployment hfi-redis: ${REDIS_READY}/${REDIS_DESIRED} replicas ready (optional)"
        else
            print_warning "Deployment hfi-redis: ${REDIS_READY}/${REDIS_DESIRED} replicas ready (optional)"
        fi
    fi
}

check_pods() {
    print_header "Checking Pods"

    # Get all pods in namespace
    PODS=$(kubectl get pods -n "$NAMESPACE" --no-headers 2>/dev/null || echo "")

    if [ -z "$PODS" ]; then
        print_error "No pods found in namespace ${NAMESPACE}"
        return
    fi

    # Check each pod
    while IFS= read -r pod_line; do
        POD_NAME=$(echo "$pod_line" | awk '{print $1}')
        POD_STATUS=$(echo "$pod_line" | awk '{print $3}')
        POD_READY=$(echo "$pod_line" | awk '{print $2}')

        if [ "$POD_STATUS" = "Running" ]; then
            print_success "Pod ${POD_NAME}: ${POD_STATUS} (${POD_READY})"
        elif [ "$POD_STATUS" = "Completed" ]; then
            print_info "Pod ${POD_NAME}: ${POD_STATUS} (CronJob)"
        else
            print_error "Pod ${POD_NAME}: ${POD_STATUS} (${POD_READY})"
        fi
    done <<< "$PODS"
}

check_services() {
    print_header "Checking Services"

    # Check dashboard service
    if kubectl get service hfi-dashboard -n "$NAMESPACE" &> /dev/null; then
        SVC_TYPE=$(kubectl get service hfi-dashboard -n "$NAMESPACE" -o jsonpath='{.spec.type}')
        NODE_PORT=$(kubectl get service hfi-dashboard -n "$NAMESPACE" -o jsonpath='{.spec.ports[0].nodePort}')
        CLUSTER_IP=$(kubectl get service hfi-dashboard -n "$NAMESPACE" -o jsonpath='{.spec.clusterIP}')

        print_success "Service hfi-dashboard: ${SVC_TYPE} (ClusterIP: ${CLUSTER_IP}, NodePort: ${NODE_PORT})"
    else
        print_error "Service hfi-dashboard not found"
    fi

    # Check Redis service if it exists
    if kubectl get service hfi-redis -n "$NAMESPACE" &> /dev/null; then
        REDIS_SVC_TYPE=$(kubectl get service hfi-redis -n "$NAMESPACE" -o jsonpath='{.spec.type}')
        REDIS_CLUSTER_IP=$(kubectl get service hfi-redis -n "$NAMESPACE" -o jsonpath='{.spec.clusterIP}')
        print_success "Service hfi-redis: ${REDIS_SVC_TYPE} (ClusterIP: ${REDIS_CLUSTER_IP}) (optional)"
    fi
}

check_cronjob() {
    print_header "Checking CronJob"

    if kubectl get cronjob hfi-scraper -n "$NAMESPACE" &> /dev/null; then
        SCHEDULE=$(kubectl get cronjob hfi-scraper -n "$NAMESPACE" -o jsonpath='{.spec.schedule}')
        SUSPEND=$(kubectl get cronjob hfi-scraper -n "$NAMESPACE" -o jsonpath='{.spec.suspend}')
        LAST_SCHEDULE=$(kubectl get cronjob hfi-scraper -n "$NAMESPACE" -o jsonpath='{.status.lastScheduleTime}')

        print_success "CronJob hfi-scraper exists"
        print_info "  Schedule: ${SCHEDULE}"
        print_info "  Suspended: ${SUSPEND}"

        if [ -n "$LAST_SCHEDULE" ]; then
            print_info "  Last schedule: ${LAST_SCHEDULE}"
        else
            print_info "  Last schedule: Never (not triggered yet)"
        fi

        # Check for recent jobs
        RECENT_JOBS=$(kubectl get jobs -n "$NAMESPACE" -l app=hfi-scraper --sort-by=.metadata.creationTimestamp 2>/dev/null | tail -n +2 | wc -l)
        if [ "$RECENT_JOBS" -gt 0 ]; then
            print_success "Found ${RECENT_JOBS} scraper job(s)"
        else
            print_warning "No scraper jobs found yet (CronJob hasn't run)"
        fi
    else
        print_error "CronJob hfi-scraper not found"
    fi
}

check_health() {
    print_header "Checking Application Health"

    # Check processor health
    PROCESSOR_POD=$(kubectl get pod -n "$NAMESPACE" -l app=hfi-processor -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
    if [ -n "$PROCESSOR_POD" ]; then
        if kubectl exec -n "$NAMESPACE" "$PROCESSOR_POD" -- python -c "import sys; sys.exit(0)" &> /dev/null; then
            print_success "Processor health check: Python runtime OK"
        else
            print_error "Processor health check: Python runtime failed"
        fi
    else
        print_warning "Processor pod not found, skipping health check"
    fi

    # Check dashboard health (Streamlit health endpoint)
    DASHBOARD_POD=$(kubectl get pod -n "$NAMESPACE" -l app=hfi-dashboard -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
    if [ -n "$DASHBOARD_POD" ]; then
        # Wait a bit for Streamlit to fully start
        sleep 5

        if kubectl exec -n "$NAMESPACE" "$DASHBOARD_POD" -- curl -f -s http://localhost:8501/_stcore/health &> /dev/null; then
            print_success "Dashboard health check: Streamlit responding"
        else
            print_warning "Dashboard health check: Streamlit not responding yet (may need more time to start)"
        fi
    else
        print_warning "Dashboard pod not found, skipping health check"
    fi

    # Check Redis health if it exists
    REDIS_POD=$(kubectl get pod -n "$NAMESPACE" -l app=hfi-redis -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
    if [ -n "$REDIS_POD" ]; then
        if kubectl exec -n "$NAMESPACE" "$REDIS_POD" -- redis-cli ping &> /dev/null; then
            print_success "Redis health check: PONG received (optional)"
        else
            print_warning "Redis health check: No response (optional)"
        fi
    fi
}

check_connectivity() {
    print_header "Checking Inter-Service Connectivity"

    # Check if processor can reach database
    PROCESSOR_POD=$(kubectl get pod -n "$NAMESPACE" -l app=hfi-processor -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
    if [ -n "$PROCESSOR_POD" ]; then
        if kubectl exec -n "$NAMESPACE" "$PROCESSOR_POD" -- test -f /app/data/hfi.db &> /dev/null; then
            print_success "Processor can access database file (SQLite)"
        else
            print_warning "Database file not yet created (will be created on first run)"
        fi

        # Check config files
        if kubectl exec -n "$NAMESPACE" "$PROCESSOR_POD" -- test -f /app/config/glossary.json &> /dev/null; then
            print_success "Processor can access glossary.json (ConfigMap)"
        else
            print_error "Processor cannot access glossary.json"
        fi
    fi

    # Check if dashboard can reach database
    DASHBOARD_POD=$(kubectl get pod -n "$NAMESPACE" -l app=hfi-dashboard -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
    if [ -n "$DASHBOARD_POD" ]; then
        if kubectl exec -n "$NAMESPACE" "$DASHBOARD_POD" -- test -f /app/data/hfi.db &> /dev/null; then
            print_success "Dashboard can access database file (SQLite)"
        else
            print_warning "Dashboard cannot access database yet (normal if no data scraped)"
        fi
    fi
}

check_dashboard_access() {
    print_header "Checking Dashboard Accessibility"

    NODE_PORT=$(kubectl get service hfi-dashboard -n "$NAMESPACE" -o jsonpath='{.spec.ports[0].nodePort}' 2>/dev/null || echo "")

    if [ -z "$NODE_PORT" ]; then
        print_error "Cannot determine dashboard NodePort"
        return
    fi

    print_info "Dashboard should be accessible at:"
    print_info "  http://localhost:${NODE_PORT}"

    # Try to curl the dashboard from host
    if command -v curl &> /dev/null; then
        if curl -f -s --max-time 5 "http://localhost:${NODE_PORT}/_stcore/health" &> /dev/null; then
            print_success "Dashboard is accessible from host via http://localhost:${NODE_PORT}"
        else
            print_warning "Dashboard not accessible from host yet (may need more time to start)"
            print_info "Try accessing manually: http://localhost:${NODE_PORT}"
        fi
    fi

    # Get node IP for alternative access
    NODE_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}' 2>/dev/null || echo "")
    if [ -n "$NODE_IP" ]; then
        print_info "  or http://${NODE_IP}:${NODE_PORT} (from other machines on network)"
    fi
}

check_logs() {
    print_header "Checking Pod Logs for Errors"

    # Check processor logs
    PROCESSOR_POD=$(kubectl get pod -n "$NAMESPACE" -l app=hfi-processor -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
    if [ -n "$PROCESSOR_POD" ]; then
        ERROR_COUNT=$(kubectl logs -n "$NAMESPACE" "$PROCESSOR_POD" --tail=100 2>/dev/null | grep -i "error" | wc -l)
        if [ "$ERROR_COUNT" -eq 0 ]; then
            print_success "Processor logs: No errors in last 100 lines"
        else
            print_warning "Processor logs: Found ${ERROR_COUNT} error(s) in last 100 lines"
            print_info "View logs: kubectl logs -n ${NAMESPACE} ${PROCESSOR_POD}"
        fi
    fi

    # Check dashboard logs
    DASHBOARD_POD=$(kubectl get pod -n "$NAMESPACE" -l app=hfi-dashboard -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
    if [ -n "$DASHBOARD_POD" ]; then
        ERROR_COUNT=$(kubectl logs -n "$NAMESPACE" "$DASHBOARD_POD" --tail=100 2>/dev/null | grep -i "error" | wc -l)
        if [ "$ERROR_COUNT" -eq 0 ]; then
            print_success "Dashboard logs: No errors in last 100 lines"
        else
            print_warning "Dashboard logs: Found ${ERROR_COUNT} error(s) in last 100 lines"
            print_info "View logs: kubectl logs -n ${NAMESPACE} ${DASHBOARD_POD}"
        fi
    fi
}

check_resource_usage() {
    print_header "Checking Resource Usage"

    # Check if metrics-server is available
    if kubectl top pods -n "$NAMESPACE" &> /dev/null; then
        print_success "Metrics server is available"

        # Show pod resource usage
        print_info "Current resource usage:"
        kubectl top pods -n "$NAMESPACE" 2>/dev/null | while IFS= read -r line; do
            print_info "  ${line}"
        done
    else
        print_warning "Metrics server not available (optional)"
        print_info "Install with: kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml"
    fi
}

# ================================================================
# Summary
# ================================================================

print_summary() {
    print_header "Verification Summary"

    echo -e "${GREEN}Passed: ${PASSED}${NC}"
    echo -e "${YELLOW}Warnings: ${WARNINGS}${NC}"
    echo -e "${RED}Failed: ${FAILED}${NC}"

    echo ""

    if [ $FAILED -eq 0 ]; then
        echo -e "${GREEN}✓ Deployment verified successfully!${NC}"
        echo ""
        echo -e "${GREEN}Next Steps:${NC}"
        echo -e "  1. Access dashboard: http://localhost:$(kubectl get svc hfi-dashboard -n $NAMESPACE -o jsonpath='{.spec.ports[0].nodePort}' 2>/dev/null || echo '30080')"
        echo -e "  2. View processor logs: kubectl logs -f -n ${NAMESPACE} deployment/hfi-processor"
        echo -e "  3. Trigger scraper manually: kubectl create job -n ${NAMESPACE} --from=cronjob/hfi-scraper manual-scrape-\$(date +%s)"
        echo -e "  4. Monitor pods: kubectl get pods -n ${NAMESPACE} -w"
        return 0
    else
        echo -e "${RED}✗ Deployment verification failed${NC}"
        echo -e "${RED}Fix the errors above and retry${NC}"
        echo ""
        echo -e "${YELLOW}Troubleshooting Commands:${NC}"
        echo -e "  kubectl get all -n ${NAMESPACE}"
        echo -e "  kubectl describe pod <pod-name> -n ${NAMESPACE}"
        echo -e "  kubectl logs <pod-name> -n ${NAMESPACE}"
        echo -e "  kubectl get events -n ${NAMESPACE} --sort-by='.lastTimestamp'"
        return 1
    fi
}

# ================================================================
# Main
# ================================================================

main() {
    echo -e "${BLUE}"
    cat << "EOF"
  _   _ _____ ___
 | | | |  ___|_ _|
 | |_| | |_   | |
 |  _  |  _|  | |
 |_| |_|_|   |___|

 Hebrew FinTech Informant
 Post-Deployment Verification
EOF
    echo -e "${NC}"

    # Check kubectl access first
    if ! kubectl cluster-info &> /dev/null; then
        print_error "Cannot access Kubernetes cluster"
        print_info "Configure kubectl: export KUBECONFIG=/etc/rancher/k3s/k3s.yaml"
        exit 1
    fi

    check_namespace
    check_secrets
    check_configmap
    check_pvcs
    check_deployments
    check_pods
    check_services
    check_cronjob
    check_health
    check_connectivity
    check_dashboard_access
    check_logs
    check_resource_usage

    print_summary
}

main "$@"
