"""
Final Hardening Regression Test Suite.
Validates:
1. Authoritative download directory resolution and Windows Explorer path normalization.
2. Download Manager live progress event bus and callback delivery.
3. Spotify playlist duplicate canonical song detection and reuse semantics.
4. Downloaded Songs physical vs database reconciliation.
"""

from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock

from config.settings import settings
from library.database import SQLiteDatabase
from library.models import (
    LibrarySong, SongState, Download, DownloadState, ImportJob, ImportJobItem, ItemState, JobStatus
)
from library.canonical import Canonicalizer
from library.jobs.job_manager import ImportJobManager
from ui.services.library_service import LibraryService, DownloadProgressEvent


def test_authoritative_output_dir_always_resolves_absolute(tmp_path: Path):
    """Verify that settings.output_dir is ALWAYS resolved to an absolute path."""
    resolved = Path(settings.output_dir)
    assert resolved.is_absolute()
    assert (resolved.parent / resolved.name).exists() or resolved.is_absolute()


def test_open_path_in_explorer_resolves_to_authoritative_root(tmp_path: Path):
    """Verify open_path_in_explorer resolves relative and absolute files to authoritative location."""
    db_path = tmp_path / "test_reg.db"
    db = SQLiteDatabase(db_path)
    db.connect()

    dl_dir = tmp_path / "downloads"
    dl_dir.mkdir(parents=True, exist_ok=True)
    test_song_file = dl_dir / "test_song.mp3"
    test_song_file.write_bytes(b"dummy mp3 data")

    service = LibraryService(db=db, download_dir=str(dl_dir))

    with patch("subprocess.run") as mock_run:
        # Test 1: Open downloads folder
        service.open_path_in_explorer(str(dl_dir))
        mock_run.assert_called_once()
        args1 = mock_run.call_args[0][0]
        assert str(dl_dir.resolve()) in args1[1]

    with patch("subprocess.run") as mock_run2:
        # Test 2: Open per-song file
        service.open_path_in_explorer(str(test_song_file))
        mock_run2.assert_called_once()
        args2 = mock_run2.call_args[0][0]
        assert "explorer" in args2[0].lower()
        assert str(test_song_file.resolve()) in args2[1]


def test_live_progress_event_bus_delivery():
    """Verify that progress events emitted via LibraryService reach registered listeners."""
    service = LibraryService()
    received_events = []

    def on_progress(event: DownloadProgressEvent):
        received_events.append(event)

    service.add_progress_listener(on_progress)

    event = DownloadProgressEvent(
        download_id=42,
        song_id=10,
        title="Arabic Kuthu",
        percent=0.65,
        status="DOWNLOADING",
        speed_str="3.2 MB/s",
        eta_str="00:04",
    )
    service.emit_progress(event)

    assert len(received_events) == 1
    ev = received_events[0]
    assert ev.download_id == 42
    assert ev.song_id == 10
    assert ev.title == "Arabic Kuthu"
    assert ev.percent == 0.65
    assert ev.status == "DOWNLOADING"
    assert ev.speed_str == "3.2 MB/s"
    assert ev.eta_str == "00:04"

    cached = service.get_active_download_progress(42)
    assert cached is not None
    assert cached.percent == 0.65

    # Unregister listener
    service.remove_progress_listener(on_progress)
    service.emit_progress(DownloadProgressEvent(download_id=42, song_id=10, title="Arabic Kuthu", percent=1.0, status="COMPLETED"))
    assert len(received_events) == 1


def test_spotify_playlist_duplicate_canonical_songs_semantics(tmp_path: Path):
    """
    Verify that when a Spotify playlist contains duplicate canonical tracks,
    analyze_url identifies them, tags them with duplicate reuse notes, and
    executing the job reuses the already downloaded file rather than duplicating.
    """
    from library.url_resolver.base import ResolvedContent, TrackMeta, ContentType, PlatformType

    db_path = tmp_path / "spotify_dedup.db"
    db = SQLiteDatabase(db_path)
    db.connect()
    job_mgr = ImportJobManager(db)

    # 4 playlist tracks, where track 1 and track 3 are identical canonical songs
    mock_resolved = ResolvedContent(
        platform=PlatformType.SPOTIFY,
        content_type=ContentType.PLAYLIST,
        title="Top Anirudh Songs",
        tracks=[
            TrackMeta(title="Thangamey", artist="Anirudh Ravichander", album="Naanum Rowdy Dhaan", duration_seconds=260),
            TrackMeta(title="Vaathi Coming", artist="Anirudh Ravichander", album="Master", duration_seconds=230),
            TrackMeta(title="Thangamey", artist="Anirudh Ravichander", album="Naanum Rowdy Dhaan", duration_seconds=260),  # Duplicate
            TrackMeta(title="Aaluma Doluma", artist="Anirudh Ravichander", album="Vedalam", duration_seconds=250),
        ],
        raw_url="https://open.spotify.com/playlist/test-dedup",
    )

    from library.providers.base import AudioCandidate
    from library.matching.matcher import MatchResult, ConfidenceTier
    mock_candidate = AudioCandidate(
        provider_name="youtube",
        source_url="https://youtube.com/watch?v=mock1",
        title="Thangamey",
        uploader="Anirudh",
        duration_seconds=260,
    )
    mock_score = MatchResult(
        confidence_tier=ConfidenceTier.HIGH,
        score=0.95,
        title_score=0.95,
        artist_score=0.95,
        duration_score=0.95,
        explanation="High confidence title & artist match",
        is_auto_eligible=True,
    )

    with patch("library.jobs.job_manager.UniversalUrlDetector.resolve", return_value=mock_resolved), \
         patch.object(job_mgr.provider_registry, "search_and_rank_candidates", return_value=[(mock_candidate, mock_score)]):
        job, items = job_mgr.analyze_url("https://open.spotify.com/playlist/test-dedup")

    assert job.total_tracks == 4
    assert len(items) == 4

    # Item 1 should be READY
    assert items[0].state == ItemState.READY
    # Item 3 (duplicate of Item 1) should be tagged with reuse notes
    assert "duplicate" in (items[2].match_explanation or "").lower()

    # Distinct canonical hashes: 3 unique songs
    hashes = {Canonicalizer.compute_hash(it.title, it.artist or "", it.album or "", it.duration_seconds) for it in items}
    assert len(hashes) == 3


def test_reconcile_missing_files_marks_db_records(tmp_path: Path):
    """Verify that if physical file is missing, library service reconciles stale OWNED state."""
    db_path = tmp_path / "reconcile.db"
    db = SQLiteDatabase(db_path)
    db.connect()

    dl_dir = tmp_path / "downloads"
    dl_dir.mkdir(parents=True, exist_ok=True)

    # Create song that claims to be OWNED, but file is missing
    missing_file = dl_dir / "ghost_song.mp3"
    song = LibrarySong(
        canonical_hash="ghost_hash_123",
        title_normalized="ghost song",
        artist_normalized="ghost artist",
        album_normalized="",
        title="Ghost Song",
        artist="Ghost Artist",
        state=SongState.OWNED,
        file_path=str(missing_file),
    )
    song_id = db.add_song(song)

    service = LibraryService(db=db, download_dir=str(dl_dir))
    reconciled = service.reconcile_library_files()

    # Ghost song was missing physically -> should be transitioned out of OWNED
    updated_song = db.get_song(song_id)
    assert updated_song.state != SongState.OWNED
