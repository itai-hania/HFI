#!/usr/bin/env python3
"""
Cross-Platform Service Launcher for HFI

Canonical service launcher for HFI, designed to provide a consistent
experience on both Windows and macOS/Linux systems.
"""

import os
import sys
import subprocess
import platform
from pathlib import Path


class Colors:
    """ANSI color codes for terminal output (works on most modern terminals)."""
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'
    
    @classmethod
    def supports_color(cls) -> bool:
        """Check if terminal supports ANSI colors."""
        if platform.system() == 'Windows':
            return os.environ.get('TERM') is not None or 'WT_SESSION' in os.environ
        return hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()


def colorize(text: str, color: str) -> str:
    """Apply color to text if terminal supports it."""
    if Colors.supports_color():
        return f"{color}{text}{Colors.NC}"
    return text


def print_banner():
    """Print the HFI service launcher banner."""
    print(colorize("=" * 45, Colors.BLUE))
    print(colorize("  HFI Service Launcher (Cross-Platform)", Colors.BLUE))
    print(colorize("=" * 45, Colors.BLUE))
    print()


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.resolve()


def check_env_file(project_root: Path) -> bool:
    """Check if .env file exists."""
    env_file = project_root / ".env"
    if not env_file.exists():
        print(colorize("❌ .env file not found!", Colors.RED))
        print(colorize("→ Create a .env file with your credentials", Colors.YELLOW))
        return False
    return True


def check_database(project_root: Path) -> bool:
    """Check if database exists, initialize if not."""
    db_file = project_root / "data" / "hfi.db"
    if not db_file.exists():
        print(colorize("⚠️  Database not found. Initializing...", Colors.YELLOW))
        init_script = project_root / "tools" / "init_db.py"
        result = subprocess.run([sys.executable, str(init_script)], cwd=project_root)
        if result.returncode != 0:
            print(colorize("❌ Failed to initialize database", Colors.RED))
            return False
        print()
    return True


def run_scraper_first_time(project_root: Path):
    """Run scraper with visible browser for first-time login."""
    print(colorize("🚀 Starting Scraper (first time setup)...", Colors.GREEN))
    print(colorize("→ Browser will open for manual login", Colors.YELLOW))
    print()
    
    scraper_dir = project_root / "src" / "scraper"
    env = os.environ.copy()
    env["SCRAPER_HEADLESS"] = "false"
    
    subprocess.run(
        [sys.executable, "main.py"],
        cwd=scraper_dir,
        env=env
    )


def run_scraper_automated(project_root: Path):
    """Run scraper in headless mode using saved session."""
    print(colorize("🚀 Starting Scraper (automated)...", Colors.GREEN))
    
    scraper_dir = project_root / "src" / "scraper"
    env = os.environ.copy()
    env["SCRAPER_HEADLESS"] = "true"
    
    subprocess.run(
        [sys.executable, "main.py"],
        cwd=scraper_dir,
        env=env
    )


def run_docker_build(project_root: Path):
    """Build Docker images."""
    print(colorize("🐳 Building Docker images...", Colors.GREEN))
    result = subprocess.run(["docker-compose", "build"], cwd=project_root)
    if result.returncode == 0:
        print()
        print(colorize("✅ Build complete!", Colors.GREEN))


def run_docker_services(project_root: Path):
    """Start Docker services."""
    print(colorize("🐳 Starting Docker services...", Colors.GREEN))
    result = subprocess.run(["docker-compose", "up", "-d"], cwd=project_root)
    if result.returncode == 0:
        print()
        print(colorize("✅ Services started!", Colors.GREEN))
        print(colorize("→ To view logs: docker-compose logs -f", Colors.YELLOW))


def run_verify_setup(project_root: Path):
    """Run the setup verification script."""
    print(colorize("🔍 Verifying setup...", Colors.GREEN))
    verify_script = project_root / "tools" / "verify_setup.py"
    subprocess.run([sys.executable, str(verify_script)], cwd=project_root)


def show_menu() -> str:
    """Display menu and get user choice."""
    print("What would you like to do?")
    print()
    print("1) Run Scraper (first time - manual login)")
    print("2) Run Scraper (automated - uses saved session)")
    print("3) Docker: Build all images")
    print("4) Docker: Start all services")
    print("5) Verify setup")
    print("6) Exit")
    print()
    return input("Enter choice [1-6]: ").strip()


def main():
    """Main entry point."""
    print_banner()
    
    project_root = get_project_root()
    
    if not check_env_file(project_root):
        return 1
    
    if not check_database(project_root):
        return 1
    
    choice = show_menu()
    
    if choice == "1":
        run_scraper_first_time(project_root)
    elif choice == "2":
        run_scraper_automated(project_root)
    elif choice == "3":
        run_docker_build(project_root)
    elif choice == "4":
        run_docker_services(project_root)
    elif choice == "5":
        run_verify_setup(project_root)
    elif choice == "6":
        print(colorize("👋 Goodbye!", Colors.BLUE))
        return 0
    else:
        print(colorize("❌ Invalid choice", Colors.RED))
        return 1
    
    print()
    print(colorize("✅ Done!", Colors.GREEN))
    return 0


if __name__ == "__main__":
    sys.exit(main())
