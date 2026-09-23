"""
Real Desktop GUI Walkthrough and Screenshot Capturer.
Uses Windows GDI PrintWindow (PW_RENDERFULLCONTENT) to capture exact desktop CustomTkinter
window frames directly from the window handle (HWND) into high-resolution PNGs.
"""

import ctypes
from ctypes import wintypes
import os
import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image
import customtkinter as ctk

from ui.app import TamilMP3App
from ui.services.library_service import LibraryService

ARTIFACTS_DIR = Path(r"C:\Users\Praveen\.gemini\antigravity-ide\brain\57609aef-0126-41b3-8788-305a12843a4a")
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ('biSize', wintypes.DWORD),
        ('biWidth', wintypes.LONG),
        ('biHeight', wintypes.LONG),
        ('biPlanes', wintypes.WORD),
        ('biBitCount', wintypes.WORD),
        ('biCompression', wintypes.DWORD),
        ('biSizeImage', wintypes.DWORD),
        ('biXPelsPerMeter', wintypes.LONG),
        ('biYPelsPerMeter', wintypes.LONG),
        ('biClrUsed', wintypes.DWORD),
        ('biClrImportant', wintypes.DWORD),
    ]


def capture_window(app: TamilMP3App, name: str) -> Path:
    app.update_idletasks()
    app.update()
    time.sleep(0.4)

    hwnd = app.winfo_id()
    w = max(1, app.winfo_width())
    h = max(1, app.winfo_height())

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32

    hdc = user32.GetWindowDC(hwnd)
    memdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(memdc, bmp)

    # 2 = PW_RENDERFULLCONTENT
    user32.PrintWindow(hwnd, memdc, 2)

    bmi = BITMAPINFOHEADER()
    bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.biWidth = w
    bmi.biHeight = -h  # top-down DIB
    bmi.biPlanes = 1
    bmi.biBitCount = 32
    bmi.biCompression = 0

    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(memdc, bmp, 0, h, buf, ctypes.byref(bmi), 0)

    img = Image.frombuffer('RGBA', (w, h), buf, 'raw', 'BGRA', 0, 1)
    out_path = ARTIFACTS_DIR / f"audit_{name}.png"
    img.save(str(out_path))

    user32.ReleaseDC(hwnd, hdc)
    gdi32.DeleteDC(memdc)
    gdi32.DeleteObject(bmp)

    print(f"Captured: {out_path} ({w}x{h})")
    return out_path


def main():
    service = LibraryService()
    service.reconcile_library_files()

    app = TamilMP3App(service=service)
    app.geometry("1400x900")
    app.deiconify()
    app.update()
    time.sleep(0.8)

    # 1. Downloaded Songs View (Page 1)
    print("Navigating to Downloaded Songs...")
    app.navigate_to("downloaded_songs")
    app.update()
    time.sleep(0.8)
    capture_window(app, "downloaded_songs_page1")

    # 2. Downloaded Songs View (Page 2)
    dl_view = app.views["downloaded_songs"]
    if dl_view.total_pages > 1:
        print("Navigating to Downloaded Songs Page 2...")
        dl_view._go_page(2)
        app.update()
        time.sleep(0.8)
        capture_window(app, "downloaded_songs_page2")

    # 3. Curated Charts View
    print("Navigating to Charts View...")
    app.navigate_to("charts")
    app.update()
    time.sleep(0.8)
    capture_window(app, "charts_directory")

    # 4. Top 100 Tab Filter
    charts_view = app.views["charts"]
    print("Selecting Top 100 tab...")
    charts_view._on_type_tab_clicked("top_100")
    app.update()
    time.sleep(0.8)
    capture_window(app, "charts_top_100_tab")

    # 5. Open Top 100 Chart Detail (Page 1)
    print("Opening Top 100 Chart Detail...")
    app._open_chart_detail("chart-tamil-top-100")
    app.update()
    time.sleep(0.8)
    capture_window(app, "chart_detail_top_100_page1")

    # Top 100 Page 5 (Ranks 81-100)
    chart_detail = app.views["chart_detail"]
    print("Navigating to Top 100 Page 5...")
    chart_detail._go_page(5)
    app.update()
    time.sleep(0.8)
    capture_window(app, "chart_detail_top_100_page5")

    # 6. Playlists View
    print("Navigating to Playlists View...")
    app.navigate_to("playlists")
    app.update()
    time.sleep(0.8)
    capture_window(app, "playlists_directory")

    # 7. Playlist Detail View (YouTube 50 tracks)
    print("Opening Playlist Detail...")
    app._open_playlist_detail(1)
    app.update()
    time.sleep(0.8)
    capture_window(app, "playlist_detail_youtube_50")

    # 8. Favorites Tab
    print("Navigating to Favorites tab...")
    app.navigate_to("playlists")
    playlists_view = app.views["playlists"]
    playlists_view._set_tab("favorites")
    app.update()
    time.sleep(0.8)
    capture_window(app, "playlists_favorites_tab")

    # 9. Top Rated Tab
    print("Navigating to Top Rated tab...")
    playlists_view._set_tab("rated")
    app.update()
    time.sleep(0.8)
    capture_window(app, "playlists_top_rated_tab")

    # 10. Artists View (A. R. Rahman deduplicated canonical inspection)
    print("Navigating to Artists View...")
    app.navigate_to("artists")
    artists_view = app.views["artists"]
    artists_view.search_entry.delete(0, "end")
    artists_view.search_entry.insert(0, "Rahman")
    artists_view._on_search()
    app.update()
    time.sleep(0.8)
    capture_window(app, "artists_rahman_deduplicated")

    try:
        app.destroy()
    except Exception:
        pass
    print("All real GUI walkthrough screenshots captured successfully!")


if __name__ == "__main__":
    main()
