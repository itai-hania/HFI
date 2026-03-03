#!/usr/bin/env python3
"""
Setup Verification Script for HFI

This script checks that all required files and dependencies are in place.
Run this before starting the services to ensure everything is configured correctly.
"""

import sys
from pathlib import Path
import importlib.util


def check_file_exists(file_path: Path, description: str) -> bool:
    """Check if a file exists"""
    if file_path.exists():
        print(f"✅ {description}: {file_path}")
        return True
    else:
        print(f"❌ {description}: {file_path} - NOT FOUND")
        return False


def check_module(module_name: str) -> bool:
    """Check if a Python module is installed"""
    spec = importlib.util.find_spec(module_name)
    if spec is not None:
        print(f"✅ Module installed: {module_name}")
        return True
    else:
        print(f"❌ Module missing: {module_name}")
        return False


def main():
    print("🔍 HFI Setup Verification")
    print("="*60)

    project_root = Path(__file__).parent
    all_checks_passed = True

    # Check directory structure
    print("\n📁 Checking Directory Structure...")
    directories = [
        (project_root / "src" / "scraper", "Scraper directory"),
        (project_root / "src" / "dashboard", "Dashboard directory"),
        (project_root / "src" / "common", "Common directory"),
        (project_root / "data", "Data directory"),
        (project_root / "config", "Config directory"),
    ]

    for dir_path, description in directories:
        if not check_file_exists(dir_path, description):
            all_checks_passed = False

    # Check critical files
    print("\n📄 Checking Critical Files...")
    files = [
        # Scraper
        (project_root / "src" / "scraper" / "scraper.py", "Scraper main file"),
        (project_root / "src" / "scraper" / "main.py", "Scraper entry point"),
        (project_root / "src" / "scraper" / "requirements.txt", "Scraper requirements"),

        # Dashboard
        (project_root / "src" / "dashboard" / "app.py", "Dashboard app"),
        (project_root / "src" / "dashboard" / "requirements.txt", "Dashboard requirements"),

        # Common
        (project_root / "src" / "common" / "models.py", "Database models"),

        # Config
        (project_root / "config" / "glossary.json", "Glossary file"),
        (project_root / "config" / "style.txt", "Style guide"),
    ]

    for file_path, description in files:
        if not check_file_exists(file_path, description):
            all_checks_passed = False

    # Check environment file
    print("\n🔐 Checking Environment Configuration...")
    env_file = project_root / ".env"
    if env_file.exists():
        print(f"✅ Environment file exists: {env_file}")

        # Check for required variables
        with open(env_file) as f:
            env_content = f.read()
            required_vars = ["X_USERNAME", "X_PASSWORD", "DATABASE_URL"]

            for var in required_vars:
                if var in env_content:
                    print(f"  ✅ {var} is set")
                else:
                    print(f"  ⚠️  {var} is missing (optional for some services)")
    else:
        print(f"⚠️  Environment file not found: {env_file}")
        print("  → Create a .env file with your credentials")

    # Check Python modules (scraper dependencies)
    print("\n📦 Checking Scraper Dependencies...")
    scraper_modules = ["playwright", "fake_useragent", "sqlalchemy", "dotenv"]

    for module in scraper_modules:
        if not check_module(module):
            all_checks_passed = False
            print(f"  → Install with: pip install {module}")

    # Check Python modules (dashboard dependencies)
    print("\n📦 Checking Dashboard Dependencies...")
    dashboard_modules = ["streamlit", "sqlalchemy", "PIL"]

    for module in dashboard_modules:
        if not check_module(module):
            all_checks_passed = False
            if module == "PIL":
                print(f"  → Install with: pip install pillow")
            else:
                print(f"  → Install with: pip install {module}")

    # Check data directories
    print("\n💾 Checking Data Directories...")
    data_dirs = [
        project_root / "data" / "media",
        project_root / "data" / "session",
    ]

    for dir_path in data_dirs:
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"✅ Created/verified: {dir_path}")

    # Summary
    print("\n" + "="*60)
    if all_checks_passed:
        print("✅ All checks passed! System is ready.")
        print("\nNext steps:")
        print("1. Ensure .env is configured with your credentials")
        print("2. Run database initialization: python tools/init_db.py")
        print("3. Start scraper: cd src/scraper && python main.py")
        print("4. Start dashboard: cd src/dashboard && streamlit run app.py")
    else:
        print("⚠️  Some checks failed. Please resolve issues above.")
        print("\nCommon fixes:")
        print("- Install missing dependencies: pip install -r src/scraper/requirements.txt")
        print("- Install Playwright browsers: playwright install chromium")
        print("- Create .env file with your credentials")
        return 1

    print("="*60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
