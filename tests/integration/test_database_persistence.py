"""Integration tests for SQLiteDatabase persistence and DownloadRegistry state lifecycle."""

from pathlib import Path
import pytest
from library.database import SQLiteDatabase
from library.registry import DownloadRegistry
from library.models import LibrarySong, SongSource, SongState, DownloadState


@pytest.mark.integration
def test_full_database_song_crud(tmp_path: Path):
    db = SQLiteDatabase(tmp_path / "crud.db")
    db.connect()

    # Create
    song = LibrarySong(
        title="Test Song",
        artist="Test Artist",
        album="Test Album",
        year=2024,
        state=SongState.NEW,
    )
    song_id = db.add_song(song)
    assert song_id > 0

    # Read
    fetched = db.get_song(song_id)
    assert fetched is not None
    assert fetched.title == "Test Song"
    assert fetched.artist == "Test Artist"

    # Update state & file
    db.update_song_state(song_id, SongState.QUEUED)
    updated = db.get_song(song_id)
    assert updated.state == SongState.QUEUED

    # Delete
    deleted = db.delete_song(song_id)
    assert deleted is True
    assert db.get_song(song_id) is None


@pytest.mark.integration
def test_registry_prevents_fake_completion_if_file_missing(tmp_path: Path):
    """Verify registry.complete() marks download as FAILED if file does not exist on disk."""
    db = SQLiteDatabase(tmp_path / "test_reg.db")
    db.connect()
    registry = DownloadRegistry(db)

    song_id = db.add_song(LibrarySong(title="Fake Song", artist="Fake Artist", state=SongState.NEW))
    src_id = db.add_source(SongSource(song_id=song_id, source_name="Test", source_url="http://fake.url"))

    dl_id = registry.acquire(song_id=song_id, song_source_id=src_id)
    assert dl_id is not None

    fake_file = tmp_path / "non_existent.mp3"

    registry.complete(
        song_id=song_id,
        download_id=dl_id,
        file_path=str(fake_file),
        file_size_bytes=1000,
        quality_kbps=320,
        library_location_id=1,
    )

    # Song state must NOT be OWNED; it must be transitioned to FAILED
    song = db.get_song(song_id)
    assert song.state != SongState.OWNED
    assert song.state == SongState.FAILED
