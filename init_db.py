#!/usr/bin/env python3
"""
Database initialization script for HFI

This script creates all necessary database tables and directories.
Run this before starting any services.
"""

import sys
from pathlib import Path

try:
    from common.models import create_tables
except ImportError:
    sys.path.append(str(Path(__file__).parent / "src"))
    from common.models import create_tables


def init_directories():
    """Create necessary directories"""
    dirs = [
        "data",
        "data/media",
        "data/session",
        "config",
    ]

    for dir_path in dirs:
        path = Path(__file__).parent / dir_path
        path.mkdir(parents=True, exist_ok=True)
        print(f"✅ Created directory: {dir_path}")


def main():
    print("🚀 Initializing HFI Database...")
    print("="*60)

    # Create directories
    print("\n📁 Creating directories...")
    init_directories()

    # Create database tables
    print("\n🗄️  Creating database tables...")
    create_tables()

    print("\n" + "="*60)
    print("✅ Database initialization complete!")
    print("\nNext steps:")
    print("1. Create a .env file with your credentials")
    print("2. Run the scraper: cd src/scraper && python main.py")
    print("3. Run the dashboard: cd src/dashboard && streamlit run app.py")
    print("="*60)


if __name__ == "__main__":
    main()
