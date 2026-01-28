#!/bin/bash
# Docker Build and Validation Script for HFI Project
# This script builds all Docker images and validates the setup

set -e  # Exit on error
set -u  # Exit on undefined variable

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function to check if Docker is installed
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker Desktop from https://www.docker.com/products/docker-desktop"
        exit 1
    fi
    print_success "Docker is installed: $(docker --version)"
}

# Function to check if Docker daemon is running
check_docker_daemon() {
    if ! docker info &> /dev/null; then
        print_error "Docker daemon is not running. Please start Docker Desktop."
        exit 1
    fi
    print_success "Docker daemon is running"
}

# Function to check if .env file exists
check_env_file() {
    if [ ! -f "$PROJECT_ROOT/.env" ]; then
        print_error ".env file not found. Please create a .env file with your credentials."
        exit 1
    else
        print_success ".env file exists"
    fi
}

# Function to create required directories
create_directories() {
    print_status "Creating required directories..."
    mkdir -p "$PROJECT_ROOT/data/media"
    mkdir -p "$PROJECT_ROOT/data/session"
    mkdir -p "$PROJECT_ROOT/config"
    print_success "Directories created"
}

# Function to build a specific service
build_service() {
    local service=$1
    print_status "Building $service service..."

    if docker compose build "$service"; then
        print_success "$service service built successfully"
        return 0
    else
        print_error "Failed to build $service service"
        return 1
    fi
}

# Function to validate Dockerfiles
validate_dockerfiles() {
    print_status "Validating Dockerfiles..."

    local dockerfiles=(
        "src/scraper/Dockerfile"
        "src/processor/Dockerfile"
        "src/dashboard/Dockerfile"
    )

    for dockerfile in "${dockerfiles[@]}"; do
        if [ ! -f "$PROJECT_ROOT/$dockerfile" ]; then
            print_error "Dockerfile not found: $dockerfile"
            exit 1
        fi
    done

    print_success "All Dockerfiles found"
}

# Function to validate requirements.txt files
validate_requirements() {
    print_status "Validating requirements.txt files..."

    local req_files=(
        "src/scraper/requirements.txt"
        "src/processor/requirements.txt"
        "src/dashboard/requirements.txt"
    )

    for req_file in "${req_files[@]}"; do
        if [ ! -f "$PROJECT_ROOT/$req_file" ]; then
            print_error "Requirements file not found: $req_file"
            exit 1
        fi
    done

    print_success "All requirements.txt files found"
}

# Main execution
main() {
    echo "=========================================="
    echo "  HFI Docker Build & Validation Script"
    echo "=========================================="
    echo ""

    # Pre-flight checks
    print_status "Running pre-flight checks..."
    check_docker
    check_docker_daemon
    check_env_file
    validate_dockerfiles
    validate_requirements
    create_directories

    echo ""
    print_status "Starting Docker image builds..."
    echo ""

    # Build services
    local failed_services=()

    # Build Redis (just pulls the image)
    print_status "Pulling Redis image..."
    if docker compose pull redis; then
        print_success "Redis image pulled successfully"
    else
        print_error "Failed to pull Redis image"
        failed_services+=("redis")
    fi

    # Build custom services
    for service in scraper processor dashboard; do
        if ! build_service "$service"; then
            failed_services+=("$service")
        fi
    done

    echo ""
    echo "=========================================="

    # Summary
    if [ ${#failed_services[@]} -eq 0 ]; then
        print_success "All services built successfully!"
        echo ""
        print_status "Next steps:"
        echo "  1. Edit .env file with your credentials"
        echo "  2. Run: docker compose up -d"
        echo "  3. Check status: docker compose ps"
        echo "  4. View logs: docker compose logs -f"
        echo "  5. Access dashboard: http://localhost:8501"
        echo ""
        print_status "To run the scraper manually:"
        echo "  docker compose exec scraper python main.py"
        echo ""
    else
        print_error "Failed to build the following services:"
        for service in "${failed_services[@]}"; do
            echo "  - $service"
        done
        exit 1
    fi
}

# Run main function
main "$@"
