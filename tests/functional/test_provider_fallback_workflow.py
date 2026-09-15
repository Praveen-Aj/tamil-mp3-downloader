"""Functional test for multi-source and multi-provider failover."""

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
def test_fallback_to_second_source_when_first_returns_404(tmp_path: Path, http_server: str):
    """Test that when Source 1 fails with 404, the downloader falls back to Source 2 and succeeds."""
    db_path = tmp_path / "fallback.db"
    dl_dir = tmp_path / "downloads"
    dl_dir.mkdir(parents=True, exist_ok=True)

    db = SQLiteDatabase(db_path)
    db.connect()
    service = LibraryService(db=db, download_dir=str(dl_dir))

    song_id = db.add_song(
        LibrarySong(
            title="Vaathi Coming",
            artist="Anirudh",
            album="Master",
            state=SongState.NEW,
        )
    )

    # Broken source (404)
    db.add_source(
        SongSource(
            song_id=song_id,
            source_name="BrokenScraper",
            source_url=f"{http_server}/not-found.mp3",
            quality_kbps=320,
            is_available=True,
        )
    )
    # Working fallback source
    db.add_source(
        SongSource(
            song_id=song_id,
            source_name="WorkingBackup",
            source_url=f"{http_server}/valid-song.mp3",
            quality_kbps=128,
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

    # Song state updated to OWNED
    song = db.get_song(song_id)
    assert song is not None
    assert song.state == SongState.OWNED
    assert song.file_path == str(target_file)
