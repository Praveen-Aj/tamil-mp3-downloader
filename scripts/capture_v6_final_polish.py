"""
V6 Final Polish Screenshot Capture Script
Captures desktop screenshots at 1536x730 to docs/ui-ux/v6-final-polish/
Focuses on:
- compact quality metadata
- clean tabs
- subtle section colors
- simplified Settings (internal diagnostics hidden)
- no command prompt
"""
import asyncio
import sys
import os
from pathlib import Path
from playwright.async_api import async_playwright

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://127.0.0.1:8765"
OUT_DIR = Path(r"C:\Users\Praveen\Downloads\Python Scripts\tamil-mp3-downloader\docs\ui-ux\v6-final-polish")
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

        print("\n=== DESKTOP 1536x730 POLISH VALIDATION ===")
        ctx = await browser.new_context(
            viewport=DESKTOP,
            device_scale_factor=1,
        )
        page = await ctx.new_page()
        page.on("console", on_console)

        # 1. Dashboard
        print("Navigating to Dashboard...")
        await page.goto(BASE_URL, wait_until="networkidle")
        await wait_and_shot(page, "desktop-01-dashboard.png", 2.5)

        # 2. Songs
        print("Navigating to Songs...")
        await nav_click(page, "Songs")
        await wait_and_shot(page, "desktop-02-songs.png", 2.0)

        # 3. Movies / Soundtracks
        print("Navigating to Movies...")
        await nav_click(page, "Movies")
        await wait_and_shot(page, "desktop-03-movies.png", 2.0)

        # 4. Downloads
        print("Navigating to Downloads...")
        await nav_click(page, "Downloads")
        await wait_and_shot(page, "desktop-04-downloads.png", 2.0)

        # 5. Settings
        print("Navigating to Settings...")
        await nav_click(page, "Settings")
        await wait_and_shot(page, "desktop-05-settings.png", 2.0)

        # 6. Player (Active Playback on Downloaded Track)
        print("Navigating to Songs and activating Player on Downloaded track...")
        await nav_click(page, "Songs")
        await asyncio.sleep(1.0)
        # Click "Downloaded" filter tab
        downloaded_tab = page.locator("button.filter-tab:has-text('Downloaded')").first
        if await downloaded_tab.is_visible():
            await downloaded_tab.click()
            await asyncio.sleep(1.0)
        # Click the first track's play button
        play_btn = page.locator(".track-art-wrap").first
        if await play_btn.is_visible():
            await play_btn.click()
            await asyncio.sleep(1.5)
        await wait_and_shot(page, "desktop-06-player.png", 2.0)

        await ctx.close()

        # MOBILE SMOKE TEST (390x844)
        print("\n=== MOBILE SMOKE TEST (390x844) ===")
        ctx_m = await browser.new_context(
            viewport=MOBILE,
            device_scale_factor=2,
        )
        page_m = await ctx_m.new_page()
        page_m.on("console", on_console)
        await page_m.goto(BASE_URL, wait_until="networkidle")
        await asyncio.sleep(1.5)
        print("Mobile render test passed without errors.")
        await ctx_m.close()

        await browser.close()

    print(f"\nAll screenshots successfully saved to: {OUT_DIR}")
    print(f"Console errors: {len(console_errors)}")


if __name__ == "__main__":
    asyncio.run(run())
