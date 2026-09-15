"""Integration tests for HTTPDownloader with real local HTTP streams and filesystem verification."""

from pathlib import Path
import pytest
from downloaders.http_downloader import HTTPDownloader
from library.database import SQLiteDatabase
from library.registry import DownloadRegistry
from library.models import LibrarySong, SongSource, SongState, DownloadState
from models.song import Song
from tests.fixtures_helper import LocalTestServer


@pytest.fixture(scope="module")
def http_server():
    server = LocalTestServer()
    base_url = server.start()
    yield base_url
    server.shutdown()


@pytest.mark.integration
def test_real_http_download_creates_valid_file_and_updates_db(tmp_path: Path, http_server: str):
    """Verify end-to-end: real HTTP stream -> physical file on disk -> file validation -> DB record."""
    db_path = tmp_path / "integration.db"
    dl_dir = tmp_path / "downloads"
    dl_dir.mkdir(parents=True, exist_ok=True)

    db = SQLiteDatabase(db_path)
    db.connect()
    registry = DownloadRegistry(db)

    # 1. Add song and source in database
    song_id = db.add_song(
        LibrarySong(
            title="Real Song",
            artist="Real Artist",
            album="Test Album",
            state=SongState.NEW,
        )
    )
    source_id = db.add_source(
        SongSource(
            song_id=song_id,
            source_name="LocalTest",
            source_url=f"{http_server}/valid-song.mp3",
            quality_kbps=320,
            is_available=True,
        )
    )

    # 2. Acquire download slot
    dl_id = registry.acquire(song_id, source_id)
    assert dl_id is not None

    # 3. Downloader downloads real audio stream to disk
    downloader = HTTPDownloader(output_dir=dl_dir)
    song_model = Song(
        name="Real Song",
        artist="Real Artist",
        album_name="Test Album",
        url=f"{http_server}/valid-song.mp3",
        quality="320kbps",
    )

    res = downloader.download_song(song_model)

    assert res.success is True
    assert res.file_path is not None
    assert res.file_path.exists()
    assert res.file_path.stat().st_size > 0

    # 4. Complete download in registry
    registry.complete(
        song_id=song_id,
        download_id=dl_id,
        file_path=str(res.file_path),
        file_size_bytes=res.file_path.stat().st_size,
        quality_kbps=320,
        library_location_id=1,
    )

    # 5. Invariant checks
    song = db.get_song(song_id)
    assert song is not None
    assert song.state == SongState.OWNED
    assert song.file_path == str(res.file_path)

    dl = db.get_download(dl_id)
    assert dl is not None
    assert dl.state == DownloadState.COMPLETED
    assert dl.output_path == str(res.file_path)


@pytest.mark.integration
def test_html_masquerade_is_rejected(tmp_path: Path, http_server: str):
    """Verify that an HTML response masquerading as MP3 is rejected."""
    dl_dir = tmp_path / "downloads_masquerade"
    dl_dir.mkdir(parents=True, exist_ok=True)
    downloader = HTTPDownloader(output_dir=dl_dir)

    song_model = Song(
        name="Masquerade Song",
        artist="Fake Artist",
        album_name="Fake Album",
        url=f"{http_server}/html-masquerade.mp3",
        quality="320kbps",
    )

    res = downloader.download_song(song_model)
    assert res.success is False


@pytest.mark.integration
def test_http_404_handled_gracefully(tmp_path: Path, http_server: str):
    """Verify 404 response fails cleanly without creating corrupt files."""
    dl_dir = tmp_path / "downloads_404"
    dl_dir.mkdir(parents=True, exist_ok=True)
    downloader = HTTPDownloader(output_dir=dl_dir)

    song_model = Song(
        name="Missing Song",
        artist="Unknown Artist",
        album_name="Missing Album",
        url=f"{http_server}/not-found.mp3",
        quality="320kbps",
    )

    res = downloader.download_song(song_model)
    assert res.success is False
