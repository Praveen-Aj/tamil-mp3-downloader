"""Functional test for single-song download workflow with real filesystem validation."""

from pathlib import Path
import pytest
from library.database import SQLiteDatabase
from ui.services.library_service import LibraryService
from library.models import LibrarySong, SongSource, SongState
from tests.fixtures_helper import LocalTestServer


@pytest.fixture(scope="module")
def http_server():
    server = LocalTestServer()
    base_url = server.start()
    yield base_url
    server.shutdown()


@pytest.mark.functional
def test_execute_single_download_creates_real_file(tmp_path: Path, http_server: str):
    """Test full functional path: execute_single_download -> real audio file created -> song marked OWNED."""
    db_path = tmp_path / "functional.db"
    dl_dir = tmp_path / "downloads"
    dl_dir.mkdir(parents=True, exist_ok=True)

    db = SQLiteDatabase(db_path)
    db.connect()
    service = LibraryService(db=db, download_dir=str(dl_dir))

    # Add song and valid source pointing to local test server
    song_id = db.add_song(
        LibrarySong(
            title="Arabic Kuthu",
            artist="Anirudh Ravichander",
            album="Beast",
            state=SongState.NEW,
        )
    )
    db.add_source(
        SongSource(
            song_id=song_id,
            source_name="LocalTest",
            source_url=f"{http_server}/valid-song.mp3",
            quality_kbps=320,
            is_available=True,
        )
    )

    success = service.execute_single_download(song_id)

    assert success is True
    # Verify file physically exists on disk
    downloaded_files = list(dl_dir.glob("**/*.mp3"))
    assert len(downloaded_files) == 1
    target_file = downloaded_files[0]
    assert target_file.exists()
    assert target_file.stat().st_size > 0

    # Verify song state in database
    song = db.get_song(song_id)
    assert song is not None
    assert song.state == SongState.OWNED
    assert song.file_path == str(target_file)

    # Verify dashboard stats reflect real file
    stats = service.get_dashboard_stats()
    assert stats["owned_songs"] == 1
    assert stats["storage_mb"] > 0
