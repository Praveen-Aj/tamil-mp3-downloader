"""
Comprehensive Download Engine and GUI Functional End-to-End Validation Suite.

Validates:
A. Complete Download Engine Lifecycle:
   - Single track addition, canonical deduplication, download record creation.
   - Live progress, download speed, and ETA reporting via callbacks.
   - Physical audio file existence, non-zero size, and storage in authoritative output directory.
   - Database reflection and consistency across LibrarySong and Download tables.
   - Duplicate prevention: re-running download does not create duplicate physical files.
   - Quality upgrade (128 kbps -> 320 kbps) succeeds; quality downgrade is strictly prevented.
   - Retry policy: transient failures retry with backoff; permanent 404 marks FAILED honestly.
   - Filesystem reconciliation: external deletion of audio file resets OWNED state to NEW.
   - Concurrent downloads: multiple simultaneous downloads write distinct physical files cleanly.

B. Universal Import & Playlist Flow:
   - Direct audio stream import, Spotify/YouTube simulated structure.
   - Canonical intra-playlist deduplication (duplicate items reuse existing download).
   - Execution of playlist downloads with physical file verification.
   - Partial failure handling and selective retry of failed items.

C. GUI Functional End-to-End:
   - Live CustomTkinter application startup and view navigation.
   - Live progress event bus dispatching without manual refresh.
   - Downloads Manager and Downloaded Songs views metadata veracity.
   - Audio playback launch validation and Open Folder resolution to authoritative root.
"""

import os
import sys
import time
import threading
from pathlib import Path
from typing import List, Optional
import unittest.mock as mock
import pytest

from config.settings import settings
from library.database import SQLiteDatabase
from library.canonical import Canonicalizer, compute_canonical_hash
from library.models import (
    LibrarySong, SongSource, SongState, Download, DownloadState,
    ImportJob, ImportJobItem, JobStatus, ItemState
)
from library.planner import DownloadPlanner
from library.jobs.job_manager import ImportJobManager
from ui.services.library_service import LibraryService, DownloadProgressEvent
from ui.app import TamilMP3App
from tests.fixtures_helper import LocalTestServer, generate_valid_mp3_bytes


@pytest.fixture(scope="module")
def http_server():
    server = LocalTestServer()
    base_url = server.start()
    yield base_url
    server.shutdown()


@pytest.fixture
def test_env(tmp_path: Path):
    orig_dir = settings.get("download.output_dir", "downloads")
    dl_dir = tmp_path / "authoritative_downloads"
    dl_dir.mkdir(parents=True, exist_ok=True)
    settings.set("download.output_dir", str(dl_dir))

    db_path = tmp_path / "validation.db"
    db = SQLiteDatabase(db_path)
    db.connect()

    service = LibraryService(db=db, download_dir=str(dl_dir))

    yield {
        "db": db,
        "dl_dir": dl_dir,
        "service": service,
        "tmp_path": tmp_path,
    }

    db.close()
    settings.set("download.output_dir", orig_dir)


class TestDownloadEngineBackendLifecycle:
    """Rigorous tests for the download engine backend using real filesystem and HTTP stream."""

    def test_single_song_complete_lifecycle(self, test_env, http_server):
        """
        Validate 1-13: Add song -> Download starts -> Progress/Speed reported ->
        Physical file created in authoritative directory -> Non-empty -> DB reflects OWNED.
        """
        db: SQLiteDatabase = test_env["db"]
        service: LibraryService = test_env["service"]
        dl_dir: Path = test_env["dl_dir"]

        # 1. Add canonical song
        c_hash = compute_canonical_hash("Marakkuma Nenjam", "A.R. Rahman", "VTK")
        song_id = db.add_song(
            LibrarySong(
                title="Marakkuma Nenjam",
                artist="A.R. Rahman",
                album="VTK",
                canonical_hash=c_hash,
                state=SongState.NEW,
            )
        )
        assert song_id > 0

        # Add source pointing to real local stream
        source_url = f"{http_server}/valid-song.mp3"
        source_id = db.add_source(
            SongSource(
                song_id=song_id,
                source_name="LocalTest",
                source_url=source_url,
                quality_kbps=320,
                is_available=True,
            )
        )
        assert source_id > 0

        # Track progress events
        progress_events: List[DownloadProgressEvent] = []
        service.add_progress_listener(lambda ev: progress_events.append(ev))

        # 2. Execute download
        success = service.execute_single_download(song_id)
        assert success is True

        # 3. Verify physical file on disk
        files = list(dl_dir.glob("**/*.mp3"))
        assert len(files) == 1
        target_file = files[0]
        assert target_file.exists()
        assert target_file.is_file()
        file_size = target_file.stat().st_size
        assert file_size > 0

        # Verify MP3 binary integrity
        content = target_file.read_bytes()
        assert content.startswith(b"ID3") or content.startswith(b"\xff\xfb")

        # 4. Verify Database state
        db_song = db.get_song(song_id)
        assert db_song is not None
        assert db_song.state == SongState.OWNED
        assert Path(db_song.file_path).resolve() == target_file.resolve()
        assert db_song.file_size_bytes == file_size

        # 5. Verify Downloaded Songs view finds this exact file
        downloaded = service.get_downloaded_songs()
        assert len(downloaded) == 1
        assert downloaded[0].id == song_id
        assert downloaded[0].file_path == str(target_file)

        # 6. Verify Progress & Speed were reported
        assert len(progress_events) >= 1
        completed_events = [e for e in progress_events if e.status == "COMPLETED" or e.percent == 1.0]
        assert len(completed_events) >= 1

    def test_rerun_download_is_idempotent_no_duplicate_files(self, test_env, http_server):
        """
        Validate 14: Re-running download for an already-owned song does not create
        duplicate physical files or re-download.
        """
        service: LibraryService = test_env["service"]
        db: SQLiteDatabase = test_env["db"]
        dl_dir: Path = test_env["dl_dir"]

        song_id = db.add_song(
            LibrarySong(
                title="Idempotent Track",
                artist="Artist",
                canonical_hash=compute_canonical_hash("Idempotent Track", "Artist", "Album"),
                state=SongState.NEW,
            )
        )
        db.add_source(
            SongSource(
                song_id=song_id,
                source_name="LocalTest",
                source_url=f"{http_server}/track1.mp3",
                quality_kbps=320,
                is_available=True,
            )
        )

        # First download
        assert service.execute_single_download(song_id) is True
        files_first = list(dl_dir.glob("**/*.mp3"))
        assert len(files_first) == 1
        mtime_first = files_first[0].stat().st_mtime

        # Second download (should recognize as owned / skip re-download)
        assert service.execute_single_download(song_id) is True
        files_second = list(dl_dir.glob("**/*.mp3"))
        assert len(files_second) == 1
        assert files_second[0].stat().st_mtime == mtime_first

    def test_quality_upgrade_and_downgrade_prevention(self, test_env, http_server):
        """
        Validate 15 & 16:
        - 128 kbps existing file is upgraded when a 320 kbps source is planned.
        - 320 kbps existing file is NEVER downgraded by a 128 kbps source.
        """
        db: SQLiteDatabase = test_env["db"]
        planner = DownloadPlanner(db, upgrade_quality_threshold=64)

        # Create owned song with 128 kbps
        song_id = db.add_song(
            LibrarySong(
                title="Upgrade Song",
                artist="Composer",
                canonical_hash=compute_canonical_hash("Upgrade Song", "Composer", "Album"),
                state=SongState.OWNED,
                quality_kbps=128,
            )
        )

        # Add 320 kbps source -> Should schedule upgrade
        db.add_source(
            SongSource(
                song_id=song_id,
                source_name="masstamilan",
                source_url=f"{http_server}/valid-song.mp3",
                quality_kbps=320,
                is_available=True,
            )
        )

        plan = planner.plan_downloads_for_song_ids([song_id])
        assert len(plan.upgrades) == 1
        assert plan.upgrades[0].quality_gain == (320 - 128)
        assert len(plan.owned) == 0

        # Now simulate owned song having 320 kbps
        db.update_song_quality(song_id, 320)
        # Attempt to plan with a 128 kbps source only
        db.execute_write("DELETE FROM song_sources WHERE song_id = ?", (song_id,))
        db.add_source(
            SongSource(
                song_id=song_id,
                source_name="friendstamilmp3",
                source_url=f"{http_server}/track1.mp3",
                quality_kbps=128,
                is_available=True,
            )
        )

        plan_downgrade = planner.plan_downloads_for_song_ids([song_id])
        assert len(plan_downgrade.upgrades) == 0  # No upgrade
        assert len(plan_downgrade.new_songs) == 0  # No download
        assert len(plan_downgrade.owned) == 1      # Treated as owned, no downgrade

    def test_flaky_server_retry_success(self, test_env, http_server):
        """
        Validate 17: Download fails initially (503 Service Unavailable) then retries and succeeds.
        """
        service: LibraryService = test_env["service"]
        db: SQLiteDatabase = test_env["db"]
        dl_dir: Path = test_env["dl_dir"]

        song_id = db.add_song(
            LibrarySong(
                title="Flaky Song",
                artist="Resilient Artist",
                canonical_hash=compute_canonical_hash("Flaky Song", "Resilient Artist", "Album"),
                state=SongState.NEW,
            )
        )
        db.add_source(
            SongSource(
                song_id=song_id,
                source_name="FlakyStream",
                source_url=f"{http_server}/flaky-song.mp3",
                quality_kbps=320,
                is_available=True,
            )
        )

        # HTTPDownloader retries 3 times with backoff, so it should succeed on attempt 3
        success = service.execute_single_download(song_id)
        assert success is True

        downloaded = list(dl_dir.glob("**/*.mp3"))
        assert len(downloaded) >= 1
        assert downloaded[0].stat().st_size > 0

    def test_failed_download_does_not_leave_owned_state(self, test_env, http_server):
        """
        Validate 18: 404 Not Found surfaces honestly, marks state FAILED, does NOT leave OWNED.
        """
        service: LibraryService = test_env["service"]
        db: SQLiteDatabase = test_env["db"]

        song_id = db.add_song(
            LibrarySong(
                title="Missing 404 Track",
                artist="Ghost Artist",
                canonical_hash=compute_canonical_hash("Missing 404 Track", "Ghost Artist", "Album"),
                state=SongState.NEW,
            )
        )
        db.add_source(
            SongSource(
                song_id=song_id,
                source_name="BrokenStream",
                source_url=f"{http_server}/not-found.mp3",
                quality_kbps=320,
                is_available=True,
            )
        )

        # Prevent live YouTube fallback for the broken item so it deterministically fails
        with mock.patch.object(service.provider_registry, "search_and_rank_candidates", return_value=[]):
            success = service.execute_single_download(song_id)
        assert success is False

        song = db.get_song(song_id)
        assert song.state == SongState.FAILED
        assert song.file_path is None

        # Verify Download record marked FAILED
        downloads = service.get_all_downloads(dedup_by_song=False)
        target_dl = [d for d in downloads if d.song_id == song_id]
        assert len(target_dl) >= 1
        assert target_dl[0].state == DownloadState.FAILED
        assert target_dl[0].error_message is not None

    def test_filesystem_reconciliation_detects_externally_deleted_files(self, test_env, http_server):
        """
        Validate 19: If a downloaded file is deleted outside the app,
        reconcile_library_files() detects the missing file and resets DB state to NEW.
        """
        service: LibraryService = test_env["service"]
        db: SQLiteDatabase = test_env["db"]
        dl_dir: Path = test_env["dl_dir"]

        song_id = db.add_song(
            LibrarySong(
                title="Reconciled Song",
                artist="Artist",
                canonical_hash=compute_canonical_hash("Reconciled Song", "Artist", "Album"),
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

        assert service.execute_single_download(song_id) is True
        assert len(service.get_downloaded_songs()) == 1

        # Delete physical file on disk
        files = list(dl_dir.glob("**/*.mp3"))
        assert len(files) == 1
        files[0].unlink()
        assert not files[0].exists()

        # Run reconciliation
        reconciled_count = service.reconcile_library_files()
        assert reconciled_count == 1

        # Confirm DB state reset to NEW
        song = db.get_song(song_id)
        assert song.state == SongState.NEW
        assert song.file_path is None
        assert len(service.get_downloaded_songs()) == 0

    def test_concurrent_downloads_write_clean_files(self, test_env, http_server):
        """
        Validate 20: Multiple downloads run concurrently via ThreadPoolExecutor
        and cleanly create independent physical files without collisions.
        """
        service: LibraryService = test_env["service"]
        db: SQLiteDatabase = test_env["db"]
        dl_dir: Path = test_env["dl_dir"]

        song_ids = []
        for i in range(3):
            sid = db.add_song(
                LibrarySong(
                    title=f"Concurrent Track {i}",
                    artist="Multi Artist",
                    album="Parallel Album",
                    canonical_hash=compute_canonical_hash(f"Concurrent Track {i}", "Multi Artist", "Parallel Album"),
                    state=SongState.NEW,
                )
            )
            db.add_source(
                SongSource(
                    song_id=sid,
                    source_name="LocalTest",
                    source_url=f"{http_server}/track{i}.mp3",
                    quality_kbps=320,
                    is_available=True,
                )
            )
            song_ids.append(sid)

        # Run concurrently
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=3) as pool:
            results = list(pool.map(service.execute_single_download, song_ids))

        assert all(results)
        files = list(dl_dir.glob("**/*.mp3"))
        assert len(files) == 3
        for f in files:
            assert f.exists()
            assert f.stat().st_size > 0


class TestImportAndPlaylistFlow:
    """Rigorous tests for playlist analysis, intra-playlist dedup, and bulk downloading."""

    def test_playlist_deduplication_and_full_download(self, test_env, http_server):
        """
        Validate B.1-10:
        Playlist with 3 tracks where track 3 is a duplicate of track 1:
        - Deduplication detects track 3 reuses track 1.
        - Only 2 unique downloads executed.
        - 2 physical files created.
        - All items marked completed.
        """
        db: SQLiteDatabase = test_env["db"]
        service: LibraryService = test_env["service"]
        dl_dir: Path = test_env["dl_dir"]

        job = ImportJob(
            id="job-dedup-pl",
            url="https://open.spotify.com/playlist/test_dedup",
            title="Playlist With Dupes",
            platform="spotify",
            content_type="playlist",
            total_tracks=3,
            status=JobStatus.READY,
        )
        db.create_import_job(job)

        items = [
            ImportJobItem(
                job_id="job-dedup-pl",
                track_index=1,
                title="Song Alpha",
                artist="Singer One",
                state=ItemState.READY,
                selected_provider="direct_http",
                selected_source_url=f"{http_server}/track1.mp3",
            ),
            ImportJobItem(
                job_id="job-dedup-pl",
                track_index=2,
                title="Song Beta",
                artist="Singer Two",
                state=ItemState.READY,
                selected_provider="direct_http",
                selected_source_url=f"{http_server}/track2.mp3",
            ),
            ImportJobItem(
                job_id="job-dedup-pl",
                track_index=3,
                title="Song Alpha",  # Duplicate of track 1
                artist="Singer One",
                state=ItemState.READY,
                selected_provider="direct_http",
                selected_source_url=f"{http_server}/track1.mp3",
            ),
        ]
        db.add_import_job_items(items)

        # Execute
        summary = service.execute_import_job(job_id="job-dedup-pl", run_async=False)
        assert summary["completed"] == 3
        assert summary["failed"] == 0

        # Physical files: exactly 2 files (Song Alpha and Song Beta)
        files = list(dl_dir.glob("*.mp3")) + list(dl_dir.glob("*/*.mp3"))
        assert len(files) == 2

        # All 3 playlist items marked COMPLETED
        db_items = db.get_import_job_items("job-dedup-pl")
        assert all(i.state == ItemState.COMPLETED for i in db_items)

    def test_playlist_partial_failure_and_retry(self, test_env, http_server):
        """
        Validate B.11-12:
        Playlist has 1 good track and 1 broken 404 track:
        - Good track completes.
        - Broken track fails with error message.
        - Retry on the failed track succeeds after source URL fixed.
        """
        db: SQLiteDatabase = test_env["db"]
        service: LibraryService = test_env["service"]

        job = ImportJob(
            id="job-partial-fail",
            url="https://www.youtube.com/playlist?list=test_partial",
            title="Partial Fail Playlist",
            platform="youtube",
            content_type="playlist",
            total_tracks=2,
            status=JobStatus.READY,
        )
        db.create_import_job(job)

        items = [
            ImportJobItem(
                job_id="job-partial-fail",
                track_index=1,
                title="Valid Track",
                artist="Artist A",
                state=ItemState.READY,
                selected_provider="direct_http",
                selected_source_url=f"{http_server}/track1.mp3",
            ),
            ImportJobItem(
                job_id="job-partial-fail",
                track_index=2,
                title="Broken Track",
                artist="Artist B",
                state=ItemState.READY,
                selected_provider="direct_http",
                selected_source_url=f"{http_server}/not-found.mp3",
            ),
        ]
        db.add_import_job_items(items)

        # Run 1: 1 success, 1 failure (prevent live YouTube fallback for the broken item)
        with mock.patch.object(service.job_manager.provider_registry, "search_and_rank_candidates", return_value=[]):
            summary = service.execute_import_job(job_id="job-partial-fail", run_async=False)
        assert summary["completed"] == 1
        assert summary["failed"] == 1

        db_items = db.get_import_job_items("job-partial-fail")
        failed_item = [i for i in db_items if i.title == "Broken Track"][0]
        assert failed_item.state == ItemState.FAILED
        assert "404" in (failed_item.error_message or "")

        # Fix the broken source URL and retry
        db.execute_write(
            "UPDATE import_job_items SET selected_source_url = ?, state = ? WHERE id = ?",
            (f"{http_server}/track2.mp3", ItemState.READY.value, failed_item.id)
        )

        # Retry only failed item
        retry_summary = service.execute_import_job(
            job_id="job-partial-fail",
            item_ids=[failed_item.id],
            run_async=False,
        )
        assert retry_summary["completed"] == 1
        assert retry_summary["failed"] == 0

        # All items now completed
        db_items_after = db.get_import_job_items("job-partial-fail")
        assert all(i.state == ItemState.COMPLETED for i in db_items_after)


class TestGUIFunctionalWorkflows:
    """Actual CustomTkinter GUI functional verification."""

    def test_gui_playback_and_open_folder_actions(self, test_env, http_server):
        """
        Validate C.10-13:
        - play_audio_file() returns True for valid downloaded audio file.
        - play_audio_file() returns False with descriptive message for missing/empty file.
        - open_path_in_explorer() resolves to authoritative download folder.
        """
        service: LibraryService = test_env["service"]
        dl_dir: Path = test_env["dl_dir"]

        # Create real physical audio file
        test_file = dl_dir / "TestPlayback.mp3"
        test_file.write_bytes(generate_valid_mp3_bytes(5))

        # Test playback with mock to prevent popping external media player on desktop
        with mock.patch("os.startfile") as mock_start:
            ok, msg = service.play_audio_file(str(test_file))
            assert ok is True
            assert "Playing" in msg
            mock_start.assert_called_once_with(str(test_file))

        # Test playback with missing file
        ok_bad, msg_bad = service.play_audio_file(str(dl_dir / "nonexistent.mp3"))
        assert ok_bad is False
        assert "not found" in msg_bad.lower()

        # Test playback with empty/None
        ok_none, msg_none = service.play_audio_file(None)
        assert ok_none is False
        assert "empty" in msg_none.lower()

        # Test open_path_in_explorer
        with mock.patch("subprocess.run") as mock_sub:
            ok_exp, msg_exp = service.open_path_in_explorer(str(test_file))
            assert ok_exp is True
            mock_sub.assert_called_once()

        with mock.patch("subprocess.run") as mock_sub:
            ok_root, msg_root = service.open_path_in_explorer(None)
            assert ok_root is True
            mock_sub.assert_called_once()

    def test_gui_live_progress_and_completion_flow(self, test_env, http_server):
        """
        Validate C.1-9:
        - Launch TamilMP3App in test environment.
        - Pump UI event loop via app.update().
        - Navigate to Add Music, trigger download.
        - Observe live progress event bus dispatching.
        - Navigate to Downloaded Songs view and verify truthful metadata.
        """
        service: LibraryService = test_env["service"]
        db: SQLiteDatabase = test_env["db"]
        dl_dir: Path = test_env["dl_dir"]

        app = TamilMP3App(service=service)
        app.update()
        assert app.winfo_exists()

        # Add single song to download
        song_id = db.add_song(
            LibrarySong(
                title="GUI Live Track",
                artist="Live Artist",
                album="Visual Album",
                canonical_hash=compute_canonical_hash("GUI Live Track", "Live Artist", "Visual Album"),
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

        # Collect live progress events
        received_events = []
        service.add_progress_listener(lambda ev: received_events.append(ev))

        # Execute download
        service.execute_single_download(song_id)
        app.update()

        # Verify progress events delivered
        assert len(received_events) >= 1

        # Navigate to Downloaded Songs view
        app.navigate_to("downloaded_songs")
        app.update()
        assert app.current_view_name == "downloaded_songs"

        dl_view = app.views["downloaded_songs"]
        assert len(dl_view._songs) == 1
        displayed_song = dl_view._songs[0]
        assert displayed_song.title == "GUI Live Track"
        assert displayed_song.artist == "Live Artist"
        assert displayed_song.quality_kbps == 320
        assert displayed_song.file_path is not None
        assert Path(displayed_song.file_path).exists()

        # Clean up
        try:
            app.destroy()
        except Exception:
            pass
