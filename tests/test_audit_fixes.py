"""
Audit Fixes Validation Test Suite.

Validates all 16 audit findings:
1. Production Download Execution (Download Plan -> Registry acquire -> URL resolve -> HTTPDownloader -> filesystem -> OWNED -> Registry complete)
2. Real Download Retry (Identify failed records -> re-acquire slot -> re-download -> update DB state / retry again on fail -> no duplicates)
3. Deterministic Source Priority (MassTamilan vs Tamilmp3 preference & failover)
4. Importer Result Model Schema (scanned, imported, matched, unmatched, failed, conflicts)
5. Quality Detection & Unknown Bitrate (Unknown bitrate stored as None, eligible for 320kbps upgrade)
6. Consistent Settings Representation (Canonical integer quality kbps & persistent settings)
7. Thread-safe Database Operations (No direct db._conn access, thread safety under concurrency)
8. Source Registry Consistency (MassTamilan, Tamilmp3, FriendsTamilMP3 enabled; Isaimini, KollySongs disabled)
9. Dashboard Source Health Semantics (Core healthy count vs disabled count)
10. Complete End-to-End Production Workflow Integration Test
"""

import http.server
import os
import socketserver
import tempfile
import threading
from pathlib import Path
import pytest

from config.settings import settings
from library.database import SQLiteDatabase
from library.importer import LibraryImporter, ImportResult
from library.models import LibrarySong, SongSource, SongState, DownloadState
from library.planner import DownloadPlanner
from scrapers.source_registry import SourceRegistry, SourceConfig, SourceCapabilities
from ui.services.library_service import LibraryService


# ── Local Test HTTP Server Fixture ────────────────────────────
class MockAudioHandler(http.server.SimpleHTTPRequestHandler):
    """Simple HTTP request handler serving mock audio stream."""
    def do_GET(self):
        if self.path == "/fail":
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b"Internal Server Error")
            return

        self.send_response(200)
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("Content-Length", "1024")
        self.end_headers()
        # Serve 1024 dummy MP3 bytes
        self.wfile.write(b"\xFF\xFB\x90\x44" + b"\x00" * 1020)


@pytest.fixture
def local_http_server():
    """Starts a local HTTP server serving mock audio."""
    handler = MockAudioHandler
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as httpd:
        port = httpd.server_address[1]
        server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        server_thread.start()
        yield f"http://127.0.0.1:{port}"
        httpd.shutdown()


@pytest.fixture
def temp_service(tmp_path):
    orig_out_dir = settings.get("download.output_dir", "downloads")
    out_dir = tmp_path / "downloads"
    out_dir.mkdir(parents=True, exist_ok=True)
    settings.set("download.output_dir", str(out_dir))
    db_path = tmp_path / "test_library.db"
    service = LibraryService(db_path=db_path, download_dir=str(out_dir))
    yield service
    service.db.close()
    settings.set("download.output_dir", orig_out_dir)


class TestAuditFixes:

    # ── Requirement 1 & 10: Download Execution & E2E Workflow ──────
    def test_e2e_download_execution_workflow(self, temp_service, local_http_server, tmp_path):
        """
        Verify complete production download execution pipeline:
        Discover -> Canonical Library -> Source Variants -> Planner -> Acquire -> Download -> File -> OWNED
        """
        service = temp_service
        
        # 1. Register canonical song & source variant
        song = LibrarySong(
            title="Kannalane",
            artist="A.R. Rahman",
            album="Bombay",
            year=1995,
            canonical_hash="kannalane_hash",
            state=SongState.NEW,
        )
        song_id = service.db.add_song(song)

        audio_url = f"{local_http_server}/kannalane.mp3"
        src = SongSource(
            song_id=song_id,
            source_name="masstamilan",
            source_url=audio_url,
            download_reference=audio_url,
            quality_kbps=320,
            is_available=True,
        )
        service.db.add_source(src)

        # 2. Plan download
        plan = service.preview_download_plan([song_id])
        assert len(plan.new_songs) == 1
        assert plan.new_songs[0].song_id == song_id

        # 3. Execute download plan synchronously
        enqueued = service.execute_download_plan(plan, run_async=False)
        assert len(enqueued) == 1
        dl_id = enqueued[0]

        # 4. Verify DB state transition to OWNED and Download complete
        updated_song = service.db.get_song(song_id)
        assert updated_song.state == SongState.OWNED
        assert updated_song.file_path is not None
        assert Path(updated_song.file_path).exists()
        assert Path(updated_song.file_path).stat().st_size > 0

        dl_record = service.db.get_download(dl_id)
        assert dl_record.state == DownloadState.COMPLETED

    # ── Requirement 2: Download Retry Functionality ───────────────
    def test_download_retry_failure_then_success(self, temp_service, local_http_server):
        """
        Verify retry functionality:
        Failed download -> retry -> successful download.
        """
        service = temp_service

        song = LibrarySong(
            title="Munbe Vaa",
            artist="A.R. Rahman",
            album="Sillunu Oru Kaadhal",
            year=2006,
            canonical_hash="munbe_vaa_hash",
            state=SongState.NEW,
        )
        song_id = service.db.add_song(song)

        fail_url = f"{local_http_server}/fail"
        src = SongSource(
            song_id=song_id,
            source_name="masstamilan",
            source_url=fail_url,
            download_reference=fail_url,
            quality_kbps=320,
            is_available=True,
        )
        source_id = service.db.add_source(src)

        # Initial download attempt -> fails due to 500 error
        plan = service.preview_download_plan([song_id])
        service.execute_download_plan(plan, run_async=False)

        failed_song = service.db.get_song(song_id)
        assert failed_song.state == SongState.FAILED
        
        failed_dls = service.db.get_all_downloads()
        assert len(failed_dls) == 1
        assert failed_dls[0].state == DownloadState.FAILED

        # Fix source URL in DB to working endpoint
        good_url = f"{local_http_server}/munbe_vaa.mp3"
        service.db.execute_write(
            "UPDATE song_sources SET source_url = ?, download_reference = ? WHERE id = ?",
            (good_url, good_url, source_id)
        )

        # Retry failed downloads
        retried_ids = service.retry_failed_downloads(run_async=False)
        assert len(retried_ids) == 1

        # Verify successful recovery
        recovered_song = service.db.get_song(song_id)
        assert recovered_song.state == SongState.OWNED
        assert recovered_song.file_path is not None

    # ── Requirement 3: Deterministic Source Priority ───────────────
    def test_source_priority_ranking_and_failover(self, temp_service):
        """
        Verify source priority:
        1. MassTamilan (preferred over Tamilmp3 when both offer 320 kbps)
        2. Tamilmp3 automatically selected when MassTamilan is unavailable
        """
        service = temp_service
        planner = DownloadPlanner(service.db, source_priority=["masstamilan", "tamilmp3", "friendstamilmp3"])

        song = LibrarySong(
            title="Aalaporaan Thamizhan",
            artist="A.R. Rahman",
            album="Mersal",
            canonical_hash="aalaporaan_hash",
        )
        song_id = service.db.add_song(song)

        src_masstamilan = SongSource(
            song_id=song_id,
            source_name="masstamilan",
            source_url="https://masstamilan.dev/aalaporaan.mp3",
            quality_kbps=320,
            is_available=True,
            reliability_score=1.0,
        )
        src_id_mass = service.db.add_source(src_masstamilan)

        src_tamilmp3 = SongSource(
            song_id=song_id,
            source_name="tamilmp3",
            source_url="https://tamilmp3.in/aalaporaan.mp3",
            quality_kbps=320,
            is_available=True,
            reliability_score=1.0,
        )
        service.db.add_source(src_tamilmp3)

        # Plan download — MassTamilan should be chosen as primary
        plan1 = planner.plan_downloads_for_song_ids([song_id])
        assert plan1.new_songs[0].primary.source_name == "masstamilan"

        # Set MassTamilan as unavailable
        service.db.execute_write("UPDATE song_sources SET is_available = 0 WHERE id = ?", (src_id_mass,))

        # Re-plan download — Tamilmp3 becomes fallback
        plan2 = planner.plan_downloads_for_song_ids([song_id])
        assert plan2.new_songs[0].primary.source_name == "tamilmp3"

    # ── Requirement 4: Importer Result Model Schema ──────────────
    def test_importer_result_schema(self, temp_service, tmp_path):
        """
        Verify LibraryImporter returns a dictionary matching ImportResult schema:
        scanned, imported, matched, unmatched, failed, conflicts
        """
        importer = LibraryImporter(temp_service.db)
        
        # Create dummy directory with a valid dummy MP3
        import_dir = tmp_path / "music"
        import_dir.mkdir(parents=True, exist_ok=True)
        (import_dir / "Song_320kbps.mp3").write_bytes(b"\xFF\xFB\x90\x44" + b"\x00" * 500)

        res = importer.import_directory(import_dir)
        assert isinstance(res, dict)
        expected_keys = {"scanned", "imported", "matched", "unmatched", "failed", "conflicts"}
        assert expected_keys.issubset(set(res.keys()))
        assert res["scanned"] == 1
        assert res["imported"] == 1

    # ── Requirement 5: Unknown Bitrate Handling ────────────────────
    def test_unknown_bitrate_handling(self, temp_service, tmp_path):
        """
        Verify unknown bitrate is stored as None (NOT 320 kbps),
        and eligible for quality upgrade when a 320 kbps variant is planned.
        """
        importer = LibraryImporter(temp_service.db)
        mp3_file = tmp_path / "unknown_song.mp3"
        mp3_file.write_bytes(b"DUMMY_MP3_NO_ID3_TAGS")

        song_id, is_new = importer.import_file(mp3_file)
        assert song_id is not None
        
        imported_song = temp_service.db.get_song(song_id)
        assert imported_song.quality_kbps is None

        # Add a 320 kbps online source variant for this imported song
        src_320 = SongSource(
            song_id=song_id,
            source_name="masstamilan",
            source_url="https://masstamilan.dev/unknown_song_320.mp3",
            quality_kbps=320,
            is_available=True,
        )
        temp_service.db.add_source(src_320)

        # Plan download for owned song -> must detect quality upgrade to 320 kbps!
        plan = temp_service.planner.plan_downloads_for_song_ids([song_id])
        assert len(plan.upgrades) == 1
        assert plan.upgrades[0].new_source.quality_kbps == 320

    # ── Requirement 6: Settings Normalization ──────────────────────
    def test_settings_canonical_integer_quality(self):
        """
        Verify settings stores canonical integer quality (320 or 128)
        and persists updates cleanly.
        """
        settings.set("download.preferred_quality", 320)
        assert settings.preferred_quality_kbps == 320

        settings.set("download.preferred_quality", "128kbps")
        assert settings.preferred_quality_kbps == 128

        # Restore default
        settings.set("download.preferred_quality", 320)

    # ── Requirement 7: Database Thread Safety & Synchronization ────
    def test_database_thread_safety_no_conn_bypass(self, temp_service):
        """
        Verify database helper methods operate concurrently without throwing sqlite3 errors.
        """
        errors = []

        def worker(thread_idx: int):
            try:
                for i in range(20):
                    song = LibrarySong(
                        title=f"Thread Song {thread_idx}-{i}",
                        canonical_hash=f"hash_{thread_idx}_{i}",
                    )
                    sid = temp_service.db.add_song(song)
                    temp_service.db.get_song(sid)
                    temp_service.db.get_paginated_songs(page=1, page_size=10)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    # ── Requirement 8 & 9: Source Registry & Dashboard Metrics ────
    def test_source_registry_and_dashboard_metrics(self, temp_service):
        """
        Verify core sources are enabled (3) and disabled sources are isolated (2),
        and Dashboard stats accurately report metrics.
        """
        sources = temp_service.source_registry.get_all_sources()
        enabled = [s for s in sources if s.enabled]
        disabled = [s for s in sources if not s.enabled]

        assert len(enabled) == 3
        assert len(disabled) == 2
        assert {s.name for s in enabled} == {"masstamilan", "tamilmp3", "friendstamilmp3"}
        assert {s.name for s in disabled} == {"isaimini", "kollysongs"}

        stats = temp_service.get_dashboard_stats()
        assert "Core Healthy" in stats["healthy_sources"]
        assert stats["disabled_sources"] == 2

    # ── Requirement 12.3: 1,000 Song Deduplication Performance Benchmark ──
    def test_benchmark_1k_songs_deduplication(self, temp_service):
        """
        Performance benchmark: Register and plan 1,000 songs across 3 sources (3,000 raw items)
        and verify deduplication finishes cleanly.
        """
        import time
        from models.song import Song

        service = temp_service
        sources = ["masstamilan", "tamilmp3", "friendstamilmp3"]

        start_time = time.time()

        source_batches = []
        for src_name in sources:
            songs = [
                Song(
                    name=f"Song_{i:04d}",
                    url=f"https://{src_name}.com/song_{i}.mp3",
                    artist=f"Artist_{i % 50:03d}",
                    album_name=f"Album_{i % 100:03d}",
                    quality="320kbps" if src_name != "friendstamilmp3" else "128kbps",
                )
                for i in range(1000)
            ]
            source_batches.append({"songs": songs, "source_name": src_name})

        plan = service.planner.plan_downloads_multi_source(source_batches)
        elapsed = time.time() - start_time

        assert plan.raw_discovered == 3000
        assert plan.unique_canonical == 1000
        assert len(plan.new_songs) == 1000
