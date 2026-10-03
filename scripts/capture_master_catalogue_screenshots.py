import os
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

def main():
    repo_root = Path(__file__).resolve().parent.parent
    screenshots_dir = repo_root / "docs" / "audits" / "master-catalogue" / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    app_brain_dir = Path(r"C:\Users\Praveen\.gemini\antigravity-ide\brain\50738ddb-de2f-4134-bbd1-98dfc528cfa5")
    app_brain_dir.mkdir(parents=True, exist_ok=True)

    print(f"Screenshots destination: {screenshots_dir}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1536, "height": 730})
        page = context.new_page()

        # 1. Dashboard View
        print("Navigating to Dashboard...")
        page.goto("http://127.0.0.1:8765/", wait_until="networkidle")
        time.sleep(2.5)
        p1 = screenshots_dir / "desktop-01-dashboard.png"
        page.screenshot(path=str(p1))
        page.screenshot(path=str(app_brain_dir / "desktop-01-dashboard.png"))
        print(f"Captured: {p1}")

        # 2. Songs View
        print("Clicking Songs Nav...")
        page.click("button:has-text('Songs')")
        time.sleep(2.5)
        p2 = screenshots_dir / "desktop-02-songs.png"
        page.screenshot(path=str(p2))
        page.screenshot(path=str(app_brain_dir / "desktop-02-songs.png"))
        print(f"Captured: {p2}")

        # 3. Movies View
        print("Clicking Movies Nav...")
        page.click("button:has-text('Movies')")
        time.sleep(2.5)
        p3 = screenshots_dir / "desktop-03-movies.png"
        page.screenshot(path=str(p3))
        page.screenshot(path=str(app_brain_dir / "desktop-03-movies.png"))
        print(f"Captured: {p3}")

        # 4. Movie Detail View - Beast (2022) or first movie card
        print("Searching Beast in movies view...")
        search_input = page.locator("input[placeholder*='Search movies'], input[placeholder*='search']").first
        if search_input.count() > 0:
            search_input.fill("Beast")
            time.sleep(1.5)
        page.click("text='Beast'")
        time.sleep(2.5)
        p4 = screenshots_dir / "desktop-04-movie-detail.png"
        page.screenshot(path=str(p4))
        page.screenshot(path=str(app_brain_dir / "desktop-04-movie-detail.png"))
        print(f"Captured: {p4}")

        # 5. Artists View
        print("Clicking Artists Nav...")
        page.click("button:has-text('Artists')")
        time.sleep(2.5)
        p5 = screenshots_dir / "desktop-05-artists.png"
        page.screenshot(path=str(p5))
        page.screenshot(path=str(app_brain_dir / "desktop-05-artists.png"))
        print(f"Captured: {p5}")

        # 6. Charts View
        print("Clicking Top Charts Nav...")
        page.click("button:has-text('Top Charts')")
        time.sleep(2.5)
        # Select Evergreen Classics tab if present to verify 50 entries
        classics_tab = page.locator("text='Evergreen'").first
        if classics_tab.count() > 0:
            classics_tab.click()
            time.sleep(1.5)
        p6 = screenshots_dir / "desktop-06-charts.png"
        page.screenshot(path=str(p6))
        page.screenshot(path=str(app_brain_dir / "desktop-06-charts.png"))
        print(f"Captured: {p6}")

        browser.close()
        print("All 6 affected page screenshots captured successfully!")

if __name__ == "__main__":
    main()
