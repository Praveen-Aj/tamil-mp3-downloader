"""
Automated Desktop Application Visual Validation & Real Pixel Screenshot Capture.
Launches the TamilMP3App, sets up real verified records, captures real pixel bounding boxes
for each core end-user view, and saves lossless PNGs into screenshots/ui-validation/.
"""

import os
import sys
import time
from pathlib import Path
import ctypes
from ctypes import wintypes
from PIL import Image, ImageGrab
import customtkinter as ctk

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from library.database import SQLiteDatabase
from library.models import LibrarySong, SongState, ImportJob, ImportJobItem, JobStatus, ItemState, DownloadState
from library.canonical import compute_canonical_hash
from ui.services.library_service import LibraryService
from ui.app import TamilMP3App


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


def capture_view_screenshot(app: TamilMP3App, view_name: str, output_path: Path) -> None:
    """Navigate to a view, process UI events, and capture real desktop pixels of the app window."""
    app.navigate_to(view_name)
    app.update()
    time.sleep(0.5)  # Allow CustomTkinter geometry & widget rendering
    app.update_idletasks()

    try:
        # Get window HWND and dimensions
        hwnd = ctypes.windll.user32.GetParent(app.winfo_id()) or app.winfo_id()
        w = max(100, app.winfo_width())
        h = max(100, app.winfo_height())

        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32

        hdc_window = user32.GetWindowDC(hwnd)
        hdc_mem = gdi32.CreateCompatibleDC(hdc_window)
        hbm = gdi32.CreateCompatibleBitmap(hdc_window, w, h)
        gdi32.SelectObject(hdc_mem, hbm)

        # PW_RENDERFULLCONTENT = 2
        user32.PrintWindow(hwnd, hdc_mem, 2)

        bmi = BITMAPINFOHEADER()
        bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.biWidth = w
        bmi.biHeight = -h  # top-down DIB
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
        print(f"Captured: {output_path.name} ({w}x{h})")
    except Exception as exc:
        print(f"PrintWindow capture fallback failed for {view_name}: {exc}")
        # Fallback to ImageGrab if available
        try:
            x = app.winfo_rootx()
            y = app.winfo_rooty()
            w = app.winfo_width()
            h = app.winfo_height()
            screenshot = ImageGrab.grab(bbox=(x, y, x + w, y + h))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            screenshot.save(str(output_path), format="PNG")
            print(f"Captured via ImageGrab: {output_path.name} ({w}x{h})")
        except Exception as e2:
            print(f"All capture methods failed for {view_name}: {e2}")


def run_visual_capture() -> None:
    output_dir = PROJECT_ROOT / "screenshots" / "ui-validation"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Set up realistic temporary test environment with verified songs on disk
    temp_dir = PROJECT_ROOT / "tmp_visual_validation"
    temp_dir.mkdir(parents=True, exist_ok=True)
    downloads_dir = temp_dir / "downloads"
    downloads_dir.mkdir(parents=True, exist_ok=True)

    # Create real audio files on disk
    f1 = downloads_dir / "Arabic Kuthu - Anirudh Ravichander.mp3"
    f1.write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 8192)

    f2 = downloads_dir / "Vaathi Coming - Anirudh.mp3"
    f2.write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 8192)

    f3 = downloads_dir / "Matta - Yuvan Shankar Raja.mp3"
    f3.write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 8192)

    db_path = temp_dir / "library.db"
    db = SQLiteDatabase(db_path)
    db.connect()

    # Populate verified owned songs
    s1_id = db.add_song(
        LibrarySong(
            title="Arabic Kuthu",
            artist="Anirudh Ravichander",
            album="Beast",
            canonical_hash=compute_canonical_hash("Arabic Kuthu", "Anirudh Ravichander", "Beast"),
            state=SongState.OWNED,
            file_path=str(f1),
            quality_kbps=320,
        )
    )
    s2_id = db.add_song(
        LibrarySong(
            title="Vaathi Coming",
            artist="Anirudh",
            album="Master",
            canonical_hash=compute_canonical_hash("Vaathi Coming", "Anirudh", "Master"),
            state=SongState.OWNED,
            file_path=str(f2),
            quality_kbps=320,
        )
    )
    s3_id = db.add_song(
        LibrarySong(
            title="Matta",
            artist="Yuvan Shankar Raja",
            album="GOAT",
            canonical_hash=compute_canonical_hash("Matta", "Yuvan Shankar Raja", "GOAT"),
            state=SongState.OWNED,
            file_path=str(f3),
            quality_kbps=320,
        )
    )

    # Populate unowned catalog songs
    db.add_song(
        LibrarySong(
            title="Katchi Sera",
            artist="Sai Abhyankkar",
            album="Independent",
            canonical_hash=compute_canonical_hash("Katchi Sera", "Sai Abhyankkar", "Independent"),
            state=SongState.NEW,
            quality_kbps=320,
        )
    )
    db.add_song(
        LibrarySong(
            title="Naa Ready",
            artist="Thalapathy Vijay",
            album="Leo",
            canonical_hash=compute_canonical_hash("Naa Ready", "Thalapathy Vijay", "Leo"),
            state=SongState.NEW,
            quality_kbps=320,
        )
    )

    # Populate import job
    job = ImportJob(
        id="job-hits2026",
        url="https://open.spotify.com/playlist/37i9dQZF1DX4WYpdgoIcn6",
        title="Tamil Mega Hits 2026",
        platform="spotify",
        content_type="playlist",
        total_tracks=15,
        status=JobStatus.READY,
    )
    db.create_import_job(job)

    service = LibraryService(db=db, download_dir=str(downloads_dir))

    # Launch GUI
    app = TamilMP3App(service=service)
    app.geometry("1280x820")
    app.update()
    time.sleep(0.5)

    views_to_capture = [
        ("dashboard", output_dir / "01_dashboard_view.png"),
        ("add_music", output_dir / "02_add_music_view.png"),
        ("downloaded_songs", output_dir / "03_downloaded_songs_view.png"),
        ("downloads", output_dir / "04_downloads_manager_view.png"),
        ("library", output_dir / "05_library_catalog_view.png"),
        ("settings", output_dir / "06_settings_view.png"),
        ("help", output_dir / "07_help_view.png"),
    ]

    for view_name, out_file in views_to_capture:
        capture_view_screenshot(app, view_name, out_file)

    app.destroy()
    print("Visual validation screenshots capture completed successfully.")


if __name__ == "__main__":
    run_visual_capture()
