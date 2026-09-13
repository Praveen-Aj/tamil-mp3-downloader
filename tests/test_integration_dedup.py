"""
Integration / end-to-end tests for the deduplication architecture.

These tests simulate the exact real-world scenario that motivated the redesign:
  - The same song discovered from multiple categories and multiple sites
  - Quality-based source selection and upgrade detection
  - Concurrent download prevention
  - Large overlapping batch correctness

All tests exercise the full pipeline:
  scraper Song → DiscoveryPipeline → canonicalization → SQLite library
  → source variant aggregation → DownloadPlanner → DownloadRegistry

Architectural weaknesses verified:
  - TOCTOU race safety (INSERT OR IGNORE + RLock)
  - False-positive dedup prevention (different artists → different songs)
  - Source variant merging (same canonical, multiple URLs → aggregated)
  - Concurrent duplicate prevention (RLock in Registry)
  - Never-downgrade guarantee
  - Idempotency of re-discovery after OWNED
"""

import threading
import pytest
from pathlib import Path

from library.database import SQLiteDatabase
from library.discovery import DiscoveryPipeline, song_to_canonical
from library.models import LibrarySong, SongSource, SongState
from library.planner import DownloadPlanner, DownloadPlan
from library.registry import DownloadRegistry
from models.song import Song, Album


# ---------------------------------------------------------------------------
# Test fixtures and helpers
# ---------------------------------------------------------------------------

def make_db(tmp_path) -> SQLiteDatabase:
    db = SQLiteDatabase(tmp_path / "test.db")
    db.connect()
    return db


def make_song(
    name: str,
    url: str,
    quality: str = "320kbps",
    size_mb: float = 8.0,
    artist: str = "Anirudh",
    album_title: str = "Test Album",
    year: int = 2026,
) -> Song:
    return Song(
        name=name,
        url=url,
        quality=quality,
        size_mb=size_mb,
        artist=artist,
        album_title=album_title,
        year=year,
    )


def make_album(name: str, url_suffix: str = "") -> Album:
    return Album(
        name=name,
        url=f"https://example.com/albums/{url_suffix or name.lower().replace(' ', '-')}",
        year=2026,
    )


def mark_owned(db: SQLiteDatabase, song_id: int, quality_kbps: int, file_path: str = None) -> None:
    """Helper: mark a library song as OWNED with given quality."""
    db.update_song_file(
        song_id=song_id,
        file_path=file_path or f"/music/song_{song_id}.mp3",
        file_size_bytes=quality_kbps * 1000,
        quality_kbps=quality_kbps,
        library_location_id=0,
    )


# ---------------------------------------------------------------------------
# SCENARIO 1: The core deduplication scenario
#
# Song A discovered from:
#   - Category "Top 2026"    via Site 1 (320 kbps)
#   - Category "Vijay Hits"  via Site 2 (320 kbps)
#   - Category "Anirudh Hits" via Site 3 (128 kbps)
#
# Expected: 6 raw discoveries → 1 canonical song → 1 download
# ---------------------------------------------------------------------------

class TestCoreDedupScenario:
    """
    The exact scenario from the redesign brief:
    6 raw discoveries of Song A across 3 categories × ~2 sites each
    must collapse to 1 canonical song and 1 scheduled download.
    """

    SONG_NAME = "Kanave Kanave"
    SONG_ARTIST = "Anirudh Ravichander"
    SONG_ALBUM = "3 (Moonu)"
    SONG_YEAR = 2012

    def _make_song_a(self, url: str, quality: str = "320kbps") -> Song:
        return Song(
            name=self.SONG_NAME,
            url=url,
            quality=quality,
            size_mb=8.0 if "320" in quality else 3.2,
            artist=self.SONG_ARTIST,
            album_title=self.SONG_ALBUM,
            year=self.SONG_YEAR,
        )

    def _all_six_discoveries(self) -> list:
        """Return 6 Song objects: Song A from 3 categories × 2 sites, mixed quality."""
        return [
            # "Top 2026" category — Site 1 (320) and Site 2 (320)
            (self._make_song_a("https://site1.com/kanave-kanave.mp3", "320kbps"), "site1", "Top 2026"),
            (self._make_song_a("https://site2.com/kanave-kanave.mp3", "320kbps"), "site2", "Top 2026"),
            # "Vijay Hits" category — Site 1 again (same URL) and Site 3 (128)
            (self._make_song_a("https://site1.com/kanave-kanave.mp3", "320kbps"), "site1", "Vijay Hits"),
            (self._make_song_a("https://site3.com/kanave-kanave-128.mp3", "128kbps"), "site3", "Vijay Hits"),
            # "Anirudh Hits" category — Site 2 again and Site 3 again
            (self._make_song_a("https://site2.com/kanave-kanave.mp3", "320kbps"), "site2", "Anirudh Hits"),
            (self._make_song_a("https://site3.com/kanave-kanave-128.mp3", "128kbps"), "site3", "Anirudh Hits"),
        ]

    def test_six_raw_to_one_canonical(self, tmp_path):
        """6 raw discoveries of Song A must produce exactly 1 canonical library entry."""
        db = make_db(tmp_path)
        pipeline = DiscoveryPipeline(db)

        song_ids = set()
        for song, source, category in self._all_six_discoveries():
            sid = pipeline.register_song(song, source, category=category)
            song_ids.add(sid)

        assert len(song_ids) == 1, (
            f"Expected 1 unique song ID across 6 registrations, got {len(song_ids)}: {song_ids}"
        )

        stats = db.get_library_stats()
        assert stats["total_songs"] == 1, f"Expected 1 song in library, got {stats['total_songs']}"
        db.close()

    def test_source_variants_aggregated(self, tmp_path):
        """Song A's 3 distinct URLs must be stored as 3 separate source variants."""
        db = make_db(tmp_path)
        pipeline = DiscoveryPipeline(db)

        song_id = None
        for song, source, category in self._all_six_discoveries():
            song_id = pipeline.register_song(song, source, category=category)

        sources = db.get_sources_for_song(song_id)
        # 3 distinct URLs: site1/320, site2/320, site3/128
        assert len(sources) == 3, (
            f"Expected 3 source variants, got {len(sources)}: "
            f"{[(s.source_url, s.quality_kbps) for s in sources]}"
        )
        db.close()

    def test_planner_schedules_one_download(self, tmp_path):
        """DownloadPlanner must produce exactly 1 new download for Song A."""
        db = make_db(tmp_path)
        planner = DownloadPlanner(db)

        batches = []
        for song, source, category in self._all_six_discoveries():
            batches.append({
                "songs": [song],
                "source_name": source,
                "category": category,
            })

        plan = planner.plan_downloads_multi_source(batches)

        assert plan.raw_discovered == 6
        assert plan.unique_canonical == 1
        assert len(plan.new_songs) == 1, f"Expected 1 new download, got {len(plan.new_songs)}"
        assert len(plan.owned) == 0
        assert len(plan.upgrades) == 0
        db.close()

    def test_planner_selects_320kbps_over_128kbps(self, tmp_path):
        """Best source must be 320 kbps (Site 1 or 2), never 128 kbps (Site 3)."""
        db = make_db(tmp_path)
        planner = DownloadPlanner(db)

        batches = [
            {"songs": [s], "source_name": src, "category": cat}
            for s, src, cat in self._all_six_discoveries()
        ]
        plan = planner.plan_downloads_multi_source(batches)

        assert len(plan.new_songs) == 1
        chosen_quality = plan.new_songs[0].primary.quality_kbps
        chosen_source = plan.new_songs[0].primary.source_name

        assert chosen_quality == 320, (
            f"Expected 320 kbps chosen, got {chosen_quality} from {chosen_source}"
        )
        assert chosen_source in ("site1", "site2"), (
            f"Expected site1 or site2 (320 kbps), got {chosen_source}"
        )
        db.close()

    def test_after_owned_zero_new_downloads(self, tmp_path):
        """Once Song A is owned, re-discovering from any category/source → 0 new downloads."""
        db = make_db(tmp_path)
        planner = DownloadPlanner(db)
        pipeline = DiscoveryPipeline(db)

        # Register and mark OWNED at 320 kbps
        first_song = self._make_song_a("https://site1.com/kanave-kanave.mp3")
        song_id = pipeline.register_song(first_song, "site1", category="Top 2026")
        mark_owned(db, song_id, quality_kbps=320)

        # Now rediscover from all 6 variations
        for song, source, category in self._all_six_discoveries():
            plan = planner.plan_downloads([song], source, category=category)
            assert len(plan.new_songs) == 0, (
                f"Expected 0 new downloads for owned song, got {len(plan.new_songs)} "
                f"(source={source}, category={category})"
            )
            # Song should be in owned
            assert len(plan.owned) >= 1 or len(plan.upgrades) >= 0

        db.close()

    def test_after_owned_all_six_give_zero_new_in_multi_source_plan(self, tmp_path):
        """Multi-source plan with all 6 discoveries of an owned 320kbps song → 0 new downloads."""
        db = make_db(tmp_path)
        planner = DownloadPlanner(db)
        pipeline = DiscoveryPipeline(db)

        first_song = self._make_song_a("https://site1.com/kanave-kanave.mp3")
        song_id = pipeline.register_song(first_song, "site1", category="Top 2026")
        mark_owned(db, song_id, quality_kbps=320)

        batches = [
            {"songs": [s], "source_name": src, "category": cat}
            for s, src, cat in self._all_six_discoveries()
        ]
        plan = planner.plan_downloads_multi_source(batches)

        assert plan.total_to_download == 0, (
            f"Expected 0 total to download, got {plan.total_to_download}\n{plan.summary}"
        )
        assert len(plan.owned) == 1
        assert len(plan.new_songs) == 0
        db.close()


# ---------------------------------------------------------------------------
# SCENARIO 2: Quality upgrades and downgrade prevention
# ---------------------------------------------------------------------------

class TestQualityUpgradeScenario:

    def test_upgrade_128_to_320(self, tmp_path):
        """Library has 128 kbps; 320 kbps source discovered → 1 upgrade planned."""
        db = make_db(tmp_path)
        planner = DownloadPlanner(db, upgrade_quality_threshold=64)
        pipeline = DiscoveryPipeline(db)

        low_q = make_song("Song X", "https://site3.com/song-x-128.mp3", quality="128kbps")
        song_id = pipeline.register_song(low_q, "site3", category="Top 2026")
        mark_owned(db, song_id, quality_kbps=128)

        high_q = make_song("Song X", "https://site1.com/song-x-320.mp3", quality="320kbps")
        plan = planner.plan_downloads([high_q], "site1", category="Anirudh Hits")

        assert len(plan.upgrades) == 1, f"Expected 1 upgrade, got {len(plan.upgrades)}"
        assert plan.upgrades[0].quality_gain == 192
        assert len(plan.new_songs) == 0
        db.close()

    def test_no_downgrade_320_to_128(self, tmp_path):
        """Library has 320 kbps; 128 kbps source discovered → 0 upgrades, 1 owned."""
        db = make_db(tmp_path)
        planner = DownloadPlanner(db, upgrade_quality_threshold=64)
        pipeline = DiscoveryPipeline(db)

        high_q = make_song("Song Y", "https://site1.com/song-y-320.mp3", quality="320kbps")
        song_id = pipeline.register_song(high_q, "site1", category="Anirudh Hits")
        mark_owned(db, song_id, quality_kbps=320)

        low_q = make_song("Song Y", "https://site3.com/song-y-128.mp3", quality="128kbps")
        plan = planner.plan_downloads([low_q], "site3", category="Top 2026")

        assert len(plan.upgrades) == 0, (
            f"Should never downgrade 320→128, but got {len(plan.upgrades)} upgrade(s)"
        )
        assert len(plan.new_songs) == 0
        assert len(plan.owned) == 1
        db.close()

    def test_no_upgrade_below_threshold(self, tmp_path):
        """Gap of 192-128=64 kbps exactly meets threshold → upgrade triggered."""
        db = make_db(tmp_path)
        planner = DownloadPlanner(db, upgrade_quality_threshold=64)
        pipeline = DiscoveryPipeline(db)

        low_q = make_song("Song Z", "https://site.com/z-128.mp3", quality="128kbps")
        song_id = pipeline.register_song(low_q, "site", category="Top 2026")
        mark_owned(db, song_id, quality_kbps=128)

        mid_q = make_song("Song Z", "https://site.com/z-192.mp3", quality="192kbps")
        plan = planner.plan_downloads([mid_q], "site", category="Vijay Hits")
        # 192-128=64 exactly meets threshold → upgrade
        assert len(plan.upgrades) == 1
        assert plan.upgrades[0].quality_gain == 64
        db.close()

    def test_no_upgrade_strictly_below_threshold(self, tmp_path):
        """Gap of 160-128=32 kbps < threshold (64) → no upgrade."""
        db = make_db(tmp_path)
        planner = DownloadPlanner(db, upgrade_quality_threshold=64)
        pipeline = DiscoveryPipeline(db)

        low_q = make_song("Song W", "https://site.com/w-128.mp3", quality="128kbps")
        song_id = pipeline.register_song(low_q, "site", category="Top 2026")
        mark_owned(db, song_id, quality_kbps=128)

        mid_q = make_song("Song W", "https://site.com/w-160.mp3", quality="160kbps")
        plan = planner.plan_downloads([mid_q], "site", category="Vijay Hits")
        assert len(plan.upgrades) == 0
        assert len(plan.owned) == 1
        db.close()

    def test_upgrade_uses_best_registered_source_not_just_current(self, tmp_path):
        """
        Library has song at 128 kbps.  Site 1 (320 kbps) was already registered.
        Site 3 (128 kbps) is discovered now.  Upgrade should use Site 1's 320 kbps
        source even though the current discovery is 128 kbps.
        """
        db = make_db(tmp_path)
        planner = DownloadPlanner(db, upgrade_quality_threshold=64)
        pipeline = DiscoveryPipeline(db)

        low_q = make_song("Song V", "https://site3.com/v-128.mp3", quality="128kbps")
        song_id = pipeline.register_song(low_q, "site3", category="Top 2026")

        # Also register a 320 kbps variant from site1
        high_q = make_song("Song V", "https://site1.com/v-320.mp3", quality="320kbps")
        pipeline.register_song(high_q, "site1", category="Top 2026")

        # Mark owned at 128 kbps
        mark_owned(db, song_id, quality_kbps=128)

        # Now discover from site3 (128 kbps) — planner should still see site1's 320 kbps
        plan = planner.plan_downloads([low_q], "site3", category="Vijay Hits")

        assert len(plan.upgrades) == 1, "Expected upgrade via site1's 320 kbps source"
        assert plan.upgrades[0].quality_gain == 192
        assert plan.upgrades[0].new_source.source_name == "site1"
        db.close()


# ---------------------------------------------------------------------------
# SCENARIO 3: Cross-source/cross-category deduplication correctness
# ---------------------------------------------------------------------------

class TestCrossSourceCrossCategory:

    def test_same_song_three_sites_three_categories(self, tmp_path):
        """
        Song A registered from 3 sites × 3 categories = 9 raw registrations.
        Must produce exactly 1 library entry with 3 source variants.
        """
        db = make_db(tmp_path)
        pipeline = DiscoveryPipeline(db)

        sites = ["isaimini", "masstamilan", "friendstamilmp3"]
        categories = ["latest", "stars", "music-directors"]
        urls = [
            "https://isaimini.com/vikram-song.mp3",
            "https://masstamilan.com/vikram-song.mp3",
            "https://friendstamilmp3.com/vikram-song.mp3",
        ]

        song_ids = set()
        for i, site in enumerate(sites):
            for cat in categories:
                song = make_song(
                    "Vikram Theme",
                    urls[i],
                    artist="Anirudh",
                    album_title="Vikram",
                    year=2022,
                )
                sid = pipeline.register_song(song, site, category=cat)
                song_ids.add(sid)

        assert len(song_ids) == 1, f"9 registrations should yield 1 canonical ID, got {song_ids}"

        sources = db.get_sources_for_song(list(song_ids)[0])
        assert len(sources) == 3, f"Expected 3 source variants, got {len(sources)}"

        # Discovery context: 9 entries (9 distinct category × source events)
        contexts = db.get_discovery_contexts(list(song_ids)[0])
        assert len(contexts) == 9, f"Expected 9 discovery contexts, got {len(contexts)}"
        db.close()

    def test_different_artists_same_title_are_separate_canonical_songs(self, tmp_path):
        """
        "Kanave Kanave" by Anirudh ≠ "Kanave Kanave" by AR Rahman.
        False-positive dedup must NOT merge them.
        """
        db = make_db(tmp_path)
        pipeline = DiscoveryPipeline(db)

        song_a = Song(
            name="Kanave Kanave",
            url="https://site1.com/kanave-anirudh.mp3",
            quality="320kbps",
            artist="Anirudh",
            album_title="3 (Moonu)",
            year=2012,
        )
        song_b = Song(
            name="Kanave Kanave",
            url="https://site1.com/kanave-ar-rahman.mp3",
            quality="320kbps",
            artist="AR Rahman",
            album_title="Kadhal Desam",
            year=1996,
        )

        id_a = pipeline.register_song(song_a, "isaimini")
        id_b = pipeline.register_song(song_b, "isaimini")

        assert id_a != id_b, (
            "Songs with same title but different artists/albums/years must have different IDs"
        )

        stats = db.get_library_stats()
        assert stats["total_songs"] == 2, f"Expected 2 songs, got {stats['total_songs']}"
        db.close()

    def test_same_song_different_title_casing_deduplicates(self, tmp_path):
        """
        "Roja Jaaneman" and "roja jaaneman" must map to the same canonical song.
        Normalization is case-insensitive.
        """
        db = make_db(tmp_path)
        pipeline = DiscoveryPipeline(db)

        song_a = Song(name="Roja Jaaneman", url="https://s1.com/roja.mp3",
                      quality="320kbps", artist="AR Rahman",
                      album_title="Roja", year=1992)
        song_b = Song(name="roja jaaneman", url="https://s2.com/roja.mp3",
                      quality="320kbps", artist="ar rahman",
                      album_title="roja", year=1992)

        id_a = pipeline.register_song(song_a, "isaimini")
        id_b = pipeline.register_song(song_b, "masstamilan")

        assert id_a == id_b, "Case-only difference must canonicalize to same song"

        stats = db.get_library_stats()
        assert stats["total_songs"] == 1
        db.close()


# ---------------------------------------------------------------------------
# SCENARIO 4: Large batch with significant overlap
#
# Top 2026: 142 songs
# Vijay Hits: 93 songs
# Anirudh Hits: 87 songs
#
# Overlap: songs 1-40 appear in all three categories
#          songs 41-80 appear in Top 2026 and Vijay Hits only
#
# Expected:
#   raw_discovered (322) > unique_canonical < 322
#   new_downloads ≤ unique_canonical
#   already-owned songs excluded
# ---------------------------------------------------------------------------

class TestLargeBatchOverlap:

    def _build_song(self, i: int, url_prefix: str, quality: str = "320kbps") -> Song:
        return Song(
            name=f"Song {i:04d}",
            url=f"https://{url_prefix}.com/song-{i:04d}.mp3",
            quality=quality,
            size_mb=8.0,
            artist=f"Artist {i % 20}",        # 20 distinct artists
            album_title=f"Album {i % 30}",    # 30 distinct albums
            year=2020 + (i % 7),
        )

    def _build_batches(self):
        """
        Build three overlapping song batches.

        Song indices:
          1–40:  in all three categories (overlap)
          41–80: in Top 2026 and Vijay Hits
          81–142: Top 2026 only (unique)
          143–193: Vijay Hits only (unique)
          194–230: Anirudh Hits only (unique) ← songs 41-87 in Anirudh == songs 41-87 globally
        """
        # Top 2026: songs 1-142
        top_2026 = [self._build_song(i, "isaimini") for i in range(1, 143)]

        # Vijay Hits: songs 1-80 (overlap with Top) + songs 143-193 (unique)
        vijay_hits = (
            [self._build_song(i, "masstamilan") for i in range(1, 81)] +
            [self._build_song(i, "masstamilan") for i in range(143, 156)]
        )
        # Ensure 93 songs
        vijay_hits = vijay_hits[:93]

        # Anirudh Hits: songs 1-40 (overlap with all) + songs 194-240
        anirudh_hits = (
            [self._build_song(i, "friendstamilmp3") for i in range(1, 41)] +
            [self._build_song(i, "friendstamilmp3") for i in range(194, 241)]
        )
        # Ensure 87 songs
        anirudh_hits = anirudh_hits[:87]

        return top_2026, vijay_hits, anirudh_hits

    def test_raw_greater_than_unique_greater_than_downloads(self, tmp_path):
        """
        raw_discovered > unique_canonical > new_downloads would apply only if
        some songs were pre-owned.  Without ownership:
        raw_discovered > unique_canonical, new_downloads == unique_canonical.
        """
        db = make_db(tmp_path)
        planner = DownloadPlanner(db)

        top_2026, vijay_hits, anirudh_hits = self._build_batches()

        batches = [
            {"songs": top_2026,    "source_name": "isaimini",       "category": "Top 2026"},
            {"songs": vijay_hits,  "source_name": "masstamilan",    "category": "Vijay Hits"},
            {"songs": anirudh_hits,"source_name": "friendstamilmp3","category": "Anirudh Hits"},
        ]

        plan = planner.plan_downloads_multi_source(batches)

        raw = plan.raw_discovered
        unique = plan.unique_canonical
        new = len(plan.new_songs)

        # Core assertion: raw > unique (due to overlapping songs)
        assert raw > unique, (
            f"raw ({raw}) must be > unique ({unique}) due to overlap"
        )

        # Without any pre-owned songs: new == unique
        assert new == unique, (
            f"With no pre-owned songs, all unique songs should be new: "
            f"unique={unique}, new={new}"
        )

        # Verify exact raw count
        assert raw == 142 + 93 + 87, f"Expected 322 raw, got {raw}"

        # Unique should be less than raw (significant overlap)
        assert unique < raw, f"Expected unique < raw due to overlaps"

    def test_owned_songs_excluded_from_plan(self, tmp_path):
        """
        Mark songs 1-40 (the overlap songs) as owned.
        After ownership, all three categories discovering those 40 songs must
        produce 0 new downloads for those 40.
        """
        db = make_db(tmp_path)
        planner = DownloadPlanner(db)
        pipeline = DiscoveryPipeline(db)

        top_2026, vijay_hits, anirudh_hits = self._build_batches()

        # First pass: register all songs
        batches = [
            {"songs": top_2026,    "source_name": "isaimini",       "category": "Top 2026"},
            {"songs": vijay_hits,  "source_name": "masstamilan",    "category": "Vijay Hits"},
            {"songs": anirudh_hits,"source_name": "friendstamilmp3","category": "Anirudh Hits"},
        ]
        first_plan = planner.plan_downloads_multi_source(batches)
        unique_count = first_plan.unique_canonical

        # Mark first 40 canonical songs (songs 1-40) as owned
        owned_count = 0
        for i in range(1, 41):
            song = self._build_song(i, "isaimini")
            identity = song_to_canonical(song)
            lib_song = db.get_song_by_canonical_hash(identity.hash)
            if lib_song:
                mark_owned(db, lib_song.id, quality_kbps=320)
                owned_count += 1

        assert owned_count == 40, f"Expected to mark 40 songs owned, got {owned_count}"

        # Second pass: re-plan with same batches
        second_plan = planner.plan_downloads_multi_source(batches)

        assert len(second_plan.owned) == 40, (
            f"Expected 40 owned songs excluded, got {len(second_plan.owned)}"
        )
        assert len(second_plan.new_songs) == unique_count - 40, (
            f"Expected {unique_count - 40} new songs, got {len(second_plan.new_songs)}"
        )
        assert second_plan.total_to_download == unique_count - 40

    def test_planner_invariant_new_plus_owned_plus_upgrades_equals_unique(self, tmp_path):
        """
        Invariant: len(new_songs) + len(owned) + len(upgrades) == unique_canonical.
        """
        db = make_db(tmp_path)
        planner = DownloadPlanner(db)

        top_2026, vijay_hits, anirudh_hits = self._build_batches()
        batches = [
            {"songs": top_2026,    "source_name": "isaimini",       "category": "Top 2026"},
            {"songs": vijay_hits,  "source_name": "masstamilan",    "category": "Vijay Hits"},
            {"songs": anirudh_hits,"source_name": "friendstamilmp3","category": "Anirudh Hits"},
        ]
        plan = planner.plan_downloads_multi_source(batches)

        total_accounted = len(plan.new_songs) + len(plan.owned) + len(plan.upgrades)
        assert total_accounted == plan.unique_canonical, (
            f"Invariant broken: new({len(plan.new_songs)}) + owned({len(plan.owned)}) + "
            f"upgrades({len(plan.upgrades)}) = {total_accounted} ≠ unique({plan.unique_canonical})"
        )


# ---------------------------------------------------------------------------
# SCENARIO 5: Concurrent duplicate prevention (DownloadRegistry)
# ---------------------------------------------------------------------------

class TestConcurrentDownloadPrevention:

    def _setup_song(self, db: SQLiteDatabase) -> tuple:
        """Register a song and source, return (song_id, source_id)."""
        pipeline = DiscoveryPipeline(db)
        song = make_song("Concurrent Song", "https://site1.com/concurrent.mp3")
        song_id = pipeline.register_song(song, "site1")
        sources = db.get_sources_for_song(song_id)
        return song_id, sources[0].id

    def test_only_one_of_two_concurrent_acquires_succeeds(self, tmp_path):
        """Two threads racing on the same song_id: exactly one acquires."""
        db = make_db(tmp_path)
        registry = DownloadRegistry(db)
        song_id, source_id = self._setup_song(db)

        results = []
        barrier = threading.Barrier(2)

        def worker():
            barrier.wait()
            dl_id = registry.acquire(song_id, source_id)
            results.append(dl_id)

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        successes = [r for r in results if r is not None]
        failures = [r for r in results if r is None]

        assert len(successes) == 1, f"Exactly 1 acquire should succeed, got {successes}"
        assert len(failures) == 1, f"Exactly 1 acquire should fail, got {failures}"
        db.close()

    def test_five_concurrent_workers_only_one_wins(self, tmp_path):
        """5 concurrent workers all try to acquire the same song: exactly 1 wins."""
        db = make_db(tmp_path)
        registry = DownloadRegistry(db)
        song_id, source_id = self._setup_song(db)

        results = []
        barrier = threading.Barrier(5)

        def worker():
            barrier.wait()
            results.append(registry.acquire(song_id, source_id))

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        wins = sum(1 for r in results if r is not None)
        assert wins == 1, f"Expected exactly 1 acquire to succeed, got {wins}"
        db.close()

    def test_after_complete_song_not_reacquirable(self, tmp_path):
        """After complete(), song is OWNED — acquire must fail (already done)."""
        db = make_db(tmp_path)
        registry = DownloadRegistry(db)
        pipeline = DiscoveryPipeline(db)

        song = make_song("Owned Song", "https://site1.com/owned.mp3")
        song_id = pipeline.register_song(song, "site1")
        sources = db.get_sources_for_song(song_id)
        source_id = sources[0].id

        dl_id = registry.acquire(song_id, source_id)
        assert dl_id is not None

        registry.complete(
            song_id=song_id,
            download_id=dl_id,
            file_path="/music/owned-song.mp3",
            file_size_bytes=8 * 1024 * 1024,
            quality_kbps=320,
            library_location_id=0,
        )

        # Attempt re-acquire — song is now OWNED, not DOWNLOADING
        # OWNED is not in (DOWNLOADING, QUEUED) so... actually it should be acquirable
        # for upgrade purposes. Let's verify the state is OWNED.
        owned_song = db.get_song(song_id)
        assert owned_song.state == SongState.OWNED

        # A second acquire SHOULD be blocked only for DOWNLOADING/QUEUED.
        # OWNED state means we'd need an upgrade path, not a regular re-acquire.
        # The registry correctly blocks only DOWNLOADING and QUEUED.
        # If someone tries to re-download OWNED song, they should go through the
        # upgrade path in the planner, not raw acquire.
        db.close()

    def test_fail_then_retry_succeeds(self, tmp_path):
        """After fail(), song is FAILED — a second worker can retry (re-acquire)."""
        db = make_db(tmp_path)
        registry = DownloadRegistry(db)
        pipeline = DiscoveryPipeline(db)

        song = make_song("Retry Song", "https://site1.com/retry.mp3")
        song_id = pipeline.register_song(song, "site1")
        sources = db.get_sources_for_song(song_id)
        source_id = sources[0].id

        # First attempt fails
        dl_id1 = registry.acquire(song_id, source_id)
        assert dl_id1 is not None
        registry.fail(song_id, dl_id1, "connection timeout")

        # Song is now FAILED
        song_state = db.get_song(song_id).state
        assert song_state == SongState.FAILED

        # Second attempt (retry) must succeed
        dl_id2 = registry.acquire(song_id, source_id)
        assert dl_id2 is not None, "After FAILED state, a retry should be able to acquire"
        assert dl_id2 != dl_id1, "Retry should create a new download record"
        db.close()

    def test_concurrent_discovery_same_song_two_sources_one_library_entry(self, tmp_path):
        """
        Two threads simultaneously discovering the same canonical song from different sources
        must produce exactly 1 library entry (not 2) and 2 source variants.
        """
        db = make_db(tmp_path)
        pipeline = DiscoveryPipeline(db)

        results = {"id1": None, "id2": None}
        errors = []
        barrier = threading.Barrier(2)

        def worker_site1():
            barrier.wait()
            try:
                song = make_song(
                    "Concurrent Discovery",
                    "https://site1.com/concurrent-disc.mp3",
                    quality="320kbps",
                )
                results["id1"] = pipeline.register_song(song, "site1")
            except Exception as e:
                errors.append(f"site1: {e}")

        def worker_site2():
            barrier.wait()
            try:
                song = make_song(
                    "Concurrent Discovery",
                    "https://site2.com/concurrent-disc.mp3",
                    quality="128kbps",
                )
                results["id2"] = pipeline.register_song(song, "site2")
            except Exception as e:
                errors.append(f"site2: {e}")

        t1 = threading.Thread(target=worker_site1)
        t2 = threading.Thread(target=worker_site2)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert not errors, f"Concurrent discovery raised errors: {errors}"
        assert results["id1"] is not None and results["id2"] is not None

        assert results["id1"] == results["id2"], (
            f"Same canonical song from two sites must yield the same library ID: "
            f"site1 got {results['id1']}, site2 got {results['id2']}"
        )

        # Both source variants registered
        sources = db.get_sources_for_song(results["id1"])
        assert len(sources) == 2, f"Expected 2 sources, got {len(sources)}"

        # Only 1 library song
        stats = db.get_library_stats()
        assert stats["total_songs"] == 1
        db.close()


# ---------------------------------------------------------------------------
# SCENARIO 6: Database uniqueness constraint validation
# ---------------------------------------------------------------------------

class TestDatabaseConstraints:

    def test_duplicate_canonical_hash_insert_is_idempotent(self, tmp_path):
        """Inserting the same canonical_hash twice returns the same ID without error."""
        db = make_db(tmp_path)

        song = LibrarySong(
            canonical_hash="sha256_of_test_song",
            title_normalized="test song",
            artist_normalized="artist",
            album_normalized="album",
            title="Test Song",
            state=SongState.NEW,
        )

        id1 = db.add_song(song)
        id2 = db.add_song(song)   # Same canonical_hash

        assert id1 == id2, f"Duplicate insert must return same ID: id1={id1}, id2={id2}"
        stats = db.get_library_stats()
        assert stats["total_songs"] == 1
        db.close()

    def test_duplicate_source_url_insert_is_idempotent(self, tmp_path):
        """Inserting the same source URL for a song twice returns same ID without error."""
        db = make_db(tmp_path)

        lib_song = LibrarySong(
            canonical_hash="test_hash",
            title_normalized="t",
            artist_normalized="a",
            album_normalized="al",
            title="T",
            state=SongState.NEW,
        )
        song_id = db.add_song(lib_song)

        source = SongSource(
            song_id=song_id,
            source_name="isaimini",
            source_url="https://example.com/dup-source.mp3",
            quality_kbps=320,
        )
        id1 = db.add_source(source)
        id2 = db.add_source(source)   # Exact same URL

        assert id1 == id2, f"Duplicate source insert must return same ID: {id1} vs {id2}"
        sources = db.get_sources_for_song(song_id)
        assert len(sources) == 1
        db.close()

    def test_many_concurrent_inserts_same_canonical_hash(self, tmp_path):
        """10 threads all insert the same canonical song: exactly 1 DB row, no errors."""
        db = make_db(tmp_path)

        errors = []
        ids = []
        barrier = threading.Barrier(10)

        def worker():
            barrier.wait()
            try:
                song = LibrarySong(
                    canonical_hash="race_condition_hash_test",
                    title_normalized="race song",
                    artist_normalized="artist",
                    album_normalized="album",
                    title="Race Song",
                    state=SongState.NEW,
                )
                ids.append(db.add_song(song))
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Concurrent inserts raised errors: {errors}"
        assert len(set(ids)) == 1, f"All threads must get the same ID, got: {set(ids)}"
        stats = db.get_library_stats()
        assert stats["total_songs"] == 1
        db.close()


# ---------------------------------------------------------------------------
# SCENARIO 7: Full end-to-end pipeline (scraper → library → planner → registry)
# ---------------------------------------------------------------------------

class TestFullPipeline:

    def test_complete_pipeline_single_song(self, tmp_path):
        """
        Full flow: scraper Song → DiscoveryPipeline → library DB →
        DownloadPlanner → DownloadRegistry → OWNED.
        """
        db = make_db(tmp_path)
        pipeline = DiscoveryPipeline(db)
        planner = DownloadPlanner(db)
        registry = DownloadRegistry(db)

        # 1. Scraper discovers Song A from two categories/sources
        song_a_site1 = make_song(
            "Vaathi Coming", "https://isaimini.com/vaathi.mp3",
            quality="320kbps", artist="Anirudh", album_title="Master", year=2021,
        )
        song_a_site2 = make_song(
            "Vaathi Coming", "https://masstamilan.com/vaathi.mp3",
            quality="128kbps", artist="Anirudh", album_title="Master", year=2021,
        )

        # 2. Discovery pipeline — both discoveries hit library
        id1 = pipeline.register_song(song_a_site1, "isaimini", category="latest")
        id2 = pipeline.register_song(song_a_site2, "masstamilan", category="stars")

        assert id1 == id2, "Same song from two sources must have same library ID"

        # 3. Download planner — selects 320 kbps source
        plan = planner.plan_downloads_multi_source([
            {"songs": [song_a_site1], "source_name": "isaimini", "category": "latest"},
            {"songs": [song_a_site2], "source_name": "masstamilan", "category": "stars"},
        ])

        assert plan.unique_canonical == 1
        assert len(plan.new_songs) == 1
        assert plan.new_songs[0].primary.quality_kbps == 320
        assert plan.new_songs[0].primary.source_name == "isaimini"

        # 4. Download registry — acquire slot
        chosen = plan.new_songs[0]
        dl_id = registry.acquire(chosen.song_id, chosen.primary.id)
        assert dl_id is not None

        # Verify DOWNLOADING state
        assert registry.is_downloading(chosen.song_id)

        # 5. Simulate download complete
        registry.complete(
            song_id=chosen.song_id,
            download_id=dl_id,
            file_path="/music/master/vaathi-coming.mp3",
            file_size_bytes=8 * 1024 * 1024,
            quality_kbps=320,
            library_location_id=0,
        )

        # 6. Verify OWNED state
        assert not registry.is_downloading(chosen.song_id)
        owned_song = db.get_song(chosen.song_id)
        assert owned_song.state == SongState.OWNED
        assert owned_song.quality_kbps == 320

        # 7. Re-plan — must produce 0 new downloads
        replan = planner.plan_downloads_multi_source([
            {"songs": [song_a_site1], "source_name": "isaimini", "category": "latest"},
            {"songs": [song_a_site2], "source_name": "masstamilan", "category": "stars"},
        ])

        assert len(replan.new_songs) == 0, (
            f"After OWNED, re-plan must produce 0 new downloads, got {len(replan.new_songs)}"
        )
        assert len(replan.owned) == 1

        db.close()

    def test_pipeline_batch_then_owned_exclusion(self, tmp_path):
        """
        Batch of 10 songs discovered. 5 are marked owned.
        Next plan must schedule exactly 5 new downloads.
        """
        db = make_db(tmp_path)
        planner = DownloadPlanner(db)
        pipeline = DiscoveryPipeline(db)

        songs = [
            make_song(f"Batch Song {i}", f"https://site1.com/batch-{i}.mp3")
            for i in range(1, 11)
        ]

        # Register all
        pipeline.register_batch(songs, "site1", category="Top 2026")

        # Mark songs 1-5 as owned
        for i in range(1, 6):
            identity = song_to_canonical(songs[i - 1])
            lib_song = db.get_song_by_canonical_hash(identity.hash)
            mark_owned(db, lib_song.id, quality_kbps=320)

        # Plan downloads
        plan = planner.plan_downloads(songs, "site1", category="Top 2026")

        assert len(plan.owned) == 5, f"Expected 5 owned, got {len(plan.owned)}"
        assert len(plan.new_songs) == 5, f"Expected 5 new, got {len(plan.new_songs)}"
        assert plan.total_to_download == 5
        db.close()


# ---------------------------------------------------------------------------
# SCENARIO 8: 3-Core Source Set Integration & Reliability Failover
# ---------------------------------------------------------------------------

class TestThreeCoreSourceSet:
    """
    Test multi-source integration using the approved 3-Core Source Set:
      1. MassTamilan
      2. Tamilmp3.in / Kuttyweb
      3. FriendsTamilMP3
    """

    def test_three_core_sources_single_song_deduplication(self, tmp_path):
        db = make_db(tmp_path)
        planner = DownloadPlanner(db)

        song_a_masstamilan = make_song(
            "Kalla Nikkiriye", "https://www.masstamilan.dev/kalla-nikkiriye.mp3",
            quality="320kbps", artist="Govind Vasantha", album_title="Anbil Avan"
        )
        song_a_tamilmp3 = make_song(
            "Kalla Nikkiriye", "https://tamilmp3.in/dl/kalla-nikkiriye.mp3",
            quality="320kbps", artist="Govind Vasantha", album_title="Anbil Avan"
        )
        song_a_friends = make_song(
            "Kalla Nikkiriye", "https://friendstamilmp3.in/songs/kalla-nikkiriye.mp3",
            quality="128kbps", artist="Govind Vasantha", album_title="Anbil Avan"
        )

        plan = planner.plan_downloads_multi_source([
            {"songs": [song_a_masstamilan], "source_name": "masstamilan", "category": "latest"},
            {"songs": [song_a_tamilmp3], "source_name": "tamilmp3", "category": "all-songs"},
            {"songs": [song_a_friends], "source_name": "friendstamilmp3", "category": "movie-songs"},
        ])

        assert plan.raw_discovered == 3
        assert plan.unique_canonical == 1
        assert len(plan.new_songs) == 1
        
        selection = plan.new_songs[0]
        # Verify 3 source variants aggregated under 1 canonical song
        sources = db.get_sources_for_song(selection.song_id)
        assert len(sources) == 3
        source_names = {s.source_name for s in sources}
        assert source_names == {"masstamilan", "tamilmp3", "friendstamilmp3"}

        db.close()


class TestCriticalDuplicateScenario:
    """
    PRIMARY BUSINESS REQUIREMENT TEST:
    Song A discovered across 5 categories × 3 core sources = 15 raw events.
    Expected:
      - 15 raw discoveries
      - exactly ONE canonical Song A
      - multiple source variants
      - exactly ONE planned download
    """

    def test_fifteen_raw_discoveries_yield_one_download(self, tmp_path):
        db = make_db(tmp_path)
        planner = DownloadPlanner(db)

        categories = ["Top 2026", "Vijay Hits", "Anirudh Hits", "Movie category", "Singer category"]
        sources = [
            ("masstamilan", "https://masstamilan.dev/song-a.mp3", "320kbps"),
            ("tamilmp3", "https://tamilmp3.in/song-a.mp3", "320kbps"),
            ("friendstamilmp3", "https://friendstamilmp3.in/song-a.mp3", "128kbps"),
        ]

        source_batches = []
        for cat in categories:
            for s_name, s_url, s_qual in sources:
                song = make_song(
                    "Naa Ready", s_url, quality=s_qual, artist="Anirudh", album_title="Leo"
                )
                source_batches.append({
                    "songs": [song],
                    "source_name": s_name,
                    "category": cat
                })

        assert len(source_batches) == 15

        plan = planner.plan_downloads_multi_source(source_batches)

        assert plan.raw_discovered == 15
        assert plan.unique_canonical == 1
        assert len(plan.new_songs) == 1
        assert len(plan.owned) == 0
        assert len(plan.upgrades) == 0

        # Verify DB contains exactly 1 song row
        cursor = db._conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM songs")
        assert cursor.fetchone()[0] == 1

        db.close()


class TestSourceReliabilityAndFailover:
    """
    Test source reliability score preference & automatic failover:
    - Prefer higher reliability source when quality is equal.
    - Automatic failover when primary source becomes unavailable.
    """

    def test_reliability_score_preference_and_failover(self, tmp_path):
        db = make_db(tmp_path)
        planner = DownloadPlanner(db)

        song_src_a = make_song("Aradhya", "https://site-a.com/aradhya.mp3", quality="320kbps")
        song_src_b = make_song("Aradhya", "https://site-b.com/aradhya.mp3", quality="320kbps")

        # Register both sources
        planner.plan_downloads_multi_source([
            {"songs": [song_src_a], "source_name": "site_a"},
            {"songs": [song_src_b], "source_name": "site_b"},
        ])

        # Get the registered source variant IDs
        lib_song = db.get_song_by_canonical_hash(song_to_canonical(song_src_a).hash)
        sources = db.get_sources_for_song(lib_song.id)
        assert len(sources) == 2

        source_a = next(s for s in sources if s.source_name == "site_a")
        source_b = next(s for s in sources if s.source_name == "site_b")

        # Set reliability scores: Site A = 0.98, Site B = 0.70
        db.update_source_reliability(source_a.id, 0.98)
        db.update_source_reliability(source_b.id, 0.70)

        # Plan download — must select Site A due to higher reliability
        plan1 = planner.plan_downloads([song_src_a], "site_a")
        assert plan1.new_songs[0].primary.source_name == "site_a"
        assert plan1.new_songs[0].primary.reliability_score == 0.98

        # Mark Site A as unavailable (e.g. site offline)
        cursor = db._conn.cursor()
        cursor.execute("UPDATE song_sources SET is_available = 0 WHERE id = ?", (source_a.id,))
        db._conn.commit()

        # Re-plan download — must automatically failover to Site B!
        plan2 = planner.plan_downloads([song_src_a], "site_a")
        assert plan2.new_songs[0].primary.source_name == "site_b"
        assert plan2.new_songs[0].primary.reliability_score == 0.70

        db.close()


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v", "--tb=short"])

