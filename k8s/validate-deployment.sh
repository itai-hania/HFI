#!/usr/bin/env bash
# ================================================================
# HFI Pre-Deployment Validation Script
# ================================================================
# This script validates prerequisites and configuration before
# deploying HFI to K3s. It checks:
# - K3s cluster accessibility
# - Required CLI tools
# - Secrets configuration
# - Manifest syntax
# - Resource availability
# - Docker images
#
# Usage: ./k8s/validate-deployment.sh
# ================================================================

set -e  # Exit on error
set -u  # Exit on undefined variable

# ================================================================
# Configuration
# ================================================================

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
K8S_DIR="${PROJECT_ROOT}/k8s"

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
# Validation Checks
# ================================================================

check_prerequisites() {
    print_header "Checking Prerequisites"

    # Docker
    if command -v docker &> /dev/null; then
        DOCKER_VERSION=$(docker --version | awk '{print $3}' | sed 's/,//')
        print_success "Docker installed: ${DOCKER_VERSION}"
    else
        print_error "Docker not found. Install from: https://docs.docker.com/engine/install/"
    fi

    # kubectl
    if command -v kubectl &> /dev/null; then
        KUBECTL_VERSION=$(kubectl version --client --short 2>/dev/null | awk '{print $3}')
        print_success "kubectl installed: ${KUBECTL_VERSION}"
    else
        print_error "kubectl not found. Install from: https://kubernetes.io/docs/tasks/tools/"
    fi

    # K3s
    if command -v k3s &> /dev/null; then
        K3S_VERSION=$(k3s --version | head -n1 | awk '{print $3}')
        print_success "K3s installed: ${K3S_VERSION}"
    else
        print_error "K3s not found. Install with: curl -sfL https://get.k3s.io | sh -"
    fi

    # jq (optional but useful)
    if command -v jq &> /dev/null; then
        print_success "jq installed (optional tool)"
    else
        print_warning "jq not installed (optional). Install with: apt-get install jq"
    fi
}

check_cluster_access() {
    print_header "Checking K3s Cluster Access"

    # Check kubectl can access cluster
    if kubectl cluster-info &> /dev/null; then
        print_success "kubectl can access K3s cluster"

        # Get cluster info
        CLUSTER_ENDPOINT=$(kubectl cluster-info | head -n1 | awk '{print $NF}')
        print_info "Cluster endpoint: ${CLUSTER_ENDPOINT}"
    else
        print_error "kubectl cannot access cluster"
        print_info "Configure with: export KUBECONFIG=/etc/rancher/k3s/k3s.yaml"
        print_info "Or copy to: mkdir -p ~/.kube && sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config"
        return
    fi

    # Check node status
    NODE_STATUS=$(kubectl get nodes -o jsonpath='{.items[0].status.conditions[?(@.type=="Ready")].status}')
    if [ "$NODE_STATUS" = "True" ]; then
        NODE_NAME=$(kubectl get nodes -o jsonpath='{.items[0].metadata.name}')
        print_success "Node ${NODE_NAME} is Ready"
    else
        print_error "Node is not Ready"
    fi

    # Check storage class
    if kubectl get storageclass local-path &> /dev/null; then
        print_success "local-path StorageClass exists"
    else
        print_error "local-path StorageClass not found (required for PVCs)"
    fi
}

check_secrets() {
    print_header "Checking Secrets Configuration"

    if [ ! -f "${K8S_DIR}/secrets.yaml" ]; then
        print_error "secrets.yaml not found"
        print_info "Create from template: cp k8s/secrets.yaml.template k8s/secrets.yaml"
        return
    fi

    print_success "secrets.yaml exists"

    # Check for placeholder values
    if grep -q "<REPLACE_ME" "${K8S_DIR}/secrets.yaml"; then
        print_error "secrets.yaml contains placeholder values (<REPLACE_ME)"
        print_info "Edit k8s/secrets.yaml and replace all placeholder values"
    else
        print_success "secrets.yaml has no placeholder values"
    fi

    # Check required keys exist
    REQUIRED_KEYS=("X_USERNAME" "X_PASSWORD" "OPENAI_API_KEY" "DATABASE_URL")
    for key in "${REQUIRED_KEYS[@]}"; do
        if grep -q "${key}:" "${K8S_DIR}/secrets.yaml"; then
            print_success "Required key found: ${key}"
        else
            print_error "Required key missing: ${key}"
        fi
    done

    # Validate OPENAI_API_KEY format
    if grep -E "OPENAI_API_KEY.*sk-proj-[a-zA-Z0-9]+" "${K8S_DIR}/secrets.yaml" &> /dev/null; then
        print_success "OPENAI_API_KEY format looks valid"
    else
        print_warning "OPENAI_API_KEY format may be invalid (should start with sk-proj-)"
    fi
}

check_manifests() {
    print_header "Checking Kubernetes Manifests"

    MANIFESTS=(
        "namespace.yaml"
        "secrets.yaml"
        "configmap.yaml"
        "pvc.yaml"
        "deployment-processor.yaml"
        "deployment-dashboard.yaml"
        "cronjob-scraper.yaml"
    )

    for manifest in "${MANIFESTS[@]}"; do
        MANIFEST_PATH="${K8S_DIR}/${manifest}"

        if [ ! -f "$MANIFEST_PATH" ]; then
            print_error "${manifest} not found"
            continue
        fi

        # Validate YAML syntax with kubectl dry-run
        if kubectl apply --dry-run=client -f "$MANIFEST_PATH" &> /dev/null; then
            print_success "${manifest} syntax valid"
        else
            print_error "${manifest} syntax invalid"
            kubectl apply --dry-run=client -f "$MANIFEST_PATH" 2>&1 | head -n5
        fi
    done

    # Check optional Redis manifest
    if [ -f "${K8S_DIR}/deployment-redis.yaml" ]; then
        if kubectl apply --dry-run=client -f "${K8S_DIR}/deployment-redis.yaml" &> /dev/null; then
            print_success "deployment-redis.yaml syntax valid (optional)"
        else
            print_warning "deployment-redis.yaml syntax invalid (optional)"
        fi
    fi
}

check_docker_images() {
    print_header "Checking Docker Images"

    IMAGES=("hfi-scraper:latest" "hfi-processor:latest" "hfi-dashboard:latest")

    for image in "${IMAGES[@]}"; do
        if docker images --format "{{.Repository}}:{{.Tag}}" | grep -q "^${image}$"; then
            IMAGE_SIZE=$(docker images --format "{{.Size}}" "${image}")
            print_success "${image} exists (${IMAGE_SIZE})"
        else
            print_warning "${image} not found (will be built during deployment)"
        fi
    done

    # Check if images are imported to K3s
    if command -v k3s &> /dev/null; then
        print_info "Checking K3s containerd images..."
        for image in "${IMAGES[@]}"; do
            if sudo k3s ctr images ls | grep -q "${image}"; then
                print_success "${image} imported to K3s"
            else
                print_warning "${image} not imported to K3s yet"
            fi
        done
    fi
}

check_dockerfiles() {
    print_header "Checking Dockerfiles"

    DOCKERFILES=(
        "src/scraper/Dockerfile"
        "src/processor/Dockerfile"
        "src/dashboard/Dockerfile"
    )

    for dockerfile in "${DOCKERFILES[@]}"; do
        DOCKERFILE_PATH="${PROJECT_ROOT}/${dockerfile}"

        if [ ! -f "$DOCKERFILE_PATH" ]; then
            print_error "${dockerfile} not found"
            continue
        fi

        # Basic Dockerfile validation
        if grep -q "^FROM" "$DOCKERFILE_PATH"; then
            print_success "${dockerfile} exists and has FROM statement"
        else
            print_error "${dockerfile} invalid (no FROM statement)"
        fi

        # Check for security best practices
        if grep -q "USER" "$DOCKERFILE_PATH"; then
            print_success "${dockerfile} runs as non-root user"
        else
            print_warning "${dockerfile} may run as root (security concern)"
        fi
    done
}

check_config_files() {
    print_header "Checking Configuration Files"

    # Check ConfigMap has required keys
    if grep -q "glossary.json:" "${K8S_DIR}/configmap.yaml"; then
        print_success "ConfigMap contains glossary.json"
    else
        print_error "ConfigMap missing glossary.json"
    fi

    if grep -q "style.txt:" "${K8S_DIR}/configmap.yaml"; then
        print_success "ConfigMap contains style.txt"
    else
        print_error "ConfigMap missing style.txt"
    fi

    # Check .env file (for local development)
    if [ -f "${PROJECT_ROOT}/.env" ]; then
        print_success ".env file exists (for local development)"

        if grep -q "OPENAI_API_KEY" "${PROJECT_ROOT}/.env"; then
            print_success ".env contains OPENAI_API_KEY"
        else
            print_warning ".env missing OPENAI_API_KEY"
        fi
    else
        print_warning ".env file not found (needed for local Docker Compose)"
    fi
}

check_resource_availability() {
    print_header "Checking Resource Availability"

    # Check node resources
    if kubectl get nodes &> /dev/null; then
        # Get allocatable resources
        ALLOCATABLE_CPU=$(kubectl get nodes -o jsonpath='{.items[0].status.allocatable.cpu}')
        ALLOCATABLE_MEM=$(kubectl get nodes -o jsonpath='{.items[0].status.allocatable.memory}' | sed 's/Ki//')
        ALLOCATABLE_MEM_GB=$((ALLOCATABLE_MEM / 1024 / 1024))

        print_info "Node allocatable resources:"
        print_info "  CPU: ${ALLOCATABLE_CPU} cores"
        print_info "  Memory: ${ALLOCATABLE_MEM_GB} GB"

        # Check if resources meet minimum requirements
        # HFI needs: ~2 CPU cores, ~3GB RAM
        if [ "$ALLOCATABLE_MEM_GB" -ge 3 ]; then
            print_success "Sufficient memory available (>= 3GB)"
        else
            print_warning "Low memory available. Consider upgrading or reducing resource limits."
        fi

        # Check disk space
        DISK_USAGE=$(df -BG /var/lib/rancher/k3s 2>/dev/null | awk 'NR==2 {print $4}' | sed 's/G//')
        if [ -n "$DISK_USAGE" ] && [ "$DISK_USAGE" -ge 10 ]; then
            print_success "Sufficient disk space available (${DISK_USAGE}GB free)"
        else
            print_warning "Low disk space. Ensure at least 20GB available."
        fi
    fi
}

check_network_connectivity() {
    print_header "Checking Network Connectivity"

    # Check OpenAI API connectivity
    if curl -s --connect-timeout 5 https://api.openai.com &> /dev/null; then
        print_success "Can reach OpenAI API (api.openai.com)"
    else
        print_error "Cannot reach OpenAI API. Check internet connectivity."
    fi

    # Check Docker Hub connectivity (for base images)
    if curl -s --connect-timeout 5 https://registry-1.docker.io &> /dev/null; then
        print_success "Can reach Docker Hub (registry-1.docker.io)"
    else
        print_warning "Cannot reach Docker Hub. May need to use cached images."
    fi

    # Check X (Twitter) connectivity
    if curl -s --connect-timeout 5 https://twitter.com &> /dev/null; then
        print_success "Can reach X/Twitter (twitter.com)"
    else
        print_warning "Cannot reach X/Twitter. Check if site is accessible."
    fi
}

# ================================================================
# Summary
# ================================================================

print_summary() {
    print_header "Validation Summary"

    echo -e "${GREEN}Passed: ${PASSED}${NC}"
    echo -e "${YELLOW}Warnings: ${WARNINGS}${NC}"
    echo -e "${RED}Failed: ${FAILED}${NC}"

    echo ""

    if [ $FAILED -eq 0 ]; then
        echo -e "${GREEN}✓ All critical checks passed!${NC}"
        echo -e "${GREEN}You can proceed with deployment: ./k8s/deploy.sh${NC}"
        return 0
    else
        echo -e "${RED}✗ ${FAILED} critical check(s) failed${NC}"
        echo -e "${RED}Fix the errors above before deploying${NC}"
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
 Pre-Deployment Validation
EOF
    echo -e "${NC}"

    check_prerequisites
    check_cluster_access
    check_secrets
    check_manifests
    check_dockerfiles
    check_docker_images
    check_config_files
    check_resource_availability
    check_network_connectivity

    print_summary
}

main "$@"
