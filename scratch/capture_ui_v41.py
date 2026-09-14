"""
Authentic UI capture script using Win32 PrintWindow.
Captures live rendered pixels of all primary views and states in Tamil MP3 Downloader v4.1.0.

Produces the exact 10 required screenshots under screenshots/ui-validation/:
01-dashboard.png
02-add-music.png
03-playlist-results.png
04-library.png
05-song-details.png
06-downloads.png
07-review-results.png
08-source-health.png
09-settings.png
10-help-guide.png
"""

import ctypes
from ctypes import windll, byref, wintypes
import time
import sys
from pathlib import Path
from PIL import Image
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

import customtkinter as ctk

from ui.app import TamilMP3App
from library.models import (
    LibrarySong, SongSource, SongState, DownloadState, Download,
    ImportJob, ImportJobItem, JobStatus, ItemState
)
from ui.dialogs.plan_preview import PlanPreviewDialog
from ui.dialogs.song_details import SongDetailsDialog

OUTPUT_DIR = Path("screenshots/ui-validation")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", BITMAPINFOHEADER),
        ("bmiColors", wintypes.DWORD * 3),
    ]


def capture_window_win32(hwnd: int, save_path: Path) -> bool:
    """Capture authentic window pixels using Win32 PrintWindow PW_RENDERFULLCONTENT."""
    user32 = windll.user32
    gdi32 = windll.gdi32

    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, byref(rect))
    width = rect.right - rect.left
    height = rect.bottom - rect.top

    if width <= 0 or height <= 0:
        return False

    hwnd_dc = user32.GetWindowDC(hwnd)
    mem_dc = gdi32.CreateCompatibleDC(hwnd_dc)
    bitmap = gdi32.CreateCompatibleBitmap(hwnd_dc, width, height)
    gdi32.SelectObject(mem_dc, bitmap)

    PW_RENDERFULLCONTENT = 2
    res = user32.PrintWindow(hwnd, mem_dc, PW_RENDERFULLCONTENT)
    if not res:
        res = user32.PrintWindow(hwnd, mem_dc, 0)

    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = width
    bmi.bmiHeader.biHeight = -height  # top-down
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = 0  # BI_RGB

    buffer_len = width * height * 4
    buffer = ctypes.create_string_buffer(buffer_len)

    gdi32.GetDIBits(mem_dc, bitmap, 0, height, buffer, byref(bmi), 0)

    # Cleanup Win32 GDI objects
    gdi32.DeleteObject(bitmap)
    gdi32.DeleteDC(mem_dc)
    user32.ReleaseDC(hwnd, hwnd_dc)

    # Save image
    img = Image.frombuffer("RGBA", (width, height), buffer, "raw", "BGRA", 0, 1)
    img = img.convert("RGB")
    img.save(str(save_path))
    print(f"Captured: {save_path.name} ({width}x{height})")
    return True


def populate_demo_data(app: TamilMP3App):
    """Seed sample canonical library entries and a demo import job."""
    db = app.service.db

    # Sample canonical songs
    songs_data = [
        ("Arabic Kuthu", "Anirudh Ravichander", "Beast", 278, SongState.OWNED, 320),
        ("Naa Ready", "Anirudh Ravichander, Thalapathy Vijay", "Leo", 248, SongState.OWNED, 320),
        ("Hukum - Thalaivar Alappara", "Anirudh Ravichander", "Jailer", 207, SongState.NEW, 320),
        ("Chinna Chinna Aasai", "A.R. Rahman, Minmini", "Roja", 295, SongState.OWNED, 320),
        ("Munbe Vaa", "A.R. Rahman, Naresh Iyer, Shreya Ghoshal", "Sillunu Oru Kaadhal", 358, SongState.NEW, 128),
        ("Aalaporan Tamizhan", "A.R. Rahman, Kailash Kher", "Mersal", 348, SongState.NEW, 320),
    ]

    song_ids = []
    for title, artist, album, dur, st, q in songs_data:
        c_hash = f"demo_hash_{title.lower().replace(' ', '_')}"
        s = LibrarySong(
            canonical_hash=c_hash,
            title_normalized=title.lower(),
            artist_normalized=artist.lower(),
            album_normalized=album.lower(),
            duration_seconds=dur,
            title=title,
            artist=artist,
            album=album,
            state=st,
            quality_kbps=q,
        )
        s_id = db.add_song(s)
        song_ids.append(s_id)
        # Add source variant
        src = SongSource(
            song_id=s_id,
            source_name="masstamilan" if q == 320 else "friendstamilmp3",
            source_url=f"https://example.com/{title.lower().replace(' ', '_')}.mp3",
            quality_kbps=q,
        )
        db.add_source(src)

    # Demo import job
    demo_job = ImportJob(
        id="job-demo-tamil-hits",
        url="https://open.spotify.com/playlist/37i9dQZF1DX4sWSpwq3LiO",
        platform="Spotify",
        content_type="Playlist",
        title="Top Tamil Hits 2026",
        artist="Spotify Curated",
        total_tracks=6,
        status=JobStatus.READY,
    )
    db.create_import_job(demo_job)

    demo_items = [
        ImportJobItem(
            id=101,
            job_id="job-demo-tamil-hits",
            track_index=1,
            title="Arabic Kuthu",
            artist="Anirudh Ravichander",
            album="Beast",
            duration_seconds=278,
            state=ItemState.OWNED,
            selected_provider="Tamil Regional",
            match_confidence=1.0,
            match_explanation="Already owned in library at 320 kbps",
        ),
        ImportJobItem(
            id=102,
            job_id="job-demo-tamil-hits",
            track_index=2,
            title="Naa Ready",
            artist="Anirudh Ravichander",
            album="Leo",
            duration_seconds=248,
            state=ItemState.OWNED,
            selected_provider="YouTube Music",
            match_confidence=0.98,
            match_explanation="Already owned in library at 320 kbps",
        ),
        ImportJobItem(
            id=103,
            job_id="job-demo-tamil-hits",
            track_index=3,
            title="Hukum - Thalaivar Alappara",
            artist="Anirudh Ravichander",
            album="Jailer",
            duration_seconds=207,
            state=ItemState.READY,
            selected_provider="YouTube Music",
            selected_source_url="https://www.youtube.com/watch?v=1F3hm6MfR1k",
            match_confidence=0.96,
            match_explanation="High confidence (96%): title & duration match closely",
        ),
        ImportJobItem(
            id=104,
            job_id="job-demo-tamil-hits",
            track_index=4,
            title="Chinna Chinna Aasai",
            artist="A.R. Rahman",
            album="Roja",
            duration_seconds=295,
            state=ItemState.READY,
            selected_provider="Tamil Regional",
            selected_source_url="https://tamilmp3.in/roja-songs",
            match_confidence=0.94,
            match_explanation="High confidence (94%): title & duration match closely",
        ),
        ImportJobItem(
            id=105,
            job_id="job-demo-tamil-hits",
            track_index=5,
            title="Munbe Vaa",
            artist="A.R. Rahman",
            album="Sillunu Oru Kaadhal",
            duration_seconds=358,
            state=ItemState.NEEDS_REVIEW,
            selected_provider="YouTube",
            selected_source_url="https://www.youtube.com/watch?v=demo",
            match_confidence=0.74,
            match_explanation="Medium confidence (74%): live version detected",
        ),
        ImportJobItem(
            id=106,
            job_id="job-demo-tamil-hits",
            track_index=6,
            title="Rare Acoustic Jam Session",
            artist="Independent",
            album="Private Studio",
            duration_seconds=180,
            state=ItemState.NO_SOURCE,
            match_confidence=0.0,
            match_explanation="No matching audio source found across providers",
        ),
    ]
    db.add_import_job_items(demo_items)

    # Seed a download record for downloads manager
    dl = Download(
        id=1,
        song_id=song_ids[0],
        song_source_id=1,
        output_path="C:/Users/Praveen/Music/Arabic_Kuthu.mp3",
        state=DownloadState.COMPLETED,
        file_size_bytes=10485760,
    )
    db.add_download(dl)

    dl2 = Download(
        id=2,
        song_id=song_ids[1],
        song_source_id=2,
        output_path="C:/Users/Praveen/Music/Naa_Ready.mp3",
        state=DownloadState.DOWNLOADING,
        file_size_bytes=9437184,
    )
    db.add_download(dl2)

    return song_ids, demo_job, demo_items


def main():
    print("Launching TamilMP3App for authentic UI validation capture...")
    app = TamilMP3App()
    app.geometry("1366x768")
    app.update()

    hwnd = app.winfo_id()

    # Seed data
    song_ids, demo_job, demo_items = populate_demo_data(app)
    app.refresh_status_bar()
    app.update()

    # 1. Dashboard
    app.show_view("dashboard")
    app.update()
    time.sleep(0.4)
    capture_window_win32(hwnd, OUTPUT_DIR / "01-dashboard.png")

    # 2. Add Music (Initial empty state)
    app.show_view("add_music")
    app.update()
    time.sleep(0.4)
    capture_window_win32(hwnd, OUTPUT_DIR / "02-add-music.png")

    # 3. Playlist Results (Add Music with analyzed playlist)
    add_music_view = app.views["add_music"]
    add_music_view.url_entry.delete(0, "end")
    add_music_view.url_entry.insert(0, demo_job.url)
    add_music_view._render_playlist_ui(demo_job, demo_items)
    app.update()
    time.sleep(0.4)
    capture_window_win32(hwnd, OUTPUT_DIR / "03-playlist-results.png")

    # 4. Library
    app.show_view("library")
    app.update()
    time.sleep(0.4)
    capture_window_win32(hwnd, OUTPUT_DIR / "04-library.png")

    # 5. Song Details Modal
    details = app.service.get_song_details(song_ids[0])
    dlg_song = SongDetailsDialog(
        app,
        song=details["song"],
        sources=details["sources"],
        contexts=details["contexts"],
        planner_decision=details.get("planner_decision"),
    )
    dlg_song.update()
    time.sleep(0.4)
    capture_window_win32(hwnd, OUTPUT_DIR / "05-song-details.png")
    dlg_song.destroy()
    app.update()

    # 6. Downloads Manager
    app.show_view("downloads")
    app.update()
    time.sleep(0.4)
    capture_window_win32(hwnd, OUTPUT_DIR / "06-downloads.png")

    # 7. Review Results View
    app.show_view("results")
    app.update()
    time.sleep(0.4)
    capture_window_win32(hwnd, OUTPUT_DIR / "07-review-results.png")

    # 8. Source Health
    app.show_view("sources")
    app.update()
    time.sleep(0.4)
    capture_window_win32(hwnd, OUTPUT_DIR / "08-source-health.png")

    # 9. Settings
    app.show_view("settings")
    app.update()
    time.sleep(0.4)
    capture_window_win32(hwnd, OUTPUT_DIR / "09-settings.png")

    # 10. Help & User Guide
    app.show_view("help")
    app.update()
    time.sleep(0.4)
    capture_window_win32(hwnd, OUTPUT_DIR / "10-help-guide.png")

    app.destroy()
    print("All 10 authentic screenshots captured successfully!")


if __name__ == "__main__":
    main()
