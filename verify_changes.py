import sys
import os
from pathlib import Path

# Add src to path
sys.path.append(str(Path.cwd() / "src"))

print("🔍 Verifying imports...")

# 1. Verify News Scraper
try:
    from scraper.news_scraper import NewsScraper
    print("✅ NewsScraper imported successfully")
except Exception as e:
    print(f"❌ NewsScraper import failed: {e}")
    sys.exit(1)

# 2. Verify Scraper (Playwright)
try:
    from scraper.scraper import TwitterScraper
    print("✅ TwitterScraper imported successfully")
except Exception as e:
    print(f"❌ TwitterScraper import failed: {e}")
    sys.exit(1)

# 3. Verify Dashboard (Streamlit app structure)
try:
    # We can't run streamlit app here, but we can check if it compiles
    with open("src/dashboard/app.py", "r") as f:
        compile(f.read(), "src/dashboard/app.py", "exec")
    print("✅ Dashboard syntax verified")
except Exception as e:
    print(f"❌ Dashboard syntax error: {e}")
    sys.exit(1)

print("🚀 All code checks passed!")
