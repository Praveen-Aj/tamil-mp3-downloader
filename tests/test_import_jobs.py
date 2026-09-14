"""
Unit tests for Persistent Import Jobs and JobManager.
"""

from pathlib import Path
from unittest.mock import MagicMock
import pytest

from library.database import SQLiteDatabase
from library.models import ImportJob, ImportJobItem, JobStatus, ItemState
from library.jobs.job_manager import ImportJobManager
from library.url_resolver.base import ResolvedContent, TrackMeta, PlatformType, ContentType


@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_jobs.db"
    db = SQLiteDatabase(db_file)
    db.connect()
    yield db
    db.close()


def test_database_migration_3_tables_exist(temp_db):
    cursor = temp_db._conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('import_jobs', 'import_job_items')")
    tables = {row[0] for row in cursor.fetchall()}
    assert "import_jobs" in tables
    assert "import_job_items" in tables


def test_import_job_crud_operations(temp_db):
    job = ImportJob(
        id="job-test-123",
        url="https://open.spotify.com/playlist/test",
        platform="Spotify",
        content_type="Playlist",
        title="Test Tamil Hits",
        total_tracks=2,
        status=JobStatus.READY,
    )
    temp_db.create_import_job(job)

    fetched = temp_db.get_import_job("job-test-123")
    assert fetched is not None
    assert fetched.title == "Test Tamil Hits"
    assert fetched.status == JobStatus.READY

    items = [
        ImportJobItem(
            job_id="job-test-123",
            track_index=1,
            title="Track One",
            artist="Artist One",
            state=ItemState.READY,
            match_confidence=0.92,
        ),
        ImportJobItem(
            job_id="job-test-123",
            track_index=2,
            title="Track Two",
            artist="Artist Two",
            state=ItemState.NEEDS_REVIEW,
            match_confidence=0.74,
        ),
    ]
    temp_db.add_import_job_items(items)

    fetched_items = temp_db.get_import_job_items("job-test-123")
    assert len(fetched_items) == 2
    assert fetched_items[0].title == "Track One"
    assert fetched_items[1].state == ItemState.NEEDS_REVIEW

    # Test state update
    temp_db.update_import_job_item_state(fetched_items[0].id, ItemState.COMPLETED)
    updated_items = temp_db.get_import_job_items("job-test-123")
    assert updated_items[0].state == ItemState.COMPLETED

    # Test aggregate stats
    stats = temp_db.get_job_progress_stats("job-test-123")
    assert stats["TOTAL"] == 2
    assert stats.get("COMPLETED") == 1
    assert stats.get("NEEDS_REVIEW") == 1


def test_import_job_manager_analyzes_mock_url(temp_db):
    mock_detector = MagicMock()
    mock_detector.resolve.return_value = ResolvedContent(
        platform=PlatformType.SPOTIFY,
        content_type=ContentType.PLAYLIST,
        title="Mock Anirudh Hits",
        tracks=[
            TrackMeta(title="Hukum", artist="Anirudh Ravichander", duration_seconds=200, track_number=1),
            TrackMeta(title="Vanthendha", artist="Anirudh Ravichander", duration_seconds=180, track_number=2),
        ],
        raw_url="https://open.spotify.com/playlist/mock",
    )

    manager = ImportJobManager(db=temp_db, detector=mock_detector)
    job, items = manager.analyze_url("https://open.spotify.com/playlist/mock")

    assert job.title == "Mock Anirudh Hits"
    assert len(items) == 2
    assert items[0].title == "Hukum"
    assert items[1].title == "Vanthendha"

    # Verify persisted in database
    recent = temp_db.get_recent_import_jobs()
    assert len(recent) >= 1
    assert recent[0].id == job.id
