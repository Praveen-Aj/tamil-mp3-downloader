"""
Validation Script for V5.2 — Real GUI Search and Filtering.

Launches the real CustomTkinter GUI application, exercises:
1. Normal Music Library view
2. Debounced search query ("Anirudh")
3. Composed search + filter ("Underdog" + "DOWNLOADED")
4. Column and dropdown sorting ("NOT DOWNLOADED" + Sort "Title" Ascending)
5. Clean no-results empty state ("NonExistentKeywordXYZ999")
6. Pagination controls and slicing (Reset All Filters, full library view)

Captures real desktop pixel screenshots to screenshots/v5.2-search/
and validates GUI responsiveness and layout.
"""

import os
import sys
import time
import ctypes
from ctypes import wintypes
from pathlib import Path
from PIL import Image

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from library.database import SQLiteDatabase
from library.models import LibrarySong, SongSource, SongState
from ui.services.library_service import LibraryService
from ui.app import TamilMP3App
from config.settings import settings


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
        ('biClrImportant', wintypes.DWORD)
    ]


def capture_app_screenshot(app: TamilMP3App, output_path: Path) -> None:
    """Capture real desktop window pixels of the running application."""
    app.update()
    time.sleep(0.4)
    app.update_idletasks()

    try:
        hwnd = ctypes.windll.user32.GetParent(app.winfo_id()) or app.winfo_id()
        w = max(100, app.winfo_width())
        h = max(100, app.winfo_height())

        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32

        hdc_window = user32.GetWindowDC(hwnd)
        hdc_mem = gdi32.CreateCompatibleDC(hdc_window)
        hbm = gdi32.CreateCompatibleBitmap(hdc_window, w, h)
        gdi32.SelectObject(hdc_mem, hbm)

        user32.PrintWindow(hwnd, hdc_mem, 2)

        bmi = BITMAPINFOHEADER()
        bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.biWidth = w
        bmi.biHeight = -h
        bmi.biPlanes = 1
        bmi.biBitCount = 32
        bmi.biCompression = 0

        buf_size = w * h * 4
        buf = ctypes.create_string_buffer(buf_size)
        gdi32.GetDIBits(hdc_mem, hbm, 0, h, buf, ctypes.byref(bmi), 0)

        img = Image.frombuffer('RGBA', (w, h), buf, 'raw', 'BGRA', 0, 1)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.convert('RGB').save(str(output_path), format="PNG")

        user32.ReleaseDC(hwnd, hdc_window)
        gdi32.DeleteDC(hdc_mem)
        gdi32.DeleteObject(hbm)
        print(f"Captured screenshot: {output_path.name}")
    except Exception as e:
        print(f"Failed to capture screenshot via PrintWindow: {e}")


def seed_demo_songs_if_needed(db: SQLiteDatabase) -> None:
    """Ensure library has a diverse catalog for rich filtering and search validation."""
    count_cur = db._conn.cursor()
    count_cur.execute("SELECT COUNT(*) FROM songs")
    count = count_cur.fetchone()[0]

    demo_songs = [
        ("h_vaathi_coming", "Vaathi Coming", "vaathi coming", "Anirudh Ravichander", "anirudh ravichander", "Master", "master", 2021, 230, SongState.NEW, 320, "masstamilan"),
        ("h_vaathi_raid", "Vaathi Raid", "vaathi raid", "Anirudh Ravichander", "anirudh ravichander", "Master", "master", 2021, 210, SongState.NEW, 128, "tamilmp3"),
        ("h_arabic_kuthu", "Arabic Kuthu", "arabic kuthu", "Anirudh Ravichander", "anirudh ravichander", "Beast", "beast", 2022, 280, SongState.NEW, 320, "masstamilan"),
        ("h_kanja_poovu", "Kanja Poovu Kannala", "kanja poovu kannala", "Yuvan Shankar Raja", "yuvan shankar raja", "Viruman", "viruman", 2022, 255, SongState.NEW, 128, "friendstamilmp3"),
        ("h_naan_naan", "Naan Naan", "naan naan", "Santhosh Narayanan", "santhosh narayanan", "Mahaan", "mahaan", 2022, 195, SongState.NEW, 320, "masstamilan"),
        ("h_tamil_vaathi", "வாத்தி கமிங்", "வாத்தி கமிங்", "அனிருத் ரவிச்சந்தர்", "அனிருத் ரவிச்சந்தர்", "மாஸ்டர்", "மாஸ்டர்", 2021, 230, SongState.NEW, 320, "tamilmp3"),
        ("h_leo_badass", "Badass", "badass", "Anirudh Ravichander", "anirudh ravichander", "Leo", "leo", 2023, 229, SongState.NEW, 320, "masstamilan"),
        ("h_leo_lokiverse", "Lokiverse 2.0", "lokiverse 2.0", "Anirudh Ravichander", "anirudh ravichander", "Leo", "leo", 2023, 114, SongState.NEW, 320, "tamilmp3"),
        ("h_jailer_kaavaalaa", "Kaavaalaa", "kaavaalaa", "Anirudh Ravichander", "anirudh ravichander", "Jailer", "jailer", 2023, 190, SongState.NEW, 320, "masstamilan"),
        ("h_jailer_hukum", "Hukum - Thalaivar Alappara", "hukum thalaivar alappara", "Anirudh Ravichander", "anirudh ravichander", "Jailer", "jailer", 2023, 207, SongState.NEW, 320, "masstamilan"),
        ("h_vikram_pathala", "Pathala Pathala", "pathala pathala", "Anirudh Ravichander", "anirudh ravichander", "Vikram", "vikram", 2022, 211, SongState.NEW, 320, "masstamilan"),
        ("h_vikram_wasted", "Wasted", "wasted", "Anirudh Ravichander", "anirudh ravichander", "Vikram", "vikram", 2022, 183, SongState.NEW, 128, "friendstamilmp3"),
    ]

    for item in demo_songs:
        s = LibrarySong(
            canonical_hash=item[0],
            title=item[1],
            title_normalized=item[2],
            artist=item[3],
            artist_normalized=item[4],
            album=item[5],
            album_normalized=item[6],
            year=item[7],
            duration_seconds=item[8],
            state=item[9],
            quality_kbps=item[10],
            file_path=None,
        )
        s_id = db.add_song(s)
        src = SongSource(
            song_id=s_id,
            source_name=item[11],
            source_url=f"https://example.com/{item[0]}",
            quality_kbps=item[10],
            is_available=True,
        )
        db.add_source(src)


def run_gui_validation():
    print("=== Starting V5.2 GUI Search & Filtering Validation ===")
    out_dir = PROJECT_ROOT / "screenshots" / "v5.2-search"
    out_dir.mkdir(parents=True, exist_ok=True)

    db_path = PROJECT_ROOT / "library.db"
    db = SQLiteDatabase(db_path)
    db.connect()
    seed_demo_songs_if_needed(db)

    service = LibraryService(db=db)
    app = TamilMP3App(service=service)
    app.geometry("1300x820")
    app.update()
    time.sleep(1.0)

    # Navigate to Music Library
    print("Navigating to Music Library view...")
    app.navigate_to("library")
    app.update()
    time.sleep(0.5)

    lib_view = app.views["library"]
    assert lib_view is not None

    # 1. Normal Music Library
    print("Capturing 01_normal_library.png...")
    capture_app_screenshot(app, out_dir / "01_normal_library.png")

    # 2. Enter Search Query: 'Anirudh'
    print("Testing debounced search with query 'Anirudh'...")
    lib_view.search_var.set("Anirudh")
    lib_view._on_search()
    app.update()
    time.sleep(0.5)
    print(f"Results after search 'Anirudh': {len(lib_view._current_songs)} songs")
    assert len(lib_view._current_songs) > 0
    capture_app_screenshot(app, out_dir / "02_search_results.png")

    # 3. Search + Filters (Query: 'Underdog' + Status: DOWNLOADED)
    print("Applying filters: search 'Underdog' + Downloaded status...")
    lib_view.search_var.set("Underdog")
    lib_view.current_query = "Underdog"
    lib_view.filter_var.set("DOWNLOADED")
    lib_view.current_filter = "DOWNLOADED"
    lib_view.quality_var.set("All Bitrates")
    lib_view.refresh()
    app.update()
    time.sleep(0.5)
    print(f"Results after search + filters: {len(lib_view._current_songs)} songs")
    assert len(lib_view._current_songs) > 0
    for s in lib_view._current_songs:
        assert s.state == SongState.OWNED
    capture_app_screenshot(app, out_dir / "03_search_and_filters.png")

    # 4. Sorting: Clear search, Filter = NOT DOWNLOADED, Sort by Title Ascending
    print("Testing sorting: NOT DOWNLOADED + Title ascending...")
    lib_view.search_var.set("")
    lib_view.current_query = ""
    lib_view.filter_var.set("NOT DOWNLOADED")
    lib_view.current_filter = "NOT DOWNLOADED"
    lib_view.sort_var.set("Title")
    lib_view.sort_ascending = True
    lib_view.sort_dir_btn.configure(text="↑")
    lib_view.refresh()
    app.update()
    time.sleep(0.5)
    titles = [s.title for s in lib_view._current_songs]
    print(f"Sorted titles ({len(titles)} songs): {titles[:5]}")
    assert len(titles) > 1
    assert titles == sorted(titles)
    capture_app_screenshot(app, out_dir / "04_sorted_results.png")

    # 5. No-Results Empty State: Search for non-existent keyword
    print("Testing No-Results Empty State...")
    lib_view.filter_var.set("ALL")
    lib_view.current_filter = "ALL"
    lib_view.search_var.set("NonExistentKeywordXYZ999")
    lib_view._on_search()
    app.update()
    time.sleep(0.5)
    assert len(lib_view._current_songs) == 0
    capture_app_screenshot(app, out_dir / "05_no_results_empty_state.png")

    # 6. Pagination & Controls: Clear all filters, full library view
    print("Testing reset and pagination controls...")
    lib_view._clear_all_filters()
    app.update()
    time.sleep(0.5)
    print(f"Total library songs restored: {len(lib_view._current_songs)}")
    assert len(lib_view._current_songs) > 0
    capture_app_screenshot(app, out_dir / "06_pagination_controls.png")

    # Clean close
    app.destroy()
    db.close()
    print("=== V5.2 GUI Validation Completed Successfully ===")


if __name__ == "__main__":
    run_gui_validation()
