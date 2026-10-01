"""
Final Validation Screenshot Capture & Smoke Test Script
Tamil MP3 Downloader V6
Captures authoritative desktop screenshots at 1536x730 and conducts mobile smoke test at 390x844.
"""
import asyncio
import sys
import os
from pathlib import Path
from playwright.async_api import async_playwright

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://127.0.0.1:8765"
OUT_DIR = Path(r"C:\Users\Praveen\Downloads\Python Scripts\tamil-mp3-downloader\docs\ui-ux\v6-final-validation")
OUT_DIR.mkdir(parents=True, exist_ok=True)

DESKTOP = {"width": 1536, "height": 730}
MOBILE = {"width": 390, "height": 844}


async def wait_and_shot(page, filename: str, delay: float = 2.0):
    await asyncio.sleep(delay)
    path = str(OUT_DIR / filename)
    await page.screenshot(path=path, full_page=False)
    print(f"  [SCREENSHOT SAVED] {filename}")


async def nav_click(page, label: str):
    """Click a sidebar nav item by visible text."""
    locator = page.locator(f"aside button:has-text('{label}'), aside a:has-text('{label}')")
    count = await locator.count()
    if count > 0:
        await locator.first.click()
    else:
        await page.get_by_text(label, exact=True).first.click()


async def run():
    console_errors = []

    def on_console(msg):
        if msg.type == "error":
            console_errors.append(msg.text)
            print(f"  [CONSOLE ERROR] {msg.text}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        # ==============================================================
        # DESKTOP VALIDATION (1536x730)
        # ==============================================================
        print("\n=== DESKTOP 1536x730 VALIDATION ===")
        ctx = await browser.new_context(
            viewport=DESKTOP,
            device_scale_factor=1,
        )
        page = await ctx.new_page()
        page.on("console", on_console)

        # 1. Dashboard (Clean state)
        print("Navigating to Dashboard...")
        await page.goto(BASE_URL, wait_until="networkidle")
        await wait_and_shot(page, "desktop-01-dashboard.png", 2.5)

        # 2. Songs (Clean state)
        print("Navigating to Songs...")
        await nav_click(page, "Songs")
        await wait_and_shot(page, "desktop-02-songs.png", 2.0)

        # 3. Movies (Clean state)
        print("Navigating to Movies...")
        await nav_click(page, "Movies")
        await wait_and_shot(page, "desktop-03-movies.png", 2.0)

        # 4. Artists (Clean state)
        print("Navigating to Artists...")
        await nav_click(page, "Artists")
        await wait_and_shot(page, "desktop-04-artists.png", 2.0)

        # 5. Search (Dedicated Search Demonstration: "AR Rahman")
        print("Performing Search for 'AR Rahman'...")
        search_input = page.locator("input[aria-label='Global search input'], input[placeholder*='Search']")
        await search_input.first.fill("AR Rahman")
        await asyncio.sleep(1.0)
        await search_input.first.press("Enter")
        await wait_and_shot(page, "desktop-05-search.png", 2.5)

        # 6. Downloads (Clean state - search input must be isolated/cleared)
        print("Navigating to Downloads...")
        await nav_click(page, "Downloads")
        await wait_and_shot(page, "desktop-06-downloads.png", 2.0)

        # 7. Settings (Clean state - verifying download directory)
        print("Navigating to Settings...")
        await nav_click(page, "Settings")
        await wait_and_shot(page, "desktop-07-settings.png", 2.0)

        # 8. Player (Active playback state)
        print("Activating Player on Songs page...")
        await nav_click(page, "Songs")
        await asyncio.sleep(1.0)
        await page.evaluate("""() => {
            if (window.__SET_PLAYER_STATE__) {
                window.__SET_PLAYER_STATE__({
                    id: 3,
                    title: "Anbil Avan - Title Theme",
                    artist: "A.R. Rahman",
                    album: "Vinnaithaandi Varuvaayaa",
                    quality: "160 kbps",
                    has_file: true,
                    is_favorite: true
                }, true, 42, 198);
            }
        }""")
        await wait_and_shot(page, "desktop-08-player.png", 2.0)

        await ctx.close()

        # ==============================================================
        # MOBILE SMOKE TEST ONLY (390x844)
        # ==============================================================
        print("\n=== MOBILE 390x844 SMOKE TEST ===")
        ctx_m = await browser.new_context(
            viewport=MOBILE,
            device_scale_factor=2,
            user_agent=(
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
            ),
        )
        page_m = await ctx_m.new_page()
        page_m.on("console", on_console)

        # 1. Mobile Dashboard Render
        print("Checking mobile Dashboard render...")
        await page_m.goto(BASE_URL, wait_until="networkidle")
        await asyncio.sleep(1.5)
        print("Mobile render successful, no crashes.")

        # 2. Open Hamburger menu
        menu_button = page_m.locator("button[aria-label='Open menu'], header button").first
        if await menu_button.is_visible():
            print("Opening mobile navigation drawer...")
            await menu_button.click()
            await asyncio.sleep(0.5)
            # Click Songs in the drawer
            songs_nav = page_m.locator("aside button:has-text('Songs')")
            if await songs_nav.is_visible():
                await songs_nav.click()
                await asyncio.sleep(1.0)
                print("Navigated to Songs via mobile drawer.")

        # 3. Player bar check
        print("Testing player rendering on mobile...")
        await page_m.evaluate("""() => {
            if (window.__SET_PLAYER_STATE__) {
                window.__SET_PLAYER_STATE__({
                    id: 3,
                    title: "Anbil Avan",
                    artist: "A.R. Rahman",
                    album: "VTV",
                    quality: "160 kbps",
                    has_file: true,
                    is_favorite: false
                }, true, 15, 198);
            }
        }""")
        await asyncio.sleep(1.0)

        # Check player element visibility
        player = page_m.locator(".player-bar, footer").first
        player_visible = await player.is_visible()
        print(f"Mobile player visibility check: {player_visible}")

        await ctx_m.close()
        await browser.close()

    print(f"\nCaptured all desktop validation screenshots into: {OUT_DIR}")
    print(f"Console errors during run: {len(console_errors)}")
    if console_errors:
        for err in console_errors[:5]:
            print(f"  - {err}")


if __name__ == "__main__":
    asyncio.run(run())
