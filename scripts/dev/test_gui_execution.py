"""
GUI Execution Verification Script.

Launches the real CustomTkinter UI application (ui.app.TamilMP3App) headlessly,
navigates through every view, exercises user interaction handlers, opens dialogs,
and verifies no exceptions, crashes, or unhandled errors occur.
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Insert project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

try:
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
except Exception as e:
    print(f"Tkinter root init: {e}", flush=True)

from ui.app import TamilMP3App
from library.models import LibrarySong, SongSource, SongState

def exercise_ui_application():
    print("1. Instantiating TamilMP3App...", flush=True)
    app = TamilMP3App()
    app.update_idletasks()
    print("   Application initialized cleanly!", flush=True)

    print("2. Testing view navigation...", flush=True)
    views = ["dashboard", "discover", "library", "downloads", "import", "sources", "settings"]
    for v in views:
        app.show_view(v)
        app.update_idletasks()
        print(f"   Navigated to '{v}' view successfully.", flush=True)

    print("3. Exercising Dashboard Overview...", flush=True)
    app.views["dashboard"].refresh()
    app.update_idletasks()

    print("4. Exercising Discover View...", flush=True)
    app.show_view("discover")
    with patch("scrapers.masstamilan.MassTamilanScraper.get_albums", return_value=[]), \
         patch("scrapers.tamilmp3.Tamilmp3Scraper.get_albums", return_value=[]), \
         patch("scrapers.friendstamilmp3.FriendsTamilMP3Scraper.get_albums", return_value=[]):
        session = app.service.run_discovery(category="latest")
        print(f"   Discovery run summary: {session}", flush=True)

    print("5. Exercising Library View & Pagination...", flush=True)
    app.show_view("library")
    lib_view = app.views["library"]
    lib_view.refresh()
    app.update_idletasks()

    print("6. Exercising Song Details Dialog...", flush=True)
    song = LibrarySong(
        title="Nenjame",
        artist="Anirudh Ravichander",
        album="Doctor",
        year=2021,
        canonical_hash="nenjame_hash",
    )
    sid = app.service.db.add_song(song)
    app.service.db.add_source(SongSource(
        song_id=sid,
        source_name="masstamilan",
        source_url="https://masstamilan.dev/nenjame.mp3",
        quality_kbps=320,
    ))

    details = app.service.get_song_details(sid)
    assert details["song"].title == "Nenjame"
    print("   Song details retrieved successfully.", flush=True)

    print("7. Exercising Download Plan Preview & Execution...", flush=True)
    plan = app.service.preview_download_plan([sid])
    assert plan.total_to_download == 1
    enqueued = app.service.execute_download_plan(plan, run_async=False)
    print(f"   Download plan executed, enqueued IDs: {enqueued}", flush=True)

    print("8. Exercising Downloads View...", flush=True)
    app.show_view("downloads")
    dl_view = app.views["downloads"]
    dl_view.refresh()
    dl_view._retry_failed()
    app.update_idletasks()

    print("9. Exercising Settings View...", flush=True)
    app.show_view("settings")
    settings_view = app.views["settings"]
    settings_view.quality_var.set("320")
    settings_view._save_settings()
    app.update_idletasks()

    print("10. Exercising Sources View...", flush=True)
    app.show_view("sources")
    sources_view = app.views["sources"]
    sources_view.refresh()
    app.update_idletasks()

    app.destroy()
    print("[OK] Full UI Application execution test completed with ZERO errors!", flush=True)

if __name__ == "__main__":
    exercise_ui_application()
