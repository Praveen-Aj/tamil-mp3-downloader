import pytest
from unittest.mock import MagicMock
from library.batch_manager import BatchDownloadManager, BatchDownloadJob


class DummyService:
    def __init__(self):
        self.emitted = []
        self.db = MagicMock()
        self.db._lock = MagicMock()
        self.db._conn = MagicMock()
        self.db.get_download = MagicMock(return_value=None)
        self.db.get_song = MagicMock(return_value=None)

    def emit_progress(self, event):
        self.emitted.append(event)


def test_batch_creation_and_stats():
    service = DummyService()
    manager = BatchDownloadManager(service)

    batch = manager.create_batch(
        batch_id="batch-test-1",
        title="Test Batch",
        source_type="spotify",
        child_download_ids=[101, 102, 103],
    )

    assert batch.batch_id == "batch-test-1"
    assert batch.total_tracks == 3
    assert batch.completed == 0
    assert batch.active == 0
    assert batch.queued == 3
    assert batch.overall_percentage == 0.0
    assert batch.status == "in_progress"

    # Track started
    manager.on_track_started("batch-test-1", 101, "Song Alpha")
    assert batch.active == 1
    assert batch.queued == 2
    assert batch.current_track == "Song Alpha"

    # Track completed
    manager.on_track_completed("batch-test-1", 101)
    assert batch.completed == 1
    assert batch.active == 0
    assert batch.queued == 2
    assert round(batch.overall_percentage, 1) == 33.3


def test_cancel_track_does_not_cancel_batch():
    service = DummyService()
    mock_dl = MagicMock()
    mock_dl.id = 101
    mock_dl.song_id = 501
    mock_dl.state = "DOWNLOADING"
    service.db.get_download.return_value = mock_dl

    manager = BatchDownloadManager(service)
    batch = manager.create_batch(
        batch_id="batch-cancel-trk",
        title="Test Track Cancel",
        source_type="movies",
        child_download_ids=[101, 102, 103],
    )

    manager.on_track_started(batch.batch_id, 101, "Track One")
    assert batch.active == 1

    # Cancel only track 101
    res = manager.cancel_track(101)
    assert res is True
    assert 101 in batch.cancelled_ids
    assert batch.is_cancelled is False  # Batch is NOT cancelled
    assert batch.status == "in_progress"  # Batch stays in progress
    assert batch.active == 0


def test_cancel_batch_cancels_active_and_queued():
    service = DummyService()
    mock_dl = MagicMock()
    mock_dl.id = 201
    mock_dl.song_id = 601
    mock_dl.state = "DOWNLOADING"
    service.db.get_download.return_value = mock_dl

    manager = BatchDownloadManager(service)
    batch = manager.create_batch(
        batch_id="batch-cancel-all",
        title="Test Batch Cancel",
        source_type="artist",
        child_download_ids=[201, 202, 203],
    )

    manager.on_track_started(batch.batch_id, 201, "Active Track")

    # Cancel entire batch
    res = manager.cancel_batch("batch-cancel-all")
    assert res is True
    assert batch.is_cancelled is True
    assert batch.status == "cancelled"
    assert 201 in batch.cancelled_ids
    assert 202 in batch.cancelled_ids
    assert 203 in batch.cancelled_ids
    assert batch.queued == 0
    assert batch.active == 0
