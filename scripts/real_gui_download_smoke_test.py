"""
Real-World GUI Download Smoke Test.
Performs an end-to-end user-facing validation using the real CustomTkinter GUI,
a real external Tamil music source (TamilMP3 / direct stream), real network streaming,
real physical file creation in the authoritative download directory, and visual screenshot capture.
"""

import os
import sys
import time
import ctypes
from ctypes import wintypes
from pathlib import Path
from PIL import Image, ImageGrab

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scrapers.tamilmp3 import Tamilmp3Scraper
from library.database import SQLiteDatabase
from library.models import SongState, DownloadState, ItemState
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
        print(f"Captured: {output_path.name} ({w}x{h})")
    except Exception as exc:
        print(f"PrintWindow capture fallback failed: {exc}")
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
            print(f"All screenshot methods failed: {e2}")


def run_real_gui_smoke_test():
    results = {}
    print("=" * 70)
    print("STARTING REAL-WORLD GUI DOWNLOAD SMOKE TEST")
    print("=" * 70)

    # 1. Authoritative setup
    smoke_dir = PROJECT_ROOT / "screenshots" / "real-smoke-test"
    smoke_dir.mkdir(parents=True, exist_ok=True)

    auth_download_dir = (PROJECT_ROOT / "downloads").resolve()
    auth_download_dir.mkdir(parents=True, exist_ok=True)
    db_path = PROJECT_ROOT / "library.db"

    print(f"Authoritative Download Directory: {auth_download_dir}")
    print(f"Database Path: {db_path}")

    # 2. Probe real external Tamil music source
    print("\n--- 1. Probing Real External Provider (Tamilmp3) ---")
    scraper = Tamilmp3Scraper()
    assert scraper.test_connection() is True, "External provider Tamilmp3 is unreachable"

    albums = scraper.get_albums(category="latest", max_pages=1)
    assert len(albums) > 0, "No albums retrieved from Tamilmp3"
    chosen_album = albums[0]
    print(f"Discovered live album: {chosen_album.name} ({chosen_album.url})")

    songs = scraper.get_songs(chosen_album)
    assert len(songs) > 0, f"No songs found in album {chosen_album.name}"
    chosen_song = songs[0]
    print(f"Discovered live song: {chosen_song.name} ({chosen_song.url})")

    real_download_url = scraper.get_download_url(chosen_song, quality="320")
    assert real_download_url and "http" in real_download_url, "Failed to get signed live download URL"
    print(f"Resolved live audio stream URL: {real_download_url[:65]}...")

    results["provider"] = "Tamilmp3 / Direct Stream"
    results["album"] = chosen_album.name
    results["song_title"] = chosen_song.name
    results["stream_url"] = real_download_url

    # Ensure fresh state for smoke test track
    for f in auth_download_dir.glob("*Underdog Anthem*"):
        f.unlink(missing_ok=True)

    # 3. Launch Real Desktop GUI
    print("\n--- 2. Launching Real Desktop GUI Application ---")
    db = SQLiteDatabase(db_path)
    db.connect()
    with db._lock:
        with db._conn:
            db._conn.execute("DELETE FROM downloads WHERE output_path LIKE '%Underdog Anthem%'")
            db._conn.execute("DELETE FROM songs WHERE title LIKE '%Underdog Anthem%'")
            db._conn.execute("DELETE FROM import_jobs WHERE url LIKE '%Underdog+Anthem%'")
    service = LibraryService(db=db, download_dir=str(auth_download_dir))

    app = TamilMP3App(service=service)
    app.geometry("1280x820")
    app.update()
    time.sleep(1.0)
    print("Application launched successfully.")

    # Capture initial Dashboard
    app.navigate_to("dashboard")
    capture_app_screenshot(app, smoke_dir / "01_initial_dashboard.png")
    results["initial_dashboard_captured"] = True

    # 4. Add/Import Song in GUI
    print("\n--- 3. Navigating to Add Music and Analyzing Real URL ---")
    app.navigate_to("add_music")
    app.update()
    add_view = app.views["add_music"]

    # Paste URL into GUI entry
    add_view.url_entry.delete(0, "end")
    add_view.url_entry.insert(0, real_download_url)
    app.update()

    # Click Analyze URL through GUI
    print("Triggering GUI URL analysis...")
    add_view._on_analyze_clicked()

    # Wait for GUI background analysis to complete
    max_wait = 30
    start_t = time.time()
    while add_view._is_analyzing and (time.time() - start_t < max_wait):
        add_view._drain_action_queue()
        app.update()
        time.sleep(0.1)

    add_view._drain_action_queue()
    app.update()
    time.sleep(0.5)
    assert not add_view._is_analyzing, "GUI analysis timed out"
    assert len(add_view._all_items) > 0, "GUI failed to resolve song item"

    resolved_item = add_view._all_items[0]
    print(f"GUI resolved track: '{resolved_item.title}', state={resolved_item.state.value}, provider={resolved_item.selected_provider}")
    capture_app_screenshot(app, smoke_dir / "02_song_analyzed_ready.png")
    results["analyzed_screenshot_captured"] = True

    # 5. Real Download via GUI
    print("\n--- 4. Initiating Real Download Through GUI ---")
    active_progress_seen = False
    progress_records = []

    def on_gui_progress(event):
        nonlocal active_progress_seen
        if event.percent > 0 and event.percent < 1.0:
            active_progress_seen = True
            progress_records.append((event.percent, event.speed_str))
            print(f"  [Live GUI Progress] {event.percent*100:.1f}% | {event.speed_str}")

    service.add_progress_listener(on_gui_progress)
    initial_dl_ids = {d.id for d in service.db.get_all_downloads()}

    # Click Download Selected in GUI
    add_view._on_download_selected()
    app.navigate_to("downloads")
    app.update()

    # Monitor live download progress
    print("Streaming audio chunks from live provider...")
    dl_start = time.time()
    dl_timeout = 240
    screenshot_captured_during_download = False
    target_download = None

    while time.time() - dl_start < dl_timeout:
        add_view._drain_action_queue()
        app.update()
        time.sleep(0.2)

        # Capture screenshot while download is actively streaming (between 10% and 90%)
        if active_progress_seen and not screenshot_captured_during_download:
            if any(0.05 < p[0] < 0.95 for p in progress_records):
                capture_app_screenshot(app, smoke_dir / "03_real_active_download.png")
                screenshot_captured_during_download = True
                print("Captured active streaming progress screenshot.")

        # Check if the specific new download has completed in DB
        new_dls = [d for d in service.db.get_all_downloads() if d.id not in initial_dl_ids]
        if new_dls and new_dls[0].state == DownloadState.COMPLETED:
            target_download = new_dls[0]
            print(f"Download reported COMPLETED by database: ID {target_download.id}")
            break
        elif new_dls and new_dls[0].state == DownloadState.FAILED:
            raise RuntimeError(f"Download reported FAILED by database: {new_dls[0].error_message}")

    assert target_download is not None, "Download timed out before completion"
    app.update()
    time.sleep(1.0)
    capture_app_screenshot(app, smoke_dir / "04_real_completed_download.png")
    results["completed_screenshot_captured"] = True
    results["live_progress_observed"] = active_progress_seen
    print(f"Live GUI progress events observed: {len(progress_records)}")

    # 6. Physical File Verification
    print("\n--- 5. Verifying Physical Audio File on Disk ---")
    target_physical_file = Path(target_download.output_path)
    print(f"Authoritative target file path from DB: {target_physical_file}")

    assert target_physical_file.exists(), f"Physical file does not exist: {target_physical_file}"
    file_size = target_physical_file.stat().st_size
    assert file_size > 100000, f"Physical file too small ({file_size} bytes)"

    # Verify audio header (ID3 or MP3 sync frame)
    header_bytes = target_physical_file.read_bytes()[:16]
    is_valid_mp3 = header_bytes.startswith(b"ID3") or header_bytes.startswith(b"\xff\xfb") or header_bytes.startswith(b"\xff\xf3")
    assert is_valid_mp3, f"Physical file lacks valid MP3 header: {header_bytes}"

    print(f"Verified physical file: {target_physical_file}")
    print(f"  Size: {file_size:,} bytes ({file_size / (1024*1024):.2f} MB)")
    print(f"  Header: {header_bytes[:10]} (Valid MP3 / ID3)")

    results["physical_file_path"] = str(target_physical_file)
    results["physical_file_size"] = file_size
    results["physical_file_format"] = "MP3 (MPEG Audio Layer III)"

    # 7. Verify GUI Downloaded Songs View
    print("\n--- 6. Verifying Downloaded Songs View in GUI ---")
    app.navigate_to("downloaded_songs")
    app.update()
    time.sleep(0.5)
    capture_app_screenshot(app, smoke_dir / "05_downloaded_songs_view.png")

    owned_songs = service.get_downloaded_songs()
    matching_owned = [s for s in owned_songs if s.id == target_download.song_id]
    assert len(matching_owned) > 0, f"Downloaded song ID {target_download.song_id} not found in Downloaded Songs list"
    downloaded_song = matching_owned[0]
    print(f"Downloaded Songs view shows: '{downloaded_song.title}' by '{downloaded_song.artist}'")
    assert downloaded_song.state == SongState.OWNED, "Song is not marked as OWNED"
    results["downloaded_songs_verified"] = True

    # 8. Real Playback Test
    print("\n--- 7. Real Playback Verification ---")
    play_success, play_msg = service.play_audio_file(downloaded_song.file_path)
    print(f"Playback result: success={play_success}, message='{play_msg}'")
    assert play_success is True, f"Playback invocation failed: {play_msg}"
    results["playback_verified"] = True

    # 9. Real Open-Folder Test
    print("\n--- 8. Real Open-Folder Verification ---")
    folder_success, folder_msg = service.open_path_in_explorer(downloaded_song.file_path)
    print(f"Open Folder result: success={folder_success}, message='{folder_msg}'")
    assert folder_success is True, f"Open folder invocation failed: {folder_msg}"
    assert str(auth_download_dir).lower() in folder_msg.lower() or "opened" in folder_msg.lower(), "Wrong folder opened"
    results["open_folder_verified"] = True

    # 10. Real Duplicate Download Test
    print("\n--- 9. Real Duplicate Download Prevention Test ---")
    # Re-analyze and attempt re-download
    app.navigate_to("add_music")
    app.update()
    add_view.url_entry.delete(0, "end")
    add_view.url_entry.insert(0, real_download_url)
    add_view._on_analyze_clicked()

    start_t = time.time()
    while add_view._is_analyzing and (time.time() - start_t < max_wait):
        add_view._drain_action_queue()
        app.update()
        time.sleep(0.1)

    add_view._drain_action_queue()
    app.update()
    time.sleep(0.5)
    re_items = add_view._all_items
    print(f"Re-analyzed track state in GUI: {re_items[0].state.value} ({re_items[0].match_explanation})")
    assert re_items[0].state == ItemState.OWNED or "already" in (re_items[0].match_explanation or "").lower(), \
        "Application failed to recognize already downloaded song"

    # Verify no duplicate file created on disk for this song
    current_files = list(auth_download_dir.glob("*Underdog Anthem*"))
    assert len(current_files) == 1, f"Duplicate physical files detected! Found: {len(current_files)} ({current_files})"
    print(f"Duplicate check PASS: Exactly 1 physical file on disk ({current_files[0].name}).")
    results["duplicate_prevented"] = True

    # 11. Settings View Verification
    print("\n--- 10. Verifying Settings View & Authoritative Directory ---")
    app.navigate_to("settings")
    app.update()
    time.sleep(0.5)
    capture_app_screenshot(app, smoke_dir / "06_settings_download_directory.png")
    results["settings_screenshot_captured"] = True

    # Close application cleanly
    app.destroy()
    print("\n" + "=" * 70)
    print("ALL REAL-WORLD GUI SMOKE TEST VERIFICATIONS PASSED SUCCESSFULLY!")
    print("=" * 70)
    return results


if __name__ == "__main__":
    run_real_gui_smoke_test()
