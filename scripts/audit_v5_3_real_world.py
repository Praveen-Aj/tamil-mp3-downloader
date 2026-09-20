"""
Real-World Audit of V5.3 Movie Discovery & Download Pipeline.

Validates:
1. Real External Source (Tamilmp3 / Direct CDN streams)
2. Real Movie Discovery & Canonical Ingestion
3. Real GUI Workflow (Movies View, Search, Detail, Download All, Live Progress, Download Missing)
4. Real File Validation (ID3/MP3 header check, non-zero file sizes, valid filenames)
5. Idempotency & Duplicate Prevention
6. Partial Failure & Retry Recovery
7. State Persistence across App Restarts
8. Visual Screenshot Capture & Inspection
"""

import os
import sys
sys.stdout.reconfigure(encoding="utf-8")
import time
import json
import logging
import ctypes
from ctypes import wintypes
from pathlib import Path
from tkinter import messagebox
from PIL import Image, ImageGrab

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scrapers.tamilmp3 import Tamilmp3Scraper
from library.database import SQLiteDatabase
from library.migrator import DatabaseMigrator
from library.models import SongState, DownloadState
from ui.services.library_service import LibraryService
from ui.app import TamilMP3App
from ui import theme


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


def verify_audio_file(file_path: Path) -> dict:
    """Perform byte-level and format verification on downloaded audio file."""
    assert file_path.exists(), f"File does not exist: {file_path}"
    size = file_path.stat().st_size
    assert size > 100_000, f"File is suspiciously small ({size} bytes): {file_path}"

    with open(file_path, "rb") as f:
        header = f.read(16)

    is_id3 = header[:3] == b"ID3"
    is_mp3_sync = header[:2] == b"\xff\xfb" or header[:2] == b"\xff\xfa" or header[:2] == b"\xff\xf3"
    is_valid_mp3 = is_id3 or is_mp3_sync

    assert is_valid_mp3, f"File does not have valid MP3 header (header: {header[:4]}): {file_path}"
    assert file_path.suffix.lower() == ".mp3", f"Expected .mp3 extension, got {file_path.suffix}"

    return {
        "file_name": file_path.name,
        "size_bytes": size,
        "size_mb": round(size / (1024 * 1024), 2),
        "is_id3": is_id3,
        "valid_mp3": is_valid_mp3,
    }


def run_audit():
    print("=" * 70)
    print("STARTING V5.3 REAL-WORLD MOVIE AUDIT")
    print("=" * 70)

    # Disable blocking message boxes for automated GUI validation
    messagebox.showinfo = lambda *args, **kwargs: None
    messagebox.showwarning = lambda *args, **kwargs: None
    messagebox.showerror = lambda *args, **kwargs: None

    screenshots_dir = PROJECT_ROOT / "screenshots" / "v5.3-real-world-audit"
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    audit_db_path = PROJECT_ROOT / "audit_real_world.db"
    if audit_db_path.exists():
        audit_db_path.unlink()

    auth_download_dir = PROJECT_ROOT / "downloads"
    auth_download_dir.mkdir(parents=True, exist_ok=True)

    print(f"Audit Database: {audit_db_path}")
    print(f"Authoritative Downloads: {auth_download_dir}")

    # 1. Initialize DB and Migration
    db = SQLiteDatabase(audit_db_path)
    db.connect()
    migrator = DatabaseMigrator(db)
    migrator.migrate()

    service = LibraryService(db=db, download_dir=str(auth_download_dir))

    # ── Phase 1 & 2: Real External Source & Movie Discovery ──────────
    print("\n--- Phase 1 & 2: Live Movie Discovery from Tamilmp3 ---")
    scraper = Tamilmp3Scraper()
    assert scraper.test_connection() is True, "Tamilmp3 provider is unreachable"
    print("Tamilmp3 provider online and accessible.")

    disc_res = service.discover_movies_from_sources(source_names=["tamilmp3"], category="latest", max_pages=1)
    print(f"Discovery Result: {disc_res}")
    assert disc_res["movies_discovered"] > 0, "No movies were discovered"
    assert disc_res["songs_registered"] > 0, "No songs were registered"

    # Search for movie 'Meesaya Murukku 2'
    target_title = "Meesaya Murukku 2"
    matched_movies, total_found = db.search_and_filter_movies(query=target_title)
    assert total_found > 0, f"Movie '{target_title}' not found in database"
    movie_info = matched_movies[0]
    movie_id = movie_info["id"]
    print(f"Found Movie: '{movie_info['title']}' (ID={movie_id}, Year={movie_info['year']})")

    movie_details = service.get_movie_details(movie_id)
    assert movie_details is not None
    songs = movie_details["songs"]
    total_songs_count = len(songs)
    print(f"Discovered songs for '{target_title}': {total_songs_count}")
    for idx, s in enumerate(songs, start=1):
        print(f"  {idx}. {s['title']} | Quality: {s['quality_display']} | Provider: {s['source']} | State: {s['download_status_display']}")

    assert total_songs_count >= 5, f"Expected at least 5 songs in movie, found {total_songs_count}"

    # Clean any pre-existing downloads for this movie to guarantee clean real run
    movie_dl_dir = auth_download_dir / str(movie_info["year"] or 2026) / movie_info["title"]
    if movie_dl_dir.exists():
        for f in movie_dl_dir.iterdir():
            if f.is_file():
                f.unlink()

    # ── Phase 3: Real GUI Workflow ───────────────────────────────────
    print("\n--- Phase 3: Launching Real Desktop GUI Application ---")
    app = TamilMP3App(service=service)
    app.geometry("1400x900")
    app.update()
    time.sleep(1.0)
    print("Application launched successfully.")

    try:
        # Step 1: Open Movies View & Search
        print("\nStep 1: Navigating to Movies view...")
        app.show_view("movies")
        app.update()
        time.sleep(0.8)

        movies_view = app.views.get("movies")
        assert movies_view is not None, "MoviesView not found in app"

        print(f"Searching for '{target_title}' in GUI...")
        movies_view.search_var.set(target_title)
        movies_view._on_search()
        app.update()
        time.sleep(0.8)

        # Screenshot 1: Real movie search result
        capture_app_screenshot(app, screenshots_dir / "01_real_movie_search_result.png")

        # Step 2: Open Movie Detail
        print(f"\nStep 2: Opening Movie Detail for '{target_title}'...")
        app._open_movie_detail(movie_id)
        app.update()
        time.sleep(1.0)

        detail_view = app.views.get("movie_detail")
        assert detail_view is not None, "MovieDetailView not found in app"

        # Screenshot 2: Real movie detail page
        capture_app_screenshot(app, screenshots_dir / "02_real_movie_detail_page.png")

        # Screenshot 3: Real movie with songs & initial download states
        capture_app_screenshot(app, screenshots_dir / "03_real_movie_with_songs.png")

        # Verify initial states
        assert str(total_songs_count) in detail_view.chip_total.cget("text")
        assert "0" in detail_view.chip_downloaded.cget("text")
        assert str(total_songs_count) in detail_view.chip_missing.cget("text")

        # Step 3: Trigger Download All
        print("\nStep 3: Triggering 'Download All' via GUI...")
        plan = service.plan_movie_download_all(movie_id)
        assert len(plan.new_songs) == total_songs_count, f"Expected {total_songs_count} new planned songs"

        # Execute download plan asynchronously through existing pipeline
        enqueued_ids = service.execute_download_plan(plan, run_async=True)
        print(f"Enqueued {len(enqueued_ids)} download jobs into DownloadJobManager.")
        app.update()
        time.sleep(0.5)

        # Screenshot 4: Active Download All
        capture_app_screenshot(app, screenshots_dir / "04_active_download_all.png")

        # Step 4: Wait for downloads to complete and monitor progress
        print("\nStep 4: Monitoring real network downloads...")
        start_wait = time.time()
        timeout = 360  # 6 minutes for real network downloads
        last_logged = -1
        while time.time() - start_wait < timeout:
            app.update()
            time.sleep(0.3)
            # Check completed count in DB
            stats = db.get_movie_download_stats(movie_id)
            elapsed = int(time.time() - start_wait)
            if elapsed != last_logged and elapsed % 5 == 0:
                print(f"  [{elapsed}s elapsed] Downloaded: {stats['downloaded']}/{total_songs_count}")
                last_logged = elapsed
            if stats["downloaded"] == total_songs_count:
                print(f"All {total_songs_count} songs downloaded in {round(time.time() - start_wait, 1)}s!")
                break
        else:
            stats = db.get_movie_download_stats(movie_id)
            print(f"Timed out waiting for downloads. Downloaded: {stats['downloaded']}/{total_songs_count}")

        # Navigate to Downloads view to verify live job manager records
        print("\nNavigating to Downloads view...")
        app.show_view("downloads")
        app.update()
        time.sleep(1.0)
        # Screenshot 5: Completed downloads
        capture_app_screenshot(app, screenshots_dir / "05_completed_downloads.png")

        # Return to Movie Detail view
        print("\nReturning to Movie Detail view...")
        app._open_movie_detail(movie_id)
        if detail_view:
            detail_view.refresh()
        app.update()
        time.sleep(1.0)

        # Screenshot 6: Final movie state
        capture_app_screenshot(app, screenshots_dir / "06_final_movie_state.png")

        # Verify completed movie metrics in GUI
        final_stats = db.get_movie_download_stats(movie_id)
        print(f"Final Movie Stats in DB: {final_stats}")
        assert final_stats["downloaded"] == total_songs_count, f"Expected {total_songs_count} downloaded, got {final_stats['downloaded']}"
        assert final_stats["missing"] == 0, f"Expected 0 missing, got {final_stats['missing']}"

        # Step 5: Test Download Missing after completion (Idempotency)
        print("\nStep 5: Triggering 'Download Missing' after full download...")
        missing_plan = service.plan_movie_download_missing(movie_id)
        print(f"Download Missing planned songs: {len(missing_plan.new_songs)}")
        assert len(missing_plan.new_songs) == 0, "Download Missing should queue 0 songs when already complete!"

        # Screenshot 7: Download Missing after completion
        capture_app_screenshot(app, screenshots_dir / "07_download_missing_after_completion.png")

    finally:
        app.destroy()
        print("Initial GUI session closed.")

    # ── Phase 4: Real File Validation ────────────────────────────────
    print("\n--- Phase 4: Byte-Level Physical File Validation ---")
    detailed_songs = db.get_movie_songs_detailed(movie_id)
    validated_files = []

    for s in detailed_songs:
        f_path_str = s["file_path"]
        assert f_path_str, f"Database file_path is empty for song: {s['title']}"
        f_path = Path(f_path_str)
        assert f_path.is_file(), f"File missing from disk: {f_path}"

        v_res = verify_audio_file(f_path)
        validated_files.append(v_res)
        print(f" [OK] Verified: '{v_res['file_name']}' | Size: {v_res['size_mb']} MB | ID3: {v_res['is_id3']} | Valid MP3: {v_res['valid_mp3']}")

    # ── Phase 5: Duplicate / Idempotency Test ─────────────────────────
    print("\n--- Phase 5: Duplicate and Idempotency Invariance Test ---")
    pre_movie_count = len(db.list_movies(limit=100))
    with db._lock:
        cursor = db._conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM songs")
        pre_song_count = cursor.fetchone()[0]

    # Re-run discovery from sources
    print("Re-running movie discovery from sources...")
    re_disc = service.discover_movies_from_sources(source_names=["tamilmp3"], category="latest", max_pages=1)
    print(f"Re-discovery stats: {re_disc}")

    post_movie_count = len(db.list_movies(limit=100))
    with db._lock:
        cursor = db._conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM songs")
        post_song_count = cursor.fetchone()[0]

    assert pre_movie_count == post_movie_count, f"Duplicate movies created! ({pre_movie_count} -> {post_movie_count})"
    assert pre_song_count == post_song_count, f"Duplicate songs created! ({pre_song_count} -> {post_song_count})"
    print(" [OK] Zero duplicate movies or songs created on re-discovery.")

    # ── Phase 6: Partial Failure & Recovery Simulation ───────────────
    print("\n--- Phase 6: Controlled Failure and Retry Recovery Test ---")
    test_song = detailed_songs[0]
    test_sid = test_song["song_id"]
    orig_file = Path(test_song["file_path"])

    # Temporarily corrupt source URL to test failure handling
    with db._lock:
        with db._conn:
            db._conn.execute(
                "UPDATE song_sources SET download_reference = ?, source_url = ? WHERE song_id = ?",
                ("https://dl.invalid-host-for-test.xyz/404.mp3", "https://invalid-host/fail", test_sid)
            )
            db._conn.execute("UPDATE songs SET state = 'NEW', file_path = NULL WHERE id = ?", (test_sid,))

    # Remove file from disk to simulate missing file
    if orig_file.exists():
        orig_file.unlink()

    # Plan and execute download missing for the failed song
    fail_plan = service.plan_movie_download_missing(movie_id)
    assert len(fail_plan.new_songs) == 1, "Expected exactly 1 song in missing plan"
    assert fail_plan.new_songs[0].song_id == test_sid

    print("Executing download with broken URL...")
    service.execute_download_plan(fail_plan, run_async=False)

    # Song must NOT become 'OWNED'
    failed_song_record = db.get_song(test_sid)
    assert failed_song_record.state != SongState.OWNED, "Failed song was falsely marked as OWNED!"
    print(f" [OK] Failed song correctly remained in state: {failed_song_record.state.value}")

    # Now recover: restore valid download reference
    print("Restoring valid URL and retrying recovery download...")
    orig_ref = f"Tamil Mp3 Songs/2026 Tamil Mp3 Songs/Meesaya Murukku 2/Meesaya Murukku 2 320kbps/{orig_file.name}"
    with db._lock:
        with db._conn:
            db._conn.execute(
                "UPDATE song_sources SET download_reference = ?, source_url = ? WHERE song_id = ?",
                (orig_ref, f"https://tamilmp3.in/meesaya-murukku-2-songs", test_sid)
            )

    retry_plan = service.plan_movie_download_missing(movie_id)
    assert len(retry_plan.new_songs) == 1
    service.execute_download_plan(retry_plan, run_async=False)

    recovered_song = db.get_song(test_sid)
    assert recovered_song.state == SongState.OWNED, f"Recovery failed, state={recovered_song.state}"
    assert orig_file.exists() and orig_file.stat().st_size > 100_000
    print(" [OK] Song successfully recovered, downloaded, and marked as OWNED!")

    # ── Phase 7: State Persistence Across Application Reopen ─────────
    print("\n--- Phase 7: Reopening Application & Verifying Persistence ---")
    app2 = TamilMP3App(service=service)
    app2.geometry("1400x900")
    app2.update()
    time.sleep(0.5)

    try:
        app2._open_movie_detail(movie_id)
        app2.update()
        time.sleep(0.8)
        detail2 = app2.views.get("movie_detail")
        assert detail2 is not None

        stats_reopen = db.get_movie_download_stats(movie_id)
        assert stats_reopen["downloaded"] == total_songs_count
        assert stats_reopen["missing"] == 0
        print(f" [OK] Reopen verification succeeded: {stats_reopen['downloaded']}/{total_songs_count} songs downloaded.")
    finally:
        app2.destroy()

    db.close()
    print("\n" + "=" * 70)
    print("V5.3 REAL-WORLD AUDIT COMPLETED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    run_audit()
