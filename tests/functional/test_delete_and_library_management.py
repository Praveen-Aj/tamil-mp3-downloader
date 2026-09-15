"""Functional test for Delete File vs Remove from Library workflows."""

from pathlib import Path
import pytest
from library.database import SQLiteDatabase
from ui.services.library_service import LibraryService
from library.models import LibrarySong, SongState


@pytest.mark.functional
def test_delete_physical_file_removes_file_and_reconciles_db(tmp_path: Path):
    """Verify that deleting a file physically removes it from disk and reconciles DB."""
    db_path = tmp_path / "delete.db"
    dl_dir = tmp_path / "downloads"
    dl_dir.mkdir(parents=True, exist_ok=True)

    db = SQLiteDatabase(db_path)
    db.connect()
    service = LibraryService(db=db, download_dir=str(dl_dir))

    # Create a real audio file
    real_file = dl_dir / "SongToDelete.mp3"
    real_file.write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 300)
    assert real_file.exists()

    song_id = db.add_song(
        LibrarySong(
            title="Song To Delete",
            artist="Artist",
            state=SongState.OWNED,
            file_path=str(real_file),
        )
    )

    # Delete physical file
    success = service.delete_downloaded_song(song_id, delete_file_from_disk=True)
    assert success is True
    assert not real_file.exists()

    # Re-verify song in DB
    song = db.get_song(song_id)
    assert song is not None
    assert song.state == SongState.NEW
    assert song.file_path is None


@pytest.mark.functional
def test_remove_from_library_only_preserves_physical_file(tmp_path: Path):
    """Verify that removing from library keeps physical audio file intact."""
    db_path = tmp_path / "remove_lib.db"
    dl_dir = tmp_path / "downloads"
    dl_dir.mkdir(parents=True, exist_ok=True)

    db = SQLiteDatabase(db_path)
    db.connect()
    service = LibraryService(db=db, download_dir=str(dl_dir))

    real_file = dl_dir / "KeepMyFile.mp3"
    real_file.write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 300)
    assert real_file.exists()

    song_id = db.add_song(
        LibrarySong(
            title="Keep My File",
            artist="Artist",
            state=SongState.OWNED,
            file_path=str(real_file),
        )
    )

    # Remove from library without deleting file from disk
    success = service.delete_downloaded_song(song_id, delete_file_from_disk=False)
    assert success is True
    # Physical file MUST still exist!
    assert real_file.exists()
    assert real_file.stat().st_size > 0
