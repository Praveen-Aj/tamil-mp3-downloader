"""End-to-end tests verifying full user journey and filesystem truth."""

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


@pytest.mark.e2e
def test_e2e_download_and_filesystem_truth(tmp_path: Path, http_server: str):
    """
    E2E Workflow:
    1. User adds/initiates download for a song.
    2. Download completes via real HTTP stream.
    3. Verify physical file exists on disk with non-zero size.
    4. Verify get_downloaded_songs() shows the song.
    5. User deletes the file.
    6. Verify file is removed from disk and get_downloaded_songs() no longer shows it.
    """
    db_path = tmp_path / "e2e.db"
    dl_dir = tmp_path / "downloads"
    dl_dir.mkdir(parents=True, exist_ok=True)

    db = SQLiteDatabase(db_path)
    db.connect()
    service = LibraryService(db=db, download_dir=str(dl_dir))

    # Step 1: Add song with source pointing to local test stream
    song_id = db.add_song(
        LibrarySong(
            title="E2E Masterpiece",
            artist="Maestro",
            album="Soundtrack",
            state=SongState.NEW,
        )
    )
    db.add_source(
        SongSource(
            song_id=song_id,
            source_name="LocalTestStream",
            source_url=f"{http_server}/valid-song.mp3",
            quality_kbps=320,
            is_available=True,
        )
    )

    # Step 2: Execute download
    success = service.execute_single_download(song_id)
    assert success is True

    # Step 3: Verify physical file on disk
    downloaded_songs = service.get_downloaded_songs()
    assert len(downloaded_songs) == 1
    song = downloaded_songs[0]
    assert song.file_path is not None
    audio_path = Path(song.file_path)
    assert audio_path.exists()
    assert audio_path.stat().st_size > 0

    # Step 4: Verify dashboard stats reflect physical storage
    stats = service.get_dashboard_stats()
    assert stats["owned_songs"] == 1
    assert stats["storage_mb"] > 0

    # Step 5: User deletes the downloaded file
    del_ok = service.delete_downloaded_song(song_id, delete_file_from_disk=True)
    assert del_ok is True

    # Step 6: Physical file removed and UI state reconciled
    assert not audio_path.exists()
    downloaded_after_del = service.get_downloaded_songs()
    assert len(downloaded_after_del) == 0

    stats_after = service.get_dashboard_stats()
    assert stats_after["owned_songs"] == 0
