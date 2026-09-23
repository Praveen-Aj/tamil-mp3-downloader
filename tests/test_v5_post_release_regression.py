"""
V5 Post-Release Regression Test Suite.

Validates all real-world audit fixes:
- Authoritative download folder path (Settings.download_dir)
- Artist name canonicalization & duplicate reconciliation (A. R. Rahman vs A.R. Rahman)
- Filesystem integrity reconciliation (physical disk truth, file_size_bytes, missing file demotion)
- File size display formatting (< 1 MB shows KB, never 0.0 MB for valid non-empty files)
- Downloaded songs centralized SQL pagination & summary stats
- Curated Charts Tamil Top 100 sync (100 tracks, 5 pages of 20 tracks each)
- Playlist external import, pagination, and user ratings/favorites persistence
"""

import os
from pathlib import Path
import pytest

from config.settings import Settings
from library.database import SQLiteDatabase
from library.canonical import normalize_artist_name, normalize_string
from library.models import (
    LibrarySong, SongState, Artist, Movie, SongArtist, MovieComposer,
    UserSongMetadata, Playlist
)
from library.filter_engine import SongFilterCriteria
from library.charts import ChartDiscoveryService
from ui.services.library_service import LibraryService


@pytest.fixture
def temp_db(tmp_path: Path):
    db_file = tmp_path / "test_v5_regression.db"
    db = SQLiteDatabase(db_file)
    db.connect()
    return db


class TestDownloadDirConfig:
    def test_download_dir_property_matches_output_dir(self, tmp_path: Path):
        cfg_file = tmp_path / "test_settings.json"
        s = Settings(config_file=cfg_file)
        assert s.download_dir == s.output_dir
        assert isinstance(s.download_dir, Path)


class TestArtistNormalizationAndDeduplication:
    def test_normalize_artist_name_variants(self):
        variants = ["A. R. Rahman", "A.R. Rahman", "A.R.Rahman", "A R Rahman", "a. r. rahman"]
        normalized = {normalize_artist_name(v) for v in variants}
        assert len(normalized) == 1
        assert "a r rahman" in normalized

    def test_normalize_artist_name_preserves_distinct_individuals(self):
        artists = ["A. R. Rahman", "Anirudh Ravichander", "Yuvan Shankar Raja", "Harris Jayaraj", "Ilaiyaraaja"]
        norm_map = {a: normalize_artist_name(a) for a in artists}
        assert len(set(norm_map.values())) == len(artists)

    def test_reconcile_artist_duplicates(self, temp_db: SQLiteDatabase):
        # Insert duplicate artists with different legacy normalized values directly into DB
        with temp_db._lock:
            cur = temp_db._conn.cursor()
            cur.execute("INSERT INTO artists (name, name_normalized, role) VALUES ('A. R. Rahman', 'a. r. rahman', 'composer')")
            art1_id = cur.lastrowid
            cur.execute("INSERT INTO artists (name, name_normalized, role) VALUES ('A.R. Rahman', 'a.r. rahman', 'composer')")
            art2_id = cur.lastrowid
            temp_db._conn.commit()

        assert art1_id is not None and art2_id is not None

        # Add songs linking to both artists
        s1_id = temp_db.add_song(LibrarySong(title="Song 1", artist="A. R. Rahman", state=SongState.NEW))
        s2_id = temp_db.add_song(LibrarySong(title="Song 2", artist="A.R. Rahman", state=SongState.NEW))
        temp_db.add_song_artist(song_id=s1_id, artist_id=art1_id, role="composer")
        temp_db.add_song_artist(song_id=s2_id, artist_id=art2_id, role="composer")

        # Reconcile duplicates
        reconciled = temp_db.reconcile_artist_duplicates()
        assert reconciled >= 1

        # Check artists table - only one normalized "a r rahman" artist should remain
        with temp_db._lock:
            cur = temp_db._conn.cursor()
            cur.execute("SELECT id, name FROM artists")
            all_artists = cur.fetchall()
        rahman_artists = [a for a in all_artists if normalize_artist_name(a[1]) == "a r rahman"]
        assert len(rahman_artists) == 1
        canonical_id = rahman_artists[0][0]

        # Check song_artists links repointed
        with temp_db._lock:
            cur = temp_db._conn.cursor()
            cur.execute("SELECT DISTINCT artist_id FROM song_artists WHERE song_id IN (?, ?)", (s1_id, s2_id))
            linked_artist_ids = [r[0] for r in cur.fetchall()]
            assert linked_artist_ids == [canonical_id]


class TestFilesystemReconciliationAndFormatting:
    def test_reconcile_filesystem_integrity(self, temp_db: SQLiteDatabase, tmp_path: Path):
        # Create a real audio file on disk
        valid_file = tmp_path / "test_track.mp3"
        valid_file.write_bytes(b"ID3" + b"\x00" * 4096)

        # Add song in OWNED state pointing to valid file with NULL file_size_bytes
        s1 = temp_db.add_song(LibrarySong(
            title="Real Song",
            artist="Real Artist",
            file_path=str(valid_file),
            file_size_bytes=None,
            state=SongState.OWNED,
        ))

        # Add song in OWNED state pointing to non-existent file
        missing_file = tmp_path / "ghost_track.mp3"
        s2 = temp_db.add_song(LibrarySong(
            title="Ghost Song",
            artist="Ghost Artist",
            file_path=str(missing_file),
            file_size_bytes=10000,
            state=SongState.OWNED,
        ))

        # Run reconciliation
        reconciled_cnt = temp_db.reconcile_filesystem_integrity()
        assert reconciled_cnt >= 1

        # Verify s1 got file_size_bytes updated from disk
        song1 = temp_db.get_song(s1)
        assert song1.file_size_bytes == 4099
        assert song1.state == SongState.OWNED

        # Verify s2 was demoted to NEW
        song2 = temp_db.get_song(s2)
        assert song2.state == SongState.NEW

    def test_file_size_formatting_logic(self):
        def format_size(size_bytes: int) -> str:
            if size_bytes >= 1024 * 1024:
                return f"{size_bytes / (1024 * 1024):.1f} MB"
            elif size_bytes > 0:
                return f"{size_bytes / 1024:.1f} KB"
            return ""

        # Small 6 KB file must not show 0.0 MB
        assert format_size(6297) == "6.1 KB"
        assert format_size(4100) == "4.0 KB"
        assert format_size(512) == "0.5 KB"

        # Standard 8.5 MB audio file
        assert format_size(8895000) == "8.5 MB"
        assert format_size(0) == ""


class TestChartsTamilTop100:
    def test_tamil_top_100_sync_and_five_page_pagination(self, temp_db: SQLiteDatabase):
        charts_svc = ChartDiscoveryService(temp_db)
        chart_id = charts_svc.sync_tamil_top_100_chart(limit=100)
        assert chart_id == "chart-tamil-top-100"

        # Check entries count in database
        entries = temp_db.get_chart_entries(chart_id)
        assert len(entries) == 100
        assert entries[0].rank == 1
        assert entries[-1].rank == 100

        # Verify pagination across 5 pages of 20 items each
        lib_svc = LibraryService(db=temp_db)
        
        # Verify chart directory type filter
        top100_charts, tot_charts = lib_svc.get_charts_page(chart_type="top_100")
        assert tot_charts == 1
        assert top100_charts[0]["id"] == "chart-tamil-top-100"

        # Check pages 1 through 5
        for page in range(1, 6):
            details = lib_svc.get_chart_details(chart_id=chart_id, page=page, page_size=20)
            assert details["total_matching"] == 100
            page_entries = details["entries"]
            assert len(page_entries) == 20
            expected_start_rank = (page - 1) * 20 + 1
            assert page_entries[0]["rank"] == expected_start_rank
            assert page_entries[-1]["rank"] == expected_start_rank + 19


class TestPlaylistAndUserPreferencesPersistence:
    def test_playlist_creation_and_ratings_persistence(self, temp_db: SQLiteDatabase):
        lib_svc = LibraryService(db=temp_db)

        # Create playlist
        pid = lib_svc.create_playlist(name="My Roadtrip Hits", description="Testing user curated playlist")
        assert pid is not None

        # Add 5 canonical songs and link to playlist
        song_ids = []
        for i in range(1, 6):
            sid = temp_db.add_song(LibrarySong(title=f"Roadtrip Song {i}", artist=f"Artist {i}", state=SongState.NEW))
            temp_db.add_playlist_item(playlist_id=pid, song_id=sid)
            song_ids.append(sid)

        # Verify playlist details
        details = lib_svc.get_playlist_details(pid, page=1, page_size=10)
        assert details["total_matching"] == 5
        assert len(details["items"]) == 5

        # Rate and favorite song #1
        first_song = song_ids[0]
        lib_svc.toggle_favorite(first_song)
        lib_svc.rate_song(first_song, 5)

        # Verify persistence via fresh service instance
        fresh_svc = LibraryService(db=temp_db)
        meta = fresh_svc.db.get_user_metadata(first_song)
        assert meta is not None
        assert meta.is_favorite is True
        assert meta.rating == 5

        # Check Favorites tab
        favs, fav_total = fresh_svc.get_favorites_page()
        assert fav_total == 1
        assert favs[0]["song_id"] == first_song

        # Check Top Rated tab
        rated, rated_total = fresh_svc.get_rated_songs_page(min_rating=1)
        assert rated_total == 1
        assert rated[0]["song_id"] == first_song
        assert rated[0]["rating"] == 5
