#!/usr/bin/env python3
"""
Regenerate the tutorial screenshots from a fresh demo database.

Run this any time the console UI changes, or after demo data changes, so the
images in TUTORIAL.html never drift from what the product actually looks like.

    # 1. start the server on a throwaway database
    cd backend && SENTINEL_SECRET=devsecret SENTINEL_DB=/tmp/shots.db \
        uvicorn app.main:app --port 8100 &

    # 2. seed it
    python3 tools/seed_demo.py --base http://127.0.0.1:8100

    # 3. capture
    python3 tools/capture_screenshots.py --base http://127.0.0.1:8100

    # 4. rebuild the guide
    python3 tools/build_tutorial.py

Requires: pip install playwright && playwright install chromium
"""
import argparse
import pathlib
import sys

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "img"

EMAIL = "parent@sentinel.example.com"
PASSWORD = "SentinelDemo2026"

# (filename, what the shot must contain, actions to reach it)
SHOTS = [
    ("01-login", "Sign-in screen", "auth"),
    ("02-family", "Device cards with live status", "family"),
    ("03-add-device", "Enrolment dialog showing the code", "add-device"),
    ("04-device", "One child: map, activity, places, screen time", "device"),
    ("05-add-zone", "Add-a-place dialog", "add-zone"),
    ("06-alerts", "Alert list", "alerts"),
    ("07-audit", "Audit log", "audit"),
    ("08-settings", "Two-factor and family settings", "settings"),
]


def sign_in(page):
    page.goto(f"{BASE}/", wait_until="networkidle")
    page.fill("#li-email", EMAIL)
    page.fill("#li-pass", PASSWORD)
    page.click("#btn-login")
    page.wait_for_selector("#kids .kid", timeout=15000)
    page.wait_for_timeout(800)


def open_child(page, name="Aarav Sharma"):
    # Devices are listed newest-first, so pick by name rather than position.
    page.locator("#kids .kid", has_text=name).first.click()
    page.wait_for_selector("#tl .row, #tl .empty", timeout=15000)
    page.wait_for_timeout(1500)  # let the map SVG paint


def shot(page, name):
    path = OUT / f"{name}.png"
    page.screenshot(path=str(path), full_page=False)
    print(f"  captured {path.name}  ({path.stat().st_size // 1024} KB)")


def main():
    global BASE
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8100")
    args = ap.parse_args()
    BASE = args.base.rstrip("/")

    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1400, "height": 980}, device_scale_factor=1)

        errors = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))

        print("capturing:")
        # 01 — login, before signing in
        page.goto(f"{BASE}/", wait_until="networkidle")
        page.wait_for_timeout(500)
        shot(page, "01-login")

        sign_in(page)
        shot(page, "02-family")

        # 04 — device detail for a seeded child (with a day of real movement)
        open_child(page, "Aarav Sharma")
        shot(page, "04-device")

        # 05 — add-a-place form, opened from the device page
        page.click("#btn-zone")
        page.wait_for_selector("#z-name", state="visible", timeout=8000)
        page.fill("#z-name", "Grandma's")
        page.wait_for_timeout(400)
        shot(page, "05-add-zone")

        # 06 — alerts
        page.click('a[data-page="alerts"]')
        page.wait_for_timeout(900)
        shot(page, "06-alerts")

        # 07 — audit log
        page.click('a[data-page="audit"]')
        page.wait_for_timeout(900)
        shot(page, "07-audit")

        # 08 — settings
        page.click('a[data-page="settings"]')
        page.wait_for_timeout(700)
        shot(page, "08-settings")

        # 03 — enrolment dialog LAST: creating a device mutates the family list,
        # so doing it earlier would leak a pending child into the other shots.
        page.click('a[data-page="home"]')
        page.wait_for_selector("#kids .kid", timeout=10000)
        page.click("#btn-new")
        page.wait_for_timeout(600)
        page.fill("#nd-label", "Aarav's phone")
        page.fill("#nd-owner", "Aarav")
        page.fill("#nd-email", "aarav@example.com")
        page.click("#nd-go")
        page.wait_for_selector("text=Enrollment code", timeout=12000)
        page.wait_for_timeout(700)
        shot(page, "03-add-device")

        browser.close()

    if errors:
        print("\n!! console errors during capture — fix before publishing:", file=sys.stderr)
        for e in errors[:10]:
            print(f"   {e}", file=sys.stderr)
        return 1
    print("\nall 8 captured with a clean console")
    return 0


if __name__ == "__main__":
    sys.exit(main())
