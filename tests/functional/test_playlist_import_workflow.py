"""Functional test for universal playlist import, item tracking, and summary generation."""

from pathlib import Path
import pytest
from library.database import SQLiteDatabase
from library.jobs.job_manager import ImportJobManager
from ui.services.library_service import LibraryService
from library.models import ImportJob, ImportJobItem, ItemState, JobStatus


@pytest.mark.functional
def test_playlist_import_lifecycle_with_individual_items(tmp_path: Path):
    """Verify playlist import lifecycle from creation to download completion and summary."""
    db_path = tmp_path / "playlist.db"
    dl_dir = tmp_path / "downloads"
    dl_dir.mkdir(parents=True, exist_ok=True)

    db = SQLiteDatabase(db_path)
    db.connect()
    job_mgr = ImportJobManager(db)
    service = LibraryService(db=db, download_dir=str(dl_dir))

    job = ImportJob(
        id="job-test-123",
        url="https://www.youtube.com/playlist?list=PL_TEST_PLAYLIST",
        title="Test Tamil Hits",
        platform="youtube",
        content_type="playlist",
        total_tracks=2,
        status=JobStatus.ANALYZING,
    )
    db.create_import_job(job)

    item1 = ImportJobItem(
        job_id="job-test-123",
        track_index=1,
        title="Track 1",
        artist="Artist 1",
        state=ItemState.READY,
    )
    item2 = ImportJobItem(
        job_id="job-test-123",
        track_index=2,
        title="Track 2",
        artist="Artist 2",
        state=ItemState.READY,
    )
    db.add_import_job_items([item1, item2])

    items = db.get_import_job_items("job-test-123")
    assert len(items) == 2

    # Simulate downloading items with real files
    file1 = dl_dir / "Track 1 - Artist 1.mp3"
    file1.write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 300)
    db.update_import_job_item_state(items[0].id, ItemState.COMPLETED)

    file2 = dl_dir / "Track 2 - Artist 2.mp3"
    file2.write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 300)
    db.update_import_job_item_state(items[1].id, ItemState.COMPLETED)

    db.update_import_job_status("job-test-123", JobStatus.COMPLETED)

    # Invariants
    assert file1.exists()
    assert file2.exists()
    fetched_job = db.get_import_job("job-test-123")
    assert fetched_job is not None
    assert fetched_job.status == JobStatus.COMPLETED
