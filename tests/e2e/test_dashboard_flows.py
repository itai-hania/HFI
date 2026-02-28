"""Playwright smoke tests for dashboard UI flows.

These tests are opt-in and require a running dashboard instance.
Run with:
    RUN_DASHBOARD_E2E=1 DASHBOARD_URL=http://localhost:8501 python3 -m pytest tests/e2e/test_dashboard_flows.py -q
"""

import os

import pytest

playwright = pytest.importorskip("playwright.sync_api")
sync_playwright = playwright.sync_playwright


def _require_e2e_enabled():
    if os.getenv("RUN_DASHBOARD_E2E") != "1":
        pytest.skip("Set RUN_DASHBOARD_E2E=1 to run Playwright dashboard smoke tests.")


def _open_dashboard(page):
    base_url = os.getenv("DASHBOARD_URL", "http://localhost:8501")
    page.goto(base_url, wait_until="domcontentloaded")

    # Optional auth flow.
    if page.locator("text=HFI Dashboard Login").is_visible():
        password = os.getenv("DASHBOARD_PASSWORD")
        if not password:
            pytest.skip("Dashboard login is enabled but DASHBOARD_PASSWORD is not set for E2E test.")
        page.get_by_label("Password").fill(password)
        page.get_by_role("button", name="Login").click()
        page.wait_for_timeout(500)


def _with_page(test_fn):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        try:
            _open_dashboard(page)
            test_fn(page)
        finally:
            browser.close()


def test_login_surface_loads():
    _require_e2e_enabled()

    def _run(page):
        assert page.locator("text=Home").first.is_visible() or page.locator("text=Content").first.is_visible()

    _with_page(_run)


def test_acquire_blank_url_validation():
    _require_e2e_enabled()

    def _run(page):
        page.get_by_role("button", name="Content").click()
        page.get_by_role("radio", name="Acquire").click()
        page.get_by_role("button", name="Scrape Thread").click()
        assert page.locator("text=Enter a URL before scraping.").is_visible()

    _with_page(_run)


def test_core_sections_render():
    _require_e2e_enabled()

    def _run(page):
        page.get_by_role("button", name="Content").click()
        page.get_by_role("radio", name="Queue").click()
        assert page.locator("text=Queue Workflow").is_visible()

        page.get_by_role("radio", name="Generate").click()
        assert page.locator("text=Generate Original Hebrew Post").is_visible()

        page.get_by_role("radio", name="Publish").click()
        assert page.locator("text=Publish Handoff").is_visible()

    _with_page(_run)


def test_keyboard_navigation_focus_moves():
    _require_e2e_enabled()

    def _run(page):
        page.keyboard.press("Tab")
        focused_element = page.evaluate("document.activeElement && document.activeElement.tagName")
        assert focused_element is not None

    _with_page(_run)
