#!/usr/bin/env bash
# ================================================================
# HFI K3s Deployment Script
# ================================================================
# This script automates the complete deployment of HFI to K3s.
# It builds Docker images, imports them to K3s, and applies manifests.
#
# Prerequisites:
# - K3s installed and running
# - Docker installed
# - kubectl configured to access K3s cluster
#
# Usage:
#   ./k8s/deploy.sh [OPTIONS]
#
# Options:
#   --build-only      Build Docker images only, don't deploy
#   --deploy-only     Deploy to K3s only, skip image build
#   --with-redis      Deploy Redis (optional caching layer)
#   --help            Show this help message
#
# Examples:
#   ./k8s/deploy.sh                    # Full deployment
#   ./k8s/deploy.sh --with-redis       # Deploy with Redis
#   ./k8s/deploy.sh --build-only       # Build images only
# ================================================================

set -e  # Exit on error
set -u  # Exit on undefined variable

# ================================================================
# Configuration
# ================================================================

# Project root directory (assuming script is in k8s/ subdirectory)
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
K8S_DIR="${PROJECT_ROOT}/k8s"

# Docker image names
SCRAPER_IMAGE="hfi-scraper:latest"
PROCESSOR_IMAGE="hfi-processor:latest"
DASHBOARD_IMAGE="hfi-dashboard:latest"

# K8s namespace
NAMESPACE="hfi-system"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Flags
BUILD_ONLY=false
DEPLOY_ONLY=false
WITH_REDIS=false

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
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${BLUE}→ $1${NC}"
}

check_prerequisites() {
    print_header "Checking Prerequisites"

    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    print_success "Docker is installed"

    # Check if kubectl is installed
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl is not installed. Please install kubectl first."
        exit 1
    fi
    print_success "kubectl is installed"

    # Check if K3s is running
    if ! sudo systemctl is-active --quiet k3s 2>/dev/null && ! kubectl cluster-info &> /dev/null; then
        print_error "K3s is not running or kubectl is not configured."
        print_info "Install K3s with: curl -sfL https://get.k3s.io | sh -"
        print_info "Configure kubectl with: export KUBECONFIG=/etc/rancher/k3s/k3s.yaml"
        exit 1
    fi
    print_success "K3s is running"

    # Check if secrets.yaml exists
    if [ ! -f "${K8S_DIR}/secrets.yaml" ]; then
        print_warning "secrets.yaml not found!"
        print_info "Creating secrets.yaml from template..."
        cp "${K8S_DIR}/secrets.yaml.template" "${K8S_DIR}/secrets.yaml"
        print_warning "Please edit k8s/secrets.yaml with your credentials before deploying."
        print_info "Required values:"
        print_info "  - X_USERNAME: Your X (Twitter) account email"
        print_info "  - X_PASSWORD: Your X (Twitter) password"
        print_info "  - OPENAI_API_KEY: Your OpenAI API key"
        read -p "Press Enter after updating secrets.yaml to continue..."
    fi
    print_success "secrets.yaml exists"
}

build_images() {
    print_header "Building Docker Images"

    cd "${PROJECT_ROOT}"

    # Build scraper image
    print_info "Building scraper image..."
    docker build -t "${SCRAPER_IMAGE}" \
        -f src/scraper/Dockerfile \
        --build-arg BUILDKIT_INLINE_CACHE=1 \
        .  # Note: Scraper needs project root context for common/
    print_success "Scraper image built"

    # Build processor image
    print_info "Building processor image..."
    docker build -t "${PROCESSOR_IMAGE}" \
        -f src/processor/Dockerfile \
        --build-arg BUILDKIT_INLINE_CACHE=1 \
        .  # Note: Processor needs project root context for common/
    print_success "Processor image built"

    # Build dashboard image
    print_info "Building dashboard image..."
    docker build -t "${DASHBOARD_IMAGE}" \
        -f src/dashboard/Dockerfile \
        --build-arg BUILDKIT_INLINE_CACHE=1 \
        .  # Note: Dashboard needs project root context for common/
    print_success "Dashboard image built"

    # List built images
    print_info "Built images:"
    docker images | grep hfi | awk '{printf "  - %s:%s (%s)\n", $1, $2, $7}'
}

import_images_to_k3s() {
    print_header "Importing Images to K3s"

    # Create temporary directory for tar files
    TMP_DIR="/tmp/hfi-images"
    mkdir -p "${TMP_DIR}"

    # Save Docker images to tar archives
    print_info "Exporting scraper image..."
    docker save "${SCRAPER_IMAGE}" -o "${TMP_DIR}/hfi-scraper.tar"

    print_info "Exporting processor image..."
    docker save "${PROCESSOR_IMAGE}" -o "${TMP_DIR}/hfi-processor.tar"

    print_info "Exporting dashboard image..."
    docker save "${DASHBOARD_IMAGE}" -o "${TMP_DIR}/hfi-dashboard.tar"

    # Import to K3s containerd
    print_info "Importing scraper image to K3s..."
    sudo k3s ctr images import "${TMP_DIR}/hfi-scraper.tar"

    print_info "Importing processor image to K3s..."
    sudo k3s ctr images import "${TMP_DIR}/hfi-processor.tar"

    print_info "Importing dashboard image to K3s..."
    sudo k3s ctr images import "${TMP_DIR}/hfi-dashboard.tar"

    # Clean up tar files
    print_info "Cleaning up temporary files..."
    rm -rf "${TMP_DIR}"

    print_success "All images imported to K3s"

    # Verify imported images
    print_info "Imported images:"
    sudo k3s ctr images ls | grep hfi | awk '{printf "  - %s\n", $1}'
}

deploy_to_k3s() {
    print_header "Deploying to K3s"

    cd "${K8S_DIR}"

    # Apply manifests in order
    print_info "Creating namespace..."
    kubectl apply -f namespace.yaml

    print_info "Creating secrets..."
    kubectl apply -f secrets.yaml

    print_info "Creating ConfigMap..."
    kubectl apply -f configmap.yaml

    print_info "Creating PersistentVolumeClaim..."
    kubectl apply -f pvc.yaml

    # Deploy Redis if requested
    if [ "$WITH_REDIS" = true ]; then
        print_info "Deploying Redis..."
        kubectl apply -f deployment-redis.yaml
    fi

    print_info "Deploying processor..."
    kubectl apply -f deployment-processor.yaml

    print_info "Deploying dashboard..."
    kubectl apply -f deployment-dashboard.yaml

    print_info "Deploying scraper CronJob..."
    kubectl apply -f cronjob-scraper.yaml

    print_success "All manifests applied"
}

wait_for_pods() {
    print_header "Waiting for Pods to be Ready"

    print_info "Waiting for processor to be ready..."
    kubectl wait --for=condition=ready pod \
        -l app=hfi-processor \
        -n "${NAMESPACE}" \
        --timeout=120s || true

    print_info "Waiting for dashboard to be ready..."
    kubectl wait --for=condition=ready pod \
        -l app=hfi-dashboard \
        -n "${NAMESPACE}" \
        --timeout=120s || true

    if [ "$WITH_REDIS" = true ]; then
        print_info "Waiting for Redis to be ready..."
        kubectl wait --for=condition=ready pod \
            -l app=hfi-redis \
            -n "${NAMESPACE}" \
            --timeout=60s || true
    fi

    print_success "Pods are ready"
}

show_status() {
    print_header "Deployment Status"

    echo -e "\n${BLUE}All Resources:${NC}"
    kubectl get all -n "${NAMESPACE}"

    echo -e "\n${BLUE}PersistentVolumeClaims:${NC}"
    kubectl get pvc -n "${NAMESPACE}"

    echo -e "\n${BLUE}Secrets:${NC}"
    kubectl get secrets -n "${NAMESPACE}"

    echo -e "\n${BLUE}ConfigMaps:${NC}"
    kubectl get configmaps -n "${NAMESPACE}"

    echo -e "\n${BLUE}CronJobs:${NC}"
    kubectl get cronjobs -n "${NAMESPACE}"

    # Get dashboard URL
    NODE_PORT=$(kubectl get svc -n "${NAMESPACE}" hfi-dashboard -o jsonpath='{.spec.ports[0].nodePort}')

    print_header "Access Information"
    print_success "Dashboard is accessible at:"
    print_info "  http://localhost:${NODE_PORT}"
    print_info "  or http://<node-ip>:${NODE_PORT}"

    echo ""
    print_info "Useful commands:"
    echo "  View logs:"
    echo "    kubectl logs -f -n ${NAMESPACE} deployment/hfi-processor"
    echo "    kubectl logs -f -n ${NAMESPACE} deployment/hfi-dashboard"
    echo ""
    echo "  Trigger scraper manually:"
    echo "    kubectl create job -n ${NAMESPACE} --from=cronjob/hfi-scraper manual-scrape-\$(date +%s)"
    echo ""
    echo "  Check pod status:"
    echo "    kubectl get pods -n ${NAMESPACE}"
    echo ""
}

show_help() {
    cat << EOF
HFI K3s Deployment Script

Usage: ./k8s/deploy.sh [OPTIONS]

Options:
  --build-only      Build Docker images only, don't deploy
  --deploy-only     Deploy to K3s only, skip image build
  --with-redis      Deploy Redis (optional caching layer)
  --help            Show this help message

Examples:
  ./k8s/deploy.sh                    # Full deployment
  ./k8s/deploy.sh --with-redis       # Deploy with Redis
  ./k8s/deploy.sh --build-only       # Build images only

Prerequisites:
  - K3s installed and running
  - Docker installed
  - kubectl configured to access K3s cluster
  - secrets.yaml created from secrets.yaml.template

For more information, see: k8s/README.md
EOF
}

# ================================================================
# Main Script
# ================================================================

main() {
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --build-only)
                BUILD_ONLY=true
                shift
                ;;
            --deploy-only)
                DEPLOY_ONLY=true
                shift
                ;;
            --with-redis)
                WITH_REDIS=true
                shift
                ;;
            --help)
                show_help
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done

    # Print banner
    echo -e "${BLUE}"
    cat << "EOF"
  _   _ _____ ___
 | | | |  ___|_ _|
 | |_| | |_   | |
 |  _  |  _|  | |
 |_| |_|_|   |___|

 Hebrew FinTech Informant
 K3s Deployment Script
EOF
    echo -e "${NC}"

    # Check prerequisites
    check_prerequisites

    # Build images
    if [ "$DEPLOY_ONLY" = false ]; then
        build_images
        import_images_to_k3s
    else
        print_warning "Skipping image build (--deploy-only)"
    fi

    # Exit if build-only
    if [ "$BUILD_ONLY" = true ]; then
        print_success "Build completed. Exiting (--build-only)"
        exit 0
    fi

    # Deploy to K3s
    deploy_to_k3s

    # Wait for pods
    wait_for_pods

    # Show status
    show_status

    print_header "Deployment Complete!"
    print_success "HFI is now running on K3s"
}

# Run main function
main "$@"
