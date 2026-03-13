#!/usr/bin/env python3
"""Refresh X session cookie by opening a browser for manual login.

Run this script locally (NOT on the server), log in to X manually,
then copy the session file to the server.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


async def main():
    from scraper.scraper import TwitterScraper

    session_dir = Path(__file__).parent.parent / "data" / "session"
    session_dir.mkdir(parents=True, exist_ok=True)
    session_file = session_dir / "storage_state.json"

    print("=" * 60)
    print("  HFI - X Session Refresh Tool")
    print("=" * 60)
    print()
    print("This will open a browser window.")
    print("Log in to X (twitter.com) manually.")
    print()

    scraper = TwitterScraper(headless=False)
    try:
        await scraper._init_browser(use_session=False)
        await scraper.page.goto("https://x.com/login", timeout=30000)

        print("Waiting for you to log in...")
        print()
        input("Press ENTER after you've logged in successfully: ")

        try:
            await scraper.page.wait_for_selector('[data-testid="primaryColumn"]', timeout=10000)
            print("Login verified!")
        except Exception:
            print("Could not verify login. Saving session anyway...")

        await scraper.context.storage_state(path=str(session_file))
        print()
        print(f"Session saved to: {session_file}")
        print()
        print("To deploy to your server, run:")
        print(f"  scp {session_file} <user>@<server>:~/HFI/data/session/storage_state.json")
        print()
    finally:
        await scraper.close()


if __name__ == "__main__":
    asyncio.run(main())
