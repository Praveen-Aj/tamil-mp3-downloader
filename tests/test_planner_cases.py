"""
Explicit Planner Test Cases (Audit Section 2).

Tests 8 specific planner scenarios:
1. Preferred source = 128 kbps vs Alternative source = 320 kbps (320 kbps selected)
2. Preferred source = 320 kbps vs Alternative source = 320 kbps (Preferred source selected)
3. Preferred source unavailable vs Alternative source available (Available source selected)
4. Owned = 320 kbps, Discovered = 128 kbps (Excluded as OWNED, zero downloads)
5. Owned = 128 kbps, Discovered = 320 kbps (Scheduled as UPGRADE)
6. Multiple sources + multiple categories discovering same song (Collapses to 1 canonical song & 1 download)
7. No usable sources (Graceful handling)
8. Re-running the same download plan (Idempotent: 0 new downloads after completion)
"""

import tempfile
from pathlib import Path
import pytest

from library.database import SQLiteDatabase
from library.models import LibrarySong, SongSource, SongState
from library.planner import DownloadPlanner
from models.song import Song


@pytest.fixture
def temp_db(tmp_path):
    db_path = tmp_path / "planner_test.db"
    db = SQLiteDatabase(db_path)
    db.connect()
    yield db
    db.close()


class TestPlannerExplicitCases:

    # Case 1: Preferred source = 128 kbps vs Alternative source = 320 kbps
    def test_case1_preferred_128_vs_alternative_320(self, temp_db):
        planner = DownloadPlanner(temp_db, source_priority=["masstamilan", "tamilmp3"])
        song = LibrarySong(title="Song 1", canonical_hash="hash_case_1")
        song_id = temp_db.add_song(song)

        # MassTamilan (Preferred) offers 128 kbps
        temp_db.add_source(SongSource(
            song_id=song_id,
            source_name="masstamilan",
            source_url="https://masstamilan.dev/song1_128.mp3",
            quality_kbps=128,
            is_available=True,
        ))

        # Tamilmp3 (Alternative) offers 320 kbps
        temp_db.add_source(SongSource(
            song_id=song_id,
            source_name="tamilmp3",
            source_url="https://tamilmp3.in/song1_320.mp3",
            quality_kbps=320,
            is_available=True,
        ))

        plan = planner.plan_downloads_for_song_ids([song_id])
        assert len(plan.new_songs) == 1
        # Quality (320 kbps) takes precedence over source preference (128 kbps)
        assert plan.new_songs[0].primary.source_name == "tamilmp3"
        assert plan.new_songs[0].primary.quality_kbps == 320

    # Case 2: Preferred source = 320 kbps vs Alternative source = 320 kbps
    def test_case2_preferred_320_vs_alternative_320(self, temp_db):
        planner = DownloadPlanner(temp_db, source_priority=["masstamilan", "tamilmp3"])
        song = LibrarySong(title="Song 2", canonical_hash="hash_case_2")
        song_id = temp_db.add_song(song)

        temp_db.add_source(SongSource(
            song_id=song_id,
            source_name="masstamilan",
            source_url="https://masstamilan.dev/song2_320.mp3",
            quality_kbps=320,
            is_available=True,
        ))
        temp_db.add_source(SongSource(
            song_id=song_id,
            source_name="tamilmp3",
            source_url="https://tamilmp3.in/song2_320.mp3",
            quality_kbps=320,
            is_available=True,
        ))

        plan = planner.plan_downloads_for_song_ids([song_id])
        assert len(plan.new_songs) == 1
        # Equal quality (320 kbps) -> MassTamilan (Preferred) is selected
        assert plan.new_songs[0].primary.source_name == "masstamilan"

    # Case 3: Preferred source unavailable vs Alternative source available
    def test_case3_preferred_unavailable_vs_alternative_available(self, temp_db):
        planner = DownloadPlanner(temp_db, source_priority=["masstamilan", "tamilmp3"])
        song = LibrarySong(title="Song 3", canonical_hash="hash_case_3")
        song_id = temp_db.add_song(song)

        # Preferred source is offline/unavailable
        temp_db.add_source(SongSource(
            song_id=song_id,
            source_name="masstamilan",
            source_url="https://masstamilan.dev/song3_320.mp3",
            quality_kbps=320,
            is_available=False,
        ))
        # Alternative source is online/available
        temp_db.add_source(SongSource(
            song_id=song_id,
            source_name="tamilmp3",
            source_url="https://tamilmp3.in/song3_320.mp3",
            quality_kbps=320,
            is_available=True,
        ))

        plan = planner.plan_downloads_for_song_ids([song_id])
        assert len(plan.new_songs) == 1
        assert plan.new_songs[0].primary.source_name == "tamilmp3"

    # Case 4: Owned = 320 kbps, Discovered = 128 kbps
    def test_case4_owned_320_discovered_128(self, temp_db):
        planner = DownloadPlanner(temp_db)
        song = LibrarySong(
            title="Song 4",
            canonical_hash="hash_case_4",
            state=SongState.OWNED,
            quality_kbps=320,
        )
        song_id = temp_db.add_song(song)

        temp_db.add_source(SongSource(
            song_id=song_id,
            source_name="friendstamilmp3",
            source_url="https://friendstamilmp3.in/song4_128.mp3",
            quality_kbps=128,
            is_available=True,
        ))

        plan = planner.plan_downloads_for_song_ids([song_id])
        assert len(plan.new_songs) == 0
        assert len(plan.upgrades) == 0
        assert len(plan.owned) == 1

    # Case 5: Owned = 128 kbps, Discovered = 320 kbps
    def test_case5_owned_128_discovered_320(self, temp_db):
        planner = DownloadPlanner(temp_db, upgrade_quality_threshold=64)
        song = LibrarySong(
            title="Song 5",
            canonical_hash="hash_case_5",
            state=SongState.OWNED,
            quality_kbps=128,
        )
        song_id = temp_db.add_song(song)

        temp_db.add_source(SongSource(
            song_id=song_id,
            source_name="masstamilan",
            source_url="https://masstamilan.dev/song5_320.mp3",
            quality_kbps=320,
            is_available=True,
        ))

        plan = planner.plan_downloads_for_song_ids([song_id])
        assert len(plan.new_songs) == 0
        assert len(plan.upgrades) == 1
        assert plan.upgrades[0].quality_gain == 192

    # Case 6: Multiple sources + multiple categories discovering same song
    def test_case6_multi_source_multi_category_same_song(self, temp_db):
        planner = DownloadPlanner(temp_db)
        song_a1 = Song(name="Song 6", url="https://masstamilan.dev/s6.mp3", quality="320kbps", artist="Artist", album_name="Album")
        song_a2 = Song(name="Song 6", url="https://tamilmp3.in/s6.mp3", quality="320kbps", artist="Artist", album_name="Album")
        song_a3 = Song(name="Song 6", url="https://friendstamilmp3.in/s6.mp3", quality="128kbps", artist="Artist", album_name="Album")

        source_batches = [
            {"songs": [song_a1], "source_name": "masstamilan", "category": "latest"},
            {"songs": [song_a2], "source_name": "tamilmp3", "category": "2026"},
            {"songs": [song_a3], "source_name": "friendstamilmp3", "category": "top"},
        ]

        plan = planner.plan_downloads_multi_source(source_batches)
        assert plan.raw_discovered == 3
        assert plan.unique_canonical == 1
        assert len(plan.new_songs) == 1

    # Case 7: No usable sources
    def test_case7_no_usable_sources(self, temp_db):
        planner = DownloadPlanner(temp_db)
        song = LibrarySong(title="Song 7", canonical_hash="hash_case_7")
        song_id = temp_db.add_song(song)

        # No sources added to DB
        plan = planner.plan_downloads_for_song_ids([song_id])
        assert len(plan.new_songs) == 0
        assert len(plan.owned) == 0

    # Case 8: Re-running the same download plan
    def test_case8_rerunning_same_download_plan(self, temp_db):
        planner = DownloadPlanner(temp_db)
        song = LibrarySong(title="Song 8", canonical_hash="hash_case_8", state=SongState.NEW)
        song_id = temp_db.add_song(song)

        temp_db.add_source(SongSource(
            song_id=song_id,
            source_name="masstamilan",
            source_url="https://masstamilan.dev/song8_320.mp3",
            quality_kbps=320,
        ))

        # First run -> 1 new song to download
        plan1 = planner.plan_downloads_for_song_ids([song_id])
        assert len(plan1.new_songs) == 1

        # Simulate download completion -> state becomes OWNED with 320kbps
        temp_db.update_song_file(song_id, file_path="/path/to/song8.mp3", file_size_bytes=5000000, quality_kbps=320)

        # Re-run plan -> 0 new downloads, song is now in owned list
        plan2 = planner.plan_downloads_for_song_ids([song_id])
        assert len(plan2.new_songs) == 0
        assert len(plan2.upgrades) == 0
        assert len(plan2.owned) == 1
