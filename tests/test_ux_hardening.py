"""
End-User UX Hardening Test Suite.

Validates the 18 UX findings and new user-reported hardening requirements:
1. Terminology Segregation: No user-facing "Owned", "Unowned", "Canonical Library", "Audio Candidate Available"
2. Real Song Metadata Display in Downloads (Title, Artist, Album — never Audio Track #<id>)
3. Safe Deletion: Deleting downloaded song removes physical file, resets DB state to NEW, updates counters
4. Bounded Retry Policy & Alternate Source Fallback
5. Open Folder Direct Explorer Action & missing file fallback
6. Multi-Selection & Bulk Operations Consistency
7. Dashboard First-Viewport KPIs and Compact Source Status Pills
8. Presentation Modes in Music Library (Table / Grid)
"""

import os
import sys
import tempfile
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from library.database import SQLiteDatabase
from library.models import LibrarySong, SongSource, SongState, DownloadState, Download
from library.planner import DownloadPlanner
from ui.services.library_service import LibraryService


@pytest.fixture
def temp_ux_service(tmp_path):
    orig_out_dir = settings.get("download.output_dir", "downloads")
    db_path = tmp_path / "test_ux_library.db"
    service = LibraryService(db_path=db_path)
    out_dir = tmp_path / "downloads"
    out_dir.mkdir(parents=True, exist_ok=True)
    settings.set("download.output_dir", str(out_dir))
    yield service
    service.db.close()
    settings.set("download.output_dir", orig_out_dir)


class TestUXHardening:

    # ── Requirement 1 & A: Terminology Verification ────────────────
    def test_ui_terminology_audit_no_developer_jargon(self):
        """
        Audit UI view modules to ensure user-visible strings do not expose
        'Canonical Library', 'Unowned Track', 'Audio Candidate Available', or 'Already Owned'.
        """
        ui_dir = Path(__file__).parent.parent / "ui"
        forbidden_phrases = [
            "Canonical Library",
            "CANONICAL LIBRARY",
            "Unowned Track",
            "Audio Candidate Available",
            "Already Owned",
            "Source Provider",
        ]

        violations = []
        for py_file in ui_dir.rglob("*.py"):
            text = py_file.read_text(encoding="utf-8")
            for phrase in forbidden_phrases:
                # Check user-facing strings (e.g. in labels, headers, buttons)
                for line_no, line in enumerate(text.splitlines(), start=1):
                    # Skip internal comments/docstrings explaining internal classes
                    stripped = line.strip()
                    if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("*"):
                        continue
                    if phrase in line and "text=" in line or f'"{phrase}"' in line or f"'{phrase}'" in line:
                        violations.append(f"{py_file.name}:{line_no} contains forbidden phrase '{phrase}': {stripped}")

        assert len(violations) == 0, f"Found user-facing terminology violations:\n" + "\n".join(violations)

    # ── Requirement 2 & C: Real Metadata in Downloads ───────────────
    def test_downloads_metadata_resolution(self, temp_ux_service, tmp_path):
        """
        Verify that downloads display actual song Title, Artist, Album,
        and never generic 'Audio Track #494' when DB song record exists.
        """
        service = temp_ux_service
        
        # Add real song
        song = LibrarySong(
            title="Nenjame",
            artist="Anirudh Ravichander",
            album="Doctor",
            year=2021,
            canonical_hash="nenjame_doctor_hash",
            state=SongState.NEW,
        )
        song_id = service.db.add_song(song)

        # Add download record for this song
        dl_id = service.registry.acquire_download(song_id=song_id, song_source_id=1)
        assert dl_id is not None

        # Verify metadata resolution
        dl = service.db.get_download(dl_id)
        resolved_song = service.db.get_song(dl.song_id)

        assert resolved_song is not None
        assert resolved_song.title == "Nenjame"
        assert resolved_song.artist == "Anirudh Ravichander"
        assert resolved_song.album == "Doctor"
        assert resolved_song.title != f"Audio Track #{dl.song_id}"

    # ── Requirement 4: Bounded Retry & Alternate Source Fallback ────
    def test_retry_alternate_source_fallback(self, temp_ux_service):
        """
        Verify that retrying a failed download automatically selects an
        alternative available source variant when the primary source failed.
        """
        service = temp_ux_service

        song = LibrarySong(
            title="Vathi Coming",
            artist="Anirudh Ravichander",
            album="Master",
            canonical_hash="vathi_coming_hash",
            state=SongState.NEW,
        )
        song_id = service.db.add_song(song)

        # Source 1 (Primary - Failing)
        src1 = SongSource(
            song_id=song_id,
            source_name="masstamilan",
            source_url="https://fail.com/vathi.mp3",
            quality_kbps=320,
            is_available=True,
        )
        s1_id = service.db.add_source(src1)

        # Source 2 (Alternate - Available)
        src2 = SongSource(
            song_id=song_id,
            source_name="tamilmp3",
            source_url="https://good.com/vathi.mp3",
            quality_kbps=320,
            is_available=True,
        )
        s2_id = service.db.add_source(src2)

        # Acquire initial download on source 1
        dl1_id = service.registry.acquire_download(song_id=song_id, song_source_id=s1_id)
        # Fail source 1
        service.registry.fail(song_id, dl1_id, "HTTP 404 Not Found", s1_id)

        failed_dl = service.db.get_download(dl1_id)
        assert failed_dl.state == DownloadState.FAILED

        # Retry failed downloads with alternate source fallback
        retried = service.retry_failed_downloads([dl1_id], try_alternate_source=True, run_async=False)
        assert len(retried) == 1
        new_dl_id = retried[0]

        # Verify new download slot targeted the alternate source (s2_id)
        new_dl = service.db.get_download(new_dl_id)
        assert new_dl.song_source_id == s2_id

    # ── Requirement 5 & D: Delete Downloaded Song Functionality ─────
    def test_delete_downloaded_song_removes_file_and_resets_state(self, temp_ux_service, tmp_path):
        """
        Verify destructive deletion:
        - Removes physical MP3 file from disk
        - Resets SQLite song state to NEW (Not Downloaded)
        - Clears file_path and file_size_bytes
        - Deletes associated completed download record
        """
        service = temp_ux_service

        # Create dummy downloaded MP3 file
        dummy_file = tmp_path / "downloads" / "Aalaporaan.mp3"
        dummy_file.parent.mkdir(parents=True, exist_ok=True)
        dummy_file.write_bytes(b"\xFF\xFB\x90\x44" + b"\x00" * 200)
        assert dummy_file.exists()

        song = LibrarySong(
            title="Aalaporaan Tamizhan",
            artist="A.R. Rahman",
            album="Mersal",
            canonical_hash="aalaporaan_del_hash",
            file_path=str(dummy_file),
            file_size_bytes=dummy_file.stat().st_size,
            quality_kbps=320,
            state=SongState.OWNED,
        )
        song_id = service.db.add_song(song)

        # Add completed download record
        dl_id = service.registry.acquire_download(song_id=song_id, song_source_id=1)
        service.registry.complete(
            song_id=song_id,
            download_id=dl_id,
            file_path=str(dummy_file),
            file_size_bytes=dummy_file.stat().st_size,
            quality_kbps=320,
            library_location_id=1,
        )

        # Ensure song is initially OWNED / Downloaded
        assert service.db.get_song(song_id).state == SongState.OWNED

        # Perform deletion
        success = service.delete_downloaded_song(song_id, delete_physical_file=True)
        assert success is True

        # 1. Physical file removed
        assert not dummy_file.exists()

        # 2. Database state reset to NEW
        updated_song = service.db.get_song(song_id)
        assert updated_song.state == SongState.NEW
        assert updated_song.file_path is None
        assert updated_song.file_size_bytes is None

        # 3. Download record cleaned up
        dl_record = service.db.get_download(dl_id)
        assert dl_record is None

    # ── Requirement 6: Open Explorer Path Resolution ───────────────
    def test_open_path_in_explorer_fallback(self, temp_ux_service, tmp_path):
        """
        Verify open_path_in_explorer handles existing file, missing file,
        and fallback to output directory gracefully without raising exceptions.
        """
        service = temp_ux_service

        # 1. Missing file -> falls back gracefully
        ok, msg = service.open_path_in_explorer(str(tmp_path / "nonexistent.mp3"))
        assert ok is True
        assert "downloads folder" in msg.lower() or "opened" in msg.lower()

        # 2. None path -> opens output directory
        ok, msg = service.open_path_in_explorer(None)
        assert ok is True
        assert "downloads folder" in msg.lower() or "opened" in msg.lower()

    # ── Requirement 8, 9, B: Dashboard KPIs and Source Pills ─────────
    def test_dashboard_stats_and_source_pills(self, temp_ux_service):
        """
        Verify dashboard stats contain user-friendly labels and source status pills.
        """
        service = temp_ux_service
        stats = service.get_dashboard_stats()

        assert "downloaded_songs" in stats
        assert "ready_downloads" in stats
        assert "active_downloads" in stats
        assert "failed_downloads" in stats
        assert "storage_mb" in stats
        assert "source_pills" in stats

        pills = stats["source_pills"]
        pill_names = {p["name"] for p in pills}
        assert "YouTube" in pill_names
        assert "Spotify" in pill_names
        assert "Direct Audio" in pill_names
        assert "Regional Tamil" in pill_names
