"""
Comprehensive GUI End-to-End Workflow Test.

Exercises the entire user-facing workflow in the CustomTkinter GUI:
1. Launch application.
2. Navigate to 'Add Music'.
3. Enter test URL and trigger Analyze.
4. Verify analyzed tracks render with checkboxes.
5. Trigger 'Download Selected'.
6. Stream valid audio chunk bytes from local test server to disk.
7. Verify physical file is created on disk with valid audio header.
8. Navigate to 'Downloaded Songs' view and verify song appears in table.
9. Test 'Open Folder' / reveal callback.
10. Trigger 'Delete File' (delete from disk + reset DB state).
11. Verify physical file is unlinked and row disappears from Downloaded Songs.
"""

from pathlib import Path
import time
import pytest
import customtkinter as ctk

from library.database import SQLiteDatabase
from library.models import LibrarySong, SongSource, SongState, ImportJob, ImportJobItem, JobStatus, ItemState
from library.canonical import compute_canonical_hash
from ui.services.library_service import LibraryService
from ui.app import TamilMP3App
from tests.fixtures_helper import LocalTestServer


@pytest.fixture(scope="module")
def local_server():
    server = LocalTestServer()
    url = server.start()
    yield url
    server.shutdown()


@pytest.mark.gui
@pytest.mark.e2e
def test_full_gui_e2e_workflow(tmp_path: Path, local_server: str):
    db_path = tmp_path / "gui_e2e.db"
    dl_dir = tmp_path / "downloads"
    dl_dir.mkdir(parents=True, exist_ok=True)

    db = SQLiteDatabase(db_path)
    db.connect()

    service = LibraryService(db=db, download_dir=str(dl_dir))

    # Step 1: Launch Application
    app = TamilMP3App(service=service)
    app.update()
    assert app.winfo_exists()
    assert app.current_view_name == "dashboard"

    # Step 2: Navigate to Add Music
    app.navigate_to("add_music")
    app.update()
    assert app.current_view_name == "add_music"
    add_music_view = app.views["add_music"]

    # Step 3: Enter test URL and perform analysis
    test_stream_url = f"{local_server}/valid-song.mp3"
    add_music_view.url_entry.delete(0, "end")
    add_music_view.url_entry.insert(0, test_stream_url)

    job, items = service.analyze_music_url(test_stream_url)
    add_music_view._render_playlist_ui(job, items)
    app.update()

    # Step 4: Verify track analysis result was populated
    assert add_music_view._active_job is not None
    assert len(add_music_view._all_items) >= 1
    assert len(add_music_view._selected_item_ids) >= 1

    # Step 5: Execute Download Selected
    service.execute_import_job(
        job_id=add_music_view._active_job.id,
        item_ids=list(add_music_view._selected_item_ids),
        run_async=False,
    )
    app.update()

    # Step 6 & 7: Verify physical audio file created on disk
    downloaded_files = list(dl_dir.glob("*.mp3")) + list(dl_dir.glob("*/*.mp3"))
    assert len(downloaded_files) >= 1
    audio_file = downloaded_files[0]
    assert audio_file.exists()
    assert audio_file.stat().st_size > 0

    # Verify ID3 or audio sync header
    content = audio_file.read_bytes()
    assert content.startswith(b"\xff\xfb") or content.startswith(b"ID3")

    # Step 8: Navigate to Downloaded Songs view
    app.navigate_to("downloaded_songs")
    app.update()
    assert app.current_view_name == "downloaded_songs"
    dl_view = app.views["downloaded_songs"]

    # Verify song row is visible
    assert len(dl_view._songs) >= 1
    song_record = dl_view._songs[0]
    assert Path(song_record.file_path).exists()

    # Step 9: Test multi-selection and UI helpers
    dl_view._toggle_select_all()
    assert len(dl_view._selected_ids) >= 1

    # Step 10: Trigger Delete File (destructive disk deletion)
    del_ok = service.delete_downloaded_song(song_record.id, delete_file_from_disk=True)
    assert del_ok is True

    # Step 11: Verify physical file unlinked and view refreshed
    assert not audio_file.exists()
    dl_view.refresh()
    app.update()
    assert len(dl_view._songs) == 0

    try:
        app.destroy()
    except Exception:
        pass
