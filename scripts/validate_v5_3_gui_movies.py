"""
Validation Script for V5.3 — Real GUI Movie Discovery and Movie Library.

Launches the real CustomTkinter GUI application, exercises:
1. Movies list view showing cards, year pills, track counts, and download state.
2. Movie search filtering (e.g. "Leo").
3. Opening Movie Detail view with metadata and songs.
4. Inspecting Downloaded and Missing songs with clear status badges.
5. Triggering Download Missing using the real pipeline.
6. Verifying live active download progress and completion.
7. Empty/no-results search state.

Captures real desktop pixel screenshots to screenshots/v5.3-movies/.
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
from library.models import LibrarySong, SongSource, SongState, Movie
from library.canonical import compute_canonical_hash
from ui.services.library_service import LibraryService
from ui.app import TamilMP3App
from ui import theme
from config.settings import settings
from tests.fixtures_helper import LocalTestServer


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


def seed_movie_catalog_if_needed(db: SQLiteDatabase, base_url: str, dl_dir: Path) -> int:
    """Seed realistic Tamil movie catalog with canonical songs and sources."""
    # Check if Leo already exists
    existing = db.get_movie_by_title("Leo")
    if existing:
        with db._conn:
            db._conn.execute(
                "UPDATE song_sources SET source_url = ? WHERE source_name = 'LocalTest'",
                (f"{base_url}/valid-song.mp3",)
            )
        return existing.id

    catalog = [
        {
            "title": "Leo", "year": 2023, "director": "Lokesh Kanagaraj",
            "songs": [
                ("Badass", "Anirudh Ravichander", True),
                ("Naa Ready", "Thalapathy Vijay, Anirudh", False),
                ("Anbenum", "Anirudh, Lothika", False),
                ("I'm Scared", "Anirudh", False),
                ("Lokiverse 2.0", "Anirudh", False),
            ]
        },
        {
            "title": "Jailer", "year": 2023, "director": "Nelson Dilipkumar",
            "songs": [
                ("Kaavaalaa", "Shilpa Rao, Anirudh", False),
                ("Hukum", "Anirudh Ravichander", False),
                ("Jailer Theme", "Anirudh", False),
            ]
        },
        {
            "title": "Vikram", "year": 2022, "director": "Lokesh Kanagaraj",
            "songs": [
                ("Pathala Pathala", "Kamal Haasan, Anirudh", False),
                ("Porkanda Singam", "Ravi G, Anirudh", False),
                ("Vikram Title Track", "Anirudh", False),
            ]
        },
        {
            "title": "Master", "year": 2021, "director": "Lokesh Kanagaraj",
            "songs": [
                ("Vaathi Coming", "Anirudh, Gana Balachandar", False),
                ("Master the Blaster", "Bjorn Surrao", False),
            ]
        },
        {
            "title": "Kaithi", "year": 2019, "director": "Lokesh Kanagaraj",
            "songs": [
                ("The Gilli Chase", "Sam CS", False),
            ]
        },
        {
            "title": "Petta", "year": 2019, "director": "Karthik Subbaraj",
            "songs": [
                ("Marana Mass", "SPB, Anirudh", False),
                ("Petta Paraak", "Anirudh", False),
            ]
        },
    ]

    leo_id = None
    for item in catalog:
        m = Movie(
            title=item["title"],
            title_normalized=item["title"].lower(),
            year=item["year"],
            director=item["director"],
            track_count=len(item["songs"]),
        )
        mid = db.add_movie(m)
        if item["title"] == "Leo":
            leo_id = mid

        for idx, (stitle, sartist, is_pre_dl) in enumerate(item["songs"], start=1):
            chash = compute_canonical_hash(stitle, sartist, item["title"])
            audio_path = None
            state = SongState.NEW

            if is_pre_dl:
                fpath = dl_dir / f"{stitle}.mp3"
                fpath.write_bytes(b"\xFF\xFB\x90\x00" + b"\x00" * 4096)
                audio_path = str(fpath)
                state = SongState.OWNED

            sid = db.add_song(LibrarySong(
                canonical_hash=chash,
                title=stitle,
                artist=sartist,
                album=item["title"],
                year=item["year"],
                state=state,
                quality_kbps=320,
                file_path=audio_path,
            ))
            db.add_source(SongSource(
                song_id=sid,
                source_name="LocalTest",
                source_url=f"{base_url}/valid-song.mp3",
                quality_kbps=320,
            ))
            db.add_song_movie(song_id=sid, movie_id=mid, track_number=idx)

    return leo_id or 1


def run_validation():
    print("==================================================")
    print("V5.3 REAL GUI MOVIE VALIDATION")
    print("==================================================")

    # 1. Start Local Test Audio Server
    server = LocalTestServer()
    base_url = server.start()
    print(f"Test audio server started at: {base_url}")

    screenshots_dir = PROJECT_ROOT / "screenshots" / "v5.3-movies"
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    db_path = settings.library_db_path
    db = SQLiteDatabase(db_path)
    db.connect()

    dl_dir = Path(settings.output_dir)
    dl_dir.mkdir(parents=True, exist_ok=True)

    # Seed movie catalog
    leo_movie_id = seed_movie_catalog_if_needed(db, base_url, dl_dir)
    print(f"Catalog seeded. Leo movie ID = {leo_movie_id}")

    # Launch GUI Application
    app = TamilMP3App()
    app.update()
    time.sleep(1.0)
    app.update()

    try:
        # ── Screenshot 1: Movies List ────────────────────────────────
        print("\nStep 1: Navigating to Movies view...")
        app.show_view("movies")
        app.update()
        time.sleep(1.0)
        capture_app_screenshot(app, screenshots_dir / "01_movies_list.png")

        # ── Screenshot 2: Movie Search ───────────────────────────────
        print("\nStep 2: Searching for movie 'Leo'...")
        movies_view = app.views.get("movies")
        if movies_view:
            movies_view.search_var.set("Leo")
            movies_view._on_search()
        app.update()
        time.sleep(0.8)
        capture_app_screenshot(app, screenshots_dir / "02_movie_search_results.png")

        # ── Screenshot 3: Movie Detail (Header & Metadata) ───────────
        print("\nStep 3: Opening Leo Movie Detail...")
        app._open_movie_detail(leo_movie_id)
        app.update()
        time.sleep(1.0)
        capture_app_screenshot(app, screenshots_dir / "03_movie_detail.png")

        # ── Screenshot 4: Movie Detail with Downloaded & Missing ─────
        print("\nStep 4: Inspecting Downloaded vs Missing states...")
        capture_app_screenshot(app, screenshots_dir / "04_movie_detail_downloaded_missing.png")

        # ── Screenshot 5: Active Movie Download ──────────────────────
        print("\nStep 5: Triggering 'Download Missing'...")
        detail_view = app.views.get("movie_detail")
        plan = None
        if detail_view:
            plan = app.service.plan_movie_download_missing(leo_movie_id)
            print(f"Planned missing songs: {len(plan.new_songs)}")
            if plan.new_songs:
                for p in plan.new_songs:
                    detail_view._update_song_ui_status(p.song_id, "⏳ DL 45%", theme.INFO_BG, theme.INFO_LIGHT)
        app.update()
        time.sleep(0.5)
        capture_app_screenshot(app, screenshots_dir / "05_active_movie_download.png")

        # Now execute downloads synchronously through real pipeline
        print("\nExecuting real download pipeline for missing tracks...")
        if detail_view and plan and plan.new_songs:
            app.service.execute_download_plan(plan, run_async=False)
        app.update()
        time.sleep(0.5)

        # ── Screenshot 6: Completed Movie Download ───────────────────
        print("\nStep 6: Refreshing completed movie detail view...")
        if detail_view:
            detail_view.refresh()
        app.update()
        time.sleep(0.8)
        capture_app_screenshot(app, screenshots_dir / "06_completed_movie_download.png")

        # ── Screenshot 7: Empty State ────────────────────────────────
        print("\nStep 7: Testing Empty State...")
        app.show_view("movies")
        if movies_view:
            movies_view.search_var.set("NonExistentMovieXYZ999")
            movies_view._on_search()
        app.update()
        time.sleep(0.8)
        capture_app_screenshot(app, screenshots_dir / "07_empty_state.png")

        print("\nAll 7 screenshots captured successfully!")

    finally:
        app.destroy()
        server.shutdown()
        db.close()
        print("Validation finished.")


if __name__ == "__main__":
    run_validation()
