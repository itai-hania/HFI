#!/bin/bash
# Start Services Script for HFI
# This script helps you quickly start the Scraper or Dashboard services

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
else
    echo -e "${RED}❌ Python not found in PATH.${NC}"
    exit 1
fi

DASHBOARD_HOST="${HFI_DASHBOARD_HOST:-0.0.0.0}"
DASHBOARD_PORT="${HFI_DASHBOARD_PORT:-8501}"

if ! [[ "$DASHBOARD_PORT" =~ ^[0-9]+$ ]]; then
    DASHBOARD_PORT="8501"
fi

LAN_IP="$("$PYTHON_BIN" - <<'PY'
import socket

sock = None
ip = ""
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.connect(("8.8.8.8", 80))
    ip = sock.getsockname()[0]
except OSError:
    pass
finally:
    if sock is not None:
        sock.close()

print("" if ip.startswith("127.") else ip)
PY
)"

# Banner
echo -e "${BLUE}=====================================${NC}"
echo -e "${BLUE}  HFI Service Launcher${NC}"
echo -e "${BLUE}=====================================${NC}"
echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
    echo -e "${RED}❌ .env file not found!${NC}"
    echo -e "${YELLOW}→ Create a .env file with your credentials${NC}"
    echo -e "${YELLOW}→ Then edit .env with your credentials${NC}"
    exit 1
fi

# Check if database exists
if [ ! -f "data/hfi.db" ]; then
    echo -e "${YELLOW}⚠️  Database not found. Initializing...${NC}"
    "$PYTHON_BIN" init_db.py
    echo ""
fi

# Menu
echo "What would you like to do?"
echo ""
echo "1) Run Scraper (first time - manual login)"
echo "2) Run Scraper (automated - uses saved session)"
echo "3) Run Dashboard"
echo "4) Run both Dashboard and monitor Scraper"
echo "5) Docker: Build all images"
echo "6) Docker: Start all services"
echo "7) Verify setup"
echo "8) Exit"
echo ""
read -p "Enter choice [1-8]: " choice

case $choice in
    1)
        echo -e "${GREEN}🚀 Starting Scraper (first time setup)...${NC}"
        echo -e "${YELLOW}→ Browser will open for manual login${NC}"
        echo ""
        cd src/scraper
        export SCRAPER_HEADLESS=false
        "$PYTHON_BIN" main.py
        ;;
    2)
        echo -e "${GREEN}🚀 Starting Scraper (automated)...${NC}"
        cd src/scraper
        export SCRAPER_HEADLESS=true
        "$PYTHON_BIN" main.py
        ;;
    3)
        echo -e "${GREEN}🚀 Starting Dashboard...${NC}"
        echo -e "${BLUE}→ Dashboard local: http://localhost:${DASHBOARD_PORT}${NC}"
        if [ -n "$LAN_IP" ]; then
            echo -e "${BLUE}→ Dashboard mobile (same Wi-Fi): http://${LAN_IP}:${DASHBOARD_PORT}${NC}"
        fi
        if [ "$DASHBOARD_HOST" = "0.0.0.0" ]; then
            echo -e "${YELLOW}⚠️  Exposed on local network. Use trusted Wi-Fi only.${NC}"
        fi
        echo ""
        cd src/dashboard
        streamlit run app.py \
            --server.address="$DASHBOARD_HOST" \
            --server.port="$DASHBOARD_PORT" \
            --server.headless=true
        ;;
    4)
        echo -e "${GREEN}🚀 Starting Dashboard...${NC}"
        echo -e "${BLUE}→ Dashboard local: http://localhost:${DASHBOARD_PORT}${NC}"
        if [ -n "$LAN_IP" ]; then
            echo -e "${BLUE}→ Dashboard mobile (same Wi-Fi): http://${LAN_IP}:${DASHBOARD_PORT}${NC}"
        fi
        if [ "$DASHBOARD_HOST" = "0.0.0.0" ]; then
            echo -e "${YELLOW}⚠️  Exposed on local network. Use trusted Wi-Fi only.${NC}"
        fi
        echo ""
        cd src/dashboard
        streamlit run app.py \
            --server.address="$DASHBOARD_HOST" \
            --server.port="$DASHBOARD_PORT" \
            --server.headless=true &
        DASHBOARD_PID=$!

        echo ""
        echo -e "${YELLOW}Press ENTER to run scraper, or Ctrl+C to exit${NC}"
        read

        cd "$PROJECT_ROOT/src/scraper"
        export SCRAPER_HEADLESS=true
        "$PYTHON_BIN" main.py

        kill $DASHBOARD_PID
        ;;
    5)
        echo -e "${GREEN}🐳 Building Docker images...${NC}"
        docker-compose build
        echo ""
        echo -e "${GREEN}✅ Build complete!${NC}"
        ;;
    6)
        echo -e "${GREEN}🐳 Starting Docker services...${NC}"
        docker-compose up -d dashboard
        echo ""
        echo -e "${GREEN}✅ Services started!${NC}"
        echo -e "${BLUE}→ Dashboard: http://localhost:8501${NC}"
        echo -e "${YELLOW}→ To run scraper: docker-compose run scraper python main.py${NC}"
        echo -e "${YELLOW}→ To view logs: docker-compose logs -f dashboard${NC}"
        ;;
    7)
        echo -e "${GREEN}🔍 Verifying setup...${NC}"
        "$PYTHON_BIN" verify_setup.py
        ;;
    8)
        echo -e "${BLUE}👋 Goodbye!${NC}"
        exit 0
        ;;
    *)
        echo -e "${RED}❌ Invalid choice${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}✅ Done!${NC}"
