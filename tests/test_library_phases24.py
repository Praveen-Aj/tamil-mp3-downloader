"""
Tests for Phase 2–4: Discovery Pipeline, Download Planner, Download Registry.
"""

import pytest
import tempfile
from pathlib import Path

from library.database import SQLiteDatabase
from library.models import LibrarySong, SongSource, SongState
from library.discovery import DiscoveryPipeline, song_to_canonical, extract_quality_kbps, extract_file_size_bytes
from library.planner import DownloadPlanner, DownloadPlan
from library.registry import DownloadRegistry
from models.song import Song, Album


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_song(name="Test Song", url="https://example.com/test.mp3",
              quality="320kbps", size_mb=5.0, artist="Test Artist",
              album_title="Test Album", year=2020) -> Song:
    return Song(
        name=name,
        url=url,
        quality=quality,
        size_mb=size_mb,
        artist=artist,
        album_title=album_title,
        year=year,
    )


def make_db(tmp_path) -> SQLiteDatabase:
    db_path = tmp_path / "test_library.db"
    db = SQLiteDatabase(db_path)
    db.connect()
    return db


# ---------------------------------------------------------------------------
# Phase 2: Discovery Pipeline
# ---------------------------------------------------------------------------

class TestDiscoveryPipeline:

    def test_register_single_song(self, tmp_path):
        """Registering a song adds it to the library."""
        db = make_db(tmp_path)
        pipeline = DiscoveryPipeline(db)
        song = make_song()

        song_id = pipeline.register_song(song, "isaimini")
        assert song_id > 0

        retrieved = db.get_song(song_id)
        assert retrieved is not None
        assert retrieved.title == "Test Song"
        assert retrieved.state == SongState.NEW
        db.close()

    def test_register_same_song_twice_is_idempotent(self, tmp_path):
        """Registering the same song twice does not create a duplicate."""
        db = make_db(tmp_path)
        pipeline = DiscoveryPipeline(db)
        song = make_song()

        id1 = pipeline.register_song(song, "isaimini")
        id2 = pipeline.register_song(song, "isaimini")
        assert id1 == id2

        # Only one song in library
        stats = db.get_library_stats()
        assert stats["total_songs"] == 1
        db.close()

    def test_register_same_song_different_sources(self, tmp_path):
        """Same canonical song from different sources creates one library entry but two sources."""
        db = make_db(tmp_path)
        pipeline = DiscoveryPipeline(db)

        song1 = make_song(url="https://isaimini.com/song.mp3")
        song2 = make_song(url="https://masstamilan.com/song.mp3")

        id1 = pipeline.register_song(song1, "isaimini")
        id2 = pipeline.register_song(song2, "masstamilan")
        assert id1 == id2  # Same canonical song

        sources = db.get_sources_for_song(id1)
        assert len(sources) == 2
        source_names = {s.source_name for s in sources}
        assert "isaimini" in source_names
        assert "masstamilan" in source_names
        db.close()

    def test_register_batch(self, tmp_path):
        """Batch registration returns correct stats."""
        db = make_db(tmp_path)
        pipeline = DiscoveryPipeline(db)

        songs = [
            make_song("Song A", "https://example.com/a.mp3"),
            make_song("Song B", "https://example.com/b.mp3"),
            make_song("Song C", "https://example.com/c.mp3"),
        ]

        stats = pipeline.register_batch(songs, "isaimini")
        assert stats["total"] == 3
        assert stats["new"] == 3
        assert stats["existing"] == 0

        # Register again — all should be existing
        stats2 = pipeline.register_batch(songs, "isaimini")
        assert stats2["existing"] == 3
        assert stats2["new"] == 0
        db.close()

    def test_discovery_context_recorded(self, tmp_path):
        """Discovery context is recorded when registering songs."""
        db = make_db(tmp_path)
        pipeline = DiscoveryPipeline(db)

        album = Album(name="Test Album", url="https://example.com/album", year=2020)
        song = make_song()
        song_id = pipeline.register_song(song, "isaimini", album=album, category="latest")

        contexts = db.get_discovery_contexts(song_id)
        assert len(contexts) >= 1
        ctx = contexts[0]
        assert ctx.source_name == "isaimini"
        assert ctx.category == "latest"
        assert ctx.album_name == "Test Album"
        db.close()

    def test_quality_extraction(self):
        """Quality kbps extraction from Song.quality string."""
        assert extract_quality_kbps(make_song(quality="320kbps")) == 320
        assert extract_quality_kbps(make_song(quality="128kbps")) == 128
        assert extract_quality_kbps(make_song(quality="256kbps")) == 256
        assert extract_quality_kbps(make_song(quality="unknown")) is None

    def test_file_size_extraction(self):
        """File size extraction from Song.size_mb."""
        song = make_song(size_mb=5.0)
        assert extract_file_size_bytes(song) == 5 * 1024 * 1024

        song_no_size = make_song()
        song_no_size.size_mb = None
        assert extract_file_size_bytes(song_no_size) is None

    def test_cross_category_dedup(self, tmp_path):
        """Same song discovered in two categories is only one library entry."""
        db = make_db(tmp_path)
        pipeline = DiscoveryPipeline(db)

        # Same song, same URL, two different categories
        song = make_song()
        id1 = pipeline.register_song(song, "isaimini", category="latest")
        id2 = pipeline.register_song(song, "isaimini", category="old")
        assert id1 == id2

        stats = db.get_library_stats()
        assert stats["total_songs"] == 1
        db.close()


# ---------------------------------------------------------------------------
# Phase 3: Download Planner
# ---------------------------------------------------------------------------

class TestDownloadPlanner:

    def test_plan_new_songs(self, tmp_path):
        """Planner queues new songs for download."""
        db = make_db(tmp_path)
        planner = DownloadPlanner(db)

        songs = [
            make_song("Song A", "https://example.com/a.mp3"),
            make_song("Song B", "https://example.com/b.mp3"),
        ]

        plan = planner.plan_downloads(songs, "isaimini")
        assert plan.raw_discovered == 2
        assert plan.unique_canonical == 2
        assert len(plan.new_songs) == 2
        assert len(plan.owned) == 0
        assert len(plan.upgrades) == 0
        db.close()

    def test_plan_skips_owned_songs(self, tmp_path):
        """Planner skips songs already owned in library."""
        db = make_db(tmp_path)
        planner = DownloadPlanner(db)

        song = make_song()
        # Register and mark as OWNED
        pipeline = DiscoveryPipeline(db)
        song_id = pipeline.register_song(song, "isaimini")
        db.update_song_file(
            song_id=song_id,
            file_path="/music/test.mp3",
            file_size_bytes=5 * 1024 * 1024,
            quality_kbps=320,
            library_location_id=0,  # No location needed for test
        )

        plan = planner.plan_downloads([song], "isaimini")
        assert len(plan.owned) == 1
        assert len(plan.new_songs) == 0
        db.close()

    def test_plan_deduplicates_within_batch(self, tmp_path):
        """Planner deduplicates same song appearing twice in the batch."""
        db = make_db(tmp_path)
        planner = DownloadPlanner(db)

        # Same canonical song, different URLs
        song1 = make_song("Test Song", "https://source1.com/test.mp3")
        song2 = make_song("Test Song", "https://source2.com/test.mp3")

        plan = planner.plan_downloads([song1, song2], "isaimini")
        assert plan.raw_discovered == 2
        assert plan.unique_canonical == 1
        assert len(plan.new_songs) == 1  # Only one download
        db.close()

    def test_plan_summary(self, tmp_path):
        """Plan summary is human-readable."""
        db = make_db(tmp_path)
        planner = DownloadPlanner(db)

        songs = [make_song("Song A", "https://example.com/a.mp3")]
        plan = planner.plan_downloads(songs, "isaimini")

        summary = plan.summary
        assert "Discovered" in summary
        assert "owned" in summary.lower() or "Owned" in summary
        db.close()

    def test_plan_upgrade_detected(self, tmp_path):
        """Planner detects quality upgrades for owned songs."""
        db = make_db(tmp_path)
        planner = DownloadPlanner(db, upgrade_quality_threshold=64)
        pipeline = DiscoveryPipeline(db)

        # Register and mark as OWNED with 128kbps
        song_128 = make_song(quality="128kbps", url="https://example.com/low.mp3")
        song_id = pipeline.register_song(song_128, "isaimini")
        db.update_song_file(
            song_id=song_id,
            file_path="/music/test.mp3",
            file_size_bytes=3 * 1024 * 1024,
            quality_kbps=128,
            library_location_id=0,
        )

        # Now discover same song at 320kbps — should be an upgrade
        song_320 = make_song(quality="320kbps", url="https://example.com/high.mp3")
        plan = planner.plan_downloads([song_320], "isaimini")

        assert len(plan.upgrades) == 1
        assert plan.upgrades[0].quality_gain == 192
        db.close()

    def test_plan_no_upgrade_below_threshold(self, tmp_path):
        """Planner does not upgrade if quality gain is below threshold."""
        db = make_db(tmp_path)
        planner = DownloadPlanner(db, upgrade_quality_threshold=200)
        pipeline = DiscoveryPipeline(db)

        song_128 = make_song(quality="128kbps", url="https://example.com/low.mp3")
        song_id = pipeline.register_song(song_128, "isaimini")
        db.update_song_file(
            song_id=song_id,
            file_path="/music/test.mp3",
            file_size_bytes=3 * 1024 * 1024,
            quality_kbps=128,
            library_location_id=0,
        )

        song_256 = make_song(quality="256kbps", url="https://example.com/mid.mp3")
        plan = planner.plan_downloads([song_256], "isaimini")

        assert len(plan.upgrades) == 0  # 128kbps gain but threshold is 200
        assert len(plan.owned) == 1
        db.close()

    def test_total_to_download_property(self, tmp_path):
        """DownloadPlan.total_to_download sums new and upgrades."""
        db = make_db(tmp_path)
        planner = DownloadPlanner(db)
        songs = [
            make_song("A", "https://example.com/a.mp3"),
            make_song("B", "https://example.com/b.mp3"),
        ]
        plan = planner.plan_downloads(songs, "isaimini")
        assert plan.total_to_download == len(plan.new_songs) + len(plan.upgrades)
        db.close()


# ---------------------------------------------------------------------------
# Phase 4: Download Registry
# ---------------------------------------------------------------------------

class TestDownloadRegistry:

    def _add_song_and_source(self, db: SQLiteDatabase) -> tuple[int, int]:
        """Helper: add a song + source, return (song_id, source_id)."""
        from library.models import LibrarySong, SongSource
        song = LibrarySong(
            canonical_hash="hash_reg_test",
            title_normalized="test",
            artist_normalized="artist",
            album_normalized="album",
            title="Test",
            state=SongState.NEW,
        )
        song_id = db.add_song(song)
        source = SongSource(
            song_id=song_id,
            source_name="isaimini",
            source_url="https://example.com/song.mp3",
            quality_kbps=320,
        )
        source_id = db.add_source(source)
        return song_id, source_id

    def test_acquire_returns_download_id(self, tmp_path):
        """Acquiring a slot returns a positive download ID."""
        db = make_db(tmp_path)
        registry = DownloadRegistry(db)
        song_id, source_id = self._add_song_and_source(db)

        dl_id = registry.acquire(song_id, source_id)
        assert dl_id is not None
        assert dl_id > 0
        db.close()

    def test_acquire_blocks_second_acquire(self, tmp_path):
        """Second acquire on same song returns None."""
        db = make_db(tmp_path)
        registry = DownloadRegistry(db)
        song_id, source_id = self._add_song_and_source(db)

        dl_id1 = registry.acquire(song_id, source_id)
        assert dl_id1 is not None

        dl_id2 = registry.acquire(song_id, source_id)
        assert dl_id2 is None  # Already downloading
        db.close()

    def test_fail_transitions_to_failed_state(self, tmp_path):
        """After fail(), song state is FAILED."""
        db = make_db(tmp_path)
        registry = DownloadRegistry(db)
        song_id, source_id = self._add_song_and_source(db)

        dl_id = registry.acquire(song_id, source_id)
        assert dl_id is not None
        registry.fail(song_id, dl_id, "connection timeout")

        song = db.get_song(song_id)
        assert song.state == SongState.FAILED
        db.close()

    def test_fail_then_reacquire(self, tmp_path):
        """After fail, same song can be re-acquired (retry)."""
        db = make_db(tmp_path)
        registry = DownloadRegistry(db)
        song_id, source_id = self._add_song_and_source(db)

        dl_id1 = registry.acquire(song_id, source_id)
        registry.fail(song_id, dl_id1, "timeout")

        # After failure, state is FAILED — can re-acquire
        dl_id2 = registry.acquire(song_id, source_id)
        assert dl_id2 is not None
        db.close()

    def test_is_downloading(self, tmp_path):
        """is_downloading() reflects live state."""
        db = make_db(tmp_path)
        registry = DownloadRegistry(db)
        song_id, source_id = self._add_song_and_source(db)

        assert not registry.is_downloading(song_id)

        dl_id = registry.acquire(song_id, source_id)
        assert registry.is_downloading(song_id)

        registry.fail(song_id, dl_id, "err")
        assert not registry.is_downloading(song_id)
        db.close()

    def test_concurrent_acquire_thread_safe(self, tmp_path):
        """Concurrent acquires on same song: only one succeeds."""
        import threading
        db = make_db(tmp_path)
        registry = DownloadRegistry(db)
        song_id, source_id = self._add_song_and_source(db)

        results = []
        barrier = threading.Barrier(5)

        def attempt():
            barrier.wait()
            dl_id = registry.acquire(song_id, source_id)
            results.append(dl_id)

        threads = [threading.Thread(target=attempt) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Exactly one should succeed
        successes = [r for r in results if r is not None]
        assert len(successes) == 1
        db.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
