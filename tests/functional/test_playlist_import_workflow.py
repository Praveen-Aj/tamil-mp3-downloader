"""Functional test for universal playlist import, item tracking, and summary generation."""

from pathlib import Path
import pytest
from library.database import SQLiteDatabase
from library.jobs.job_manager import ImportJobManager
from ui.services.library_service import LibraryService
from library.models import ImportJob, ImportJobItem, ItemState, JobStatus
from tests.fixtures_helper import LocalTestServer


@pytest.fixture(scope="module")
def http_server():
    server = LocalTestServer()
    base_url = server.start()
    yield base_url
    server.shutdown()


@pytest.mark.functional
def test_playlist_import_lifecycle_with_individual_items(tmp_path: Path, http_server: str):
    """Verify playlist import lifecycle from creation to actual streaming download completion and summary."""
    db_path = tmp_path / "playlist.db"
    dl_dir = tmp_path / "downloads"
    dl_dir.mkdir(parents=True, exist_ok=True)

    db = SQLiteDatabase(db_path)
    db.connect()
    service = LibraryService(db=db, download_dir=str(dl_dir))

    job = ImportJob(
        id="job-test-123",
        url="https://www.youtube.com/playlist?list=PL_TEST_PLAYLIST",
        title="Test Tamil Hits",
        platform="youtube",
        content_type="playlist",
        total_tracks=2,
        status=JobStatus.READY,
    )
    db.create_import_job(job)

    item1 = ImportJobItem(
        job_id="job-test-123",
        track_index=1,
        title="Track 1",
        artist="Artist 1",
        state=ItemState.READY,
        selected_provider="direct_http",
        selected_source_url=f"{http_server}/track1.mp3",
    )
    item2 = ImportJobItem(
        job_id="job-test-123",
        track_index=2,
        title="Track 2",
        artist="Artist 2",
        state=ItemState.READY,
        selected_provider="direct_http",
        selected_source_url=f"{http_server}/track2.mp3",
    )
    db.add_import_job_items([item1, item2])

    items = db.get_import_job_items("job-test-123")
    assert len(items) == 2

    # Execute actual streaming download through LibraryService and ImportJobManager
    summary = service.execute_import_job(job_id="job-test-123", run_async=False)
    assert summary["completed"] == 2
    assert summary["failed"] == 0

    # Verify physical files exist on disk with valid audio content
    files = list(dl_dir.glob("*.mp3")) + list(dl_dir.glob("*/*.mp3"))
    assert len(files) == 2
    for f in files:
        assert f.exists()
        assert f.stat().st_size > 0
        content = f.read_bytes()
        assert content.startswith(b"\xff\xfb") or content.startswith(b"ID3")

    # Verify database state after download
    items_after = db.get_import_job_items("job-test-123")
    assert all(i.state == ItemState.COMPLETED for i in items_after)

    fetched_job = db.get_import_job("job-test-123")
    assert fetched_job is not None
    assert fetched_job.status == JobStatus.COMPLETED

    # Verify canonical songs registered as OWNED
    owned_songs = service.get_downloaded_songs()
    assert len(owned_songs) == 2

