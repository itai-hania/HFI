#!/bin/bash
# Docker Environment Validation Script for HFI Project
# Validates Docker setup and running containers

set -e
set -u

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

print_error() {
    echo -e "${RED}[FAIL]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

CHECKS_PASSED=0
CHECKS_FAILED=0

check_docker_installed() {
    print_status "Checking if Docker is installed..."
    if command -v docker &> /dev/null; then
        DOCKER_VERSION=$(docker --version)
        print_success "Docker is installed: $DOCKER_VERSION"
        ((CHECKS_PASSED++))
        return 0
    else
        print_error "Docker is not installed"
        ((CHECKS_FAILED++))
        return 1
    fi
}

check_docker_running() {
    print_status "Checking if Docker daemon is running..."
    if docker info &> /dev/null; then
        print_success "Docker daemon is running"
        ((CHECKS_PASSED++))
        return 0
    else
        print_error "Docker daemon is not running"
        ((CHECKS_FAILED++))
        return 1
    fi
}

check_docker_compose() {
    print_status "Checking Docker Compose version..."
    if docker compose version &> /dev/null; then
        COMPOSE_VERSION=$(docker compose version)
        print_success "Docker Compose is available: $COMPOSE_VERSION"
        ((CHECKS_PASSED++))
        return 0
    else
        print_error "Docker Compose is not available"
        ((CHECKS_FAILED++))
        return 1
    fi
}

check_images_built() {
    print_status "Checking if Docker images are built..."
    local all_built=true

    for image in scraper processor dashboard; do
        if docker images | grep -q "hfi-$image"; then
            print_success "Image hfi-$image exists"
        else
            print_warning "Image hfi-$image not found (run ./docker-build.sh)"
            all_built=false
        fi
    done

    if [ "$all_built" = true ]; then
        ((CHECKS_PASSED++))
        return 0
    else
        ((CHECKS_FAILED++))
        return 1
    fi
}

check_containers_running() {
    print_status "Checking if containers are running..."

    if ! docker compose ps &> /dev/null; then
        print_warning "No containers are running (run: docker compose up -d)"
        ((CHECKS_FAILED++))
        return 1
    fi

    local services=("redis" "scraper" "processor" "dashboard")
    local all_running=true

    for service in "${services[@]}"; do
        if docker compose ps | grep -q "hfi-$service.*Up"; then
            print_success "Container hfi-$service is running"
        else
            print_warning "Container hfi-$service is not running"
            all_running=false
        fi
    done

    if [ "$all_running" = true ]; then
        ((CHECKS_PASSED++))
        return 0
    else
        ((CHECKS_FAILED++))
        return 1
    fi
}

check_redis_health() {
    print_status "Checking Redis health..."
    if docker compose exec -T redis redis-cli ping 2>/dev/null | grep -q "PONG"; then
        print_success "Redis is healthy"
        ((CHECKS_PASSED++))
        return 0
    else
        print_warning "Redis is not responding"
        ((CHECKS_FAILED++))
        return 1
    fi
}

check_dashboard_accessible() {
    print_status "Checking if dashboard is accessible..."
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:8501/_stcore/health | grep -q "200"; then
        print_success "Dashboard is accessible at http://localhost:8501"
        ((CHECKS_PASSED++))
        return 0
    else
        print_warning "Dashboard is not accessible (may still be starting up)"
        ((CHECKS_FAILED++))
        return 1
    fi
}

check_database_exists() {
    print_status "Checking if database exists..."
    if [ -f "$PROJECT_ROOT/data/hfi.db" ]; then
        DB_SIZE=$(du -h "$PROJECT_ROOT/data/hfi.db" | cut -f1)
        print_success "Database exists: data/hfi.db ($DB_SIZE)"
        ((CHECKS_PASSED++))
        return 0
    else
        print_warning "Database not found (will be created on first run)"
        ((CHECKS_FAILED++))
        return 1
    fi
}

check_env_file() {
    print_status "Checking .env file configuration..."
    if [ ! -f "$PROJECT_ROOT/.env" ]; then
        print_error ".env file not found"
        ((CHECKS_FAILED++))
        return 1
    fi

    # Check for required variables
    local required_vars=("OPENAI_API_KEY" "DATABASE_URL" "LOG_LEVEL")
    local all_present=true

    for var in "${required_vars[@]}"; do
        if grep -q "^$var=" "$PROJECT_ROOT/.env"; then
            print_success "$var is configured"
        else
            print_warning "$var is missing in .env"
            all_present=false
        fi
    done

    # Check if using mock API key
    if grep -q "sk-test-mock-key" "$PROJECT_ROOT/.env"; then
        print_warning "Using mock OpenAI API key (processor will not work)"
    fi

    if [ "$all_present" = true ]; then
        ((CHECKS_PASSED++))
        return 0
    else
        ((CHECKS_FAILED++))
        return 1
    fi
}

check_volumes() {
    print_status "Checking Docker volumes..."
    if docker volume ls | grep -q "hfi_redis_data"; then
        print_success "Redis data volume exists"
        ((CHECKS_PASSED++))
        return 0
    else
        print_warning "Redis data volume not found"
        ((CHECKS_FAILED++))
        return 1
    fi
}

check_network() {
    print_status "Checking Docker network..."
    if docker network ls | grep -q "hfi-network"; then
        print_success "HFI network exists"
        ((CHECKS_PASSED++))
        return 0
    else
        print_warning "HFI network not found (will be created on docker compose up)"
        ((CHECKS_FAILED++))
        return 1
    fi
}

check_disk_space() {
    print_status "Checking available disk space..."
    local available=$(df -h "$PROJECT_ROOT" | tail -1 | awk '{print $4}')
    local available_gb=$(df -BG "$PROJECT_ROOT" | tail -1 | awk '{print $4}' | sed 's/G//')

    if [ "$available_gb" -ge 10 ]; then
        print_success "Sufficient disk space available: $available"
        ((CHECKS_PASSED++))
        return 0
    else
        print_warning "Low disk space: $available (recommend 10GB+)"
        ((CHECKS_FAILED++))
        return 1
    fi
}

check_docker_resources() {
    print_status "Checking Docker resource allocation..."
    if docker info 2>/dev/null | grep -q "Total Memory"; then
        local total_mem=$(docker info 2>/dev/null | grep "Total Memory" | awk '{print $3$4}')
        print_success "Docker memory allocation: $total_mem"
        ((CHECKS_PASSED++))
        return 0
    else
        print_warning "Could not determine Docker memory allocation"
        ((CHECKS_FAILED++))
        return 1
    fi
}

print_summary() {
    echo ""
    echo "=========================================="
    echo "         Validation Summary"
    echo "=========================================="
    echo ""
    print_success "Checks passed: $CHECKS_PASSED"
    if [ $CHECKS_FAILED -gt 0 ]; then
        print_error "Checks failed: $CHECKS_FAILED"
    else
        print_success "Checks failed: 0"
    fi
    echo ""

    if [ $CHECKS_FAILED -eq 0 ]; then
        print_success "All checks passed! HFI is ready to use."
        echo ""
        echo "Access dashboard: http://localhost:8501"
        echo "Run scraper: docker compose exec scraper python main.py"
        echo "View logs: docker compose logs -f"
        return 0
    else
        print_warning "Some checks failed. Review the output above."
        echo ""
        echo "Common fixes:"
        echo "  - Not built: ./docker-build.sh"
        echo "  - Not running: docker compose up -d"
        echo "  - Check logs: docker compose logs"
        return 1
    fi
}

main() {
    echo "=========================================="
    echo "  HFI Docker Validation Script"
    echo "=========================================="
    echo ""

    # Core checks (must pass)
    check_docker_installed || exit 1
    check_docker_running || exit 1
    check_docker_compose || exit 1

    echo ""
    print_status "Running configuration checks..."
    echo ""

    # Configuration checks
    check_env_file
    check_disk_space
    check_docker_resources

    echo ""
    print_status "Running build checks..."
    echo ""

    # Build checks
    check_images_built
    check_volumes
    check_network

    echo ""
    print_status "Running runtime checks..."
    echo ""

    # Runtime checks
    check_containers_running
    check_redis_health
    check_dashboard_accessible
    check_database_exists

    # Summary
    print_summary
}

main "$@"
