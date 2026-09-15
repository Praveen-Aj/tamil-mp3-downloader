"""GUI tests for Downloaded Songs view interactions (selection, select all, clear selection, filters)."""

from pathlib import Path
import pytest
import customtkinter as ctk

from library.database import SQLiteDatabase
from library.models import LibrarySong, SongState
from library.canonical import compute_canonical_hash
from ui.services.library_service import LibraryService
from ui.views.downloaded_songs import DownloadedSongsView
from ui.app import TamilMP3App


@pytest.mark.gui
def test_downloaded_songs_view_interactions(tmp_path: Path):
    """Verify DownloadedSongsView displays verified songs, handles multi-select, and updates UI."""
    db_path = tmp_path / "gui_dl.db"
    dl_dir = tmp_path / "downloads"
    dl_dir.mkdir(parents=True, exist_ok=True)

    # Create 2 verified audio files
    f1 = dl_dir / "Song1.mp3"
    f1.write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 300)
    f2 = dl_dir / "Song2.mp3"
    f2.write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 300)

    db = SQLiteDatabase(db_path)
    db.connect()
    s1_id = db.add_song(
        LibrarySong(
            title="Song 1",
            artist="Artist 1",
            canonical_hash=compute_canonical_hash("Song 1", "Artist 1", "Album 1"),
            state=SongState.OWNED,
            file_path=str(f1),
        )
    )
    s2_id = db.add_song(
        LibrarySong(
            title="Song 2",
            artist="Artist 2",
            canonical_hash=compute_canonical_hash("Song 2", "Artist 2", "Album 2"),
            state=SongState.OWNED,
            file_path=str(f2),
        )
    )

    service = LibraryService(db=db, download_dir=str(dl_dir))

    app = TamilMP3App(service=service)
    app.navigate_to("downloaded_songs")
    app.update()
    view = app.views["downloaded_songs"]

    # Verify initial render
    assert len(view._songs) == 2

    # Test Select All
    view._toggle_select_all()
    assert len(view._selected_ids) == 2

    # Test Clear Selection
    view._toggle_select_all()
    assert len(view._selected_ids) == 0

    # Test Search / Filter
    view.search_entry.insert(0, "Song 1")
    view._on_search_changed()
    assert len(view._songs) == 1

    try:
        app.withdraw()
    except Exception:
        pass

