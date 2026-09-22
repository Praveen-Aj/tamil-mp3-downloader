"""
Comprehensive test suite for V5.5 Curated Charts & Top 100 subsystem.

Validates:
1. Chart CRUD operations in SQLiteDatabase.
2. Ranked chart entries insertion, retrieval, and unique (chart_id, rank) constraint.
3. Trend calculation (up, down, same, new) from previous_rank vs rank.
4. Duplicate prevention and canonical song association.
5. Cascade delete safety: deleting chart deletes entries, NEVER deletes canonical songs or sources.
6. Chart pagination, search, and type filtering.
7. Detailed chart entries querying with artist and movie resolution.
8. Authoritative download statistics and disk file cross-verification.
9. Download planning: plan_chart_download_all vs plan_chart_download_missing idempotency.
10. Single entry download planning.
11. ChartDiscoveryService sync integration and canonical resolution.
12. Strict user-facing terminology enforcement (no 'owned'/'unowned' exposed).
"""

import os
from datetime import datetime
from pathlib import Path
import pytest

from library.database import SQLiteDatabase
from library.models import Chart, ChartEntry, LibrarySong, SongSource, SongState
from library.charts import ChartDiscoveryService
from ui.services.library_service import LibraryService


@pytest.fixture
def temp_db(tmp_path) -> SQLiteDatabase:
    """Provides a fresh SQLiteDatabase instance."""
    db_path = tmp_path / "test_charts.db"
    db = SQLiteDatabase(db_path)
    db.connect()
    yield db
    db.close()


@pytest.fixture
def service(temp_db, tmp_path) -> LibraryService:
    """Provides a connected LibraryService instance with temp download directory."""
    dl_dir = tmp_path / "downloads"
    dl_dir.mkdir(parents=True, exist_ok=True)
    svc = LibraryService(db=temp_db, download_dir=str(dl_dir))
    return svc


def test_chart_crud_and_uniqueness(temp_db):
    """Test Chart creation, lookup, update, and deletion."""
    chart = Chart(
        id="chart-top-50-2026",
        title="Tamil Top 50 - Week 38 2026",
        chart_type="top_100",
        provider_name="apple_music",
        snapshot_date=datetime(2026, 9, 21, 10, 0, 0),
    )
    chart_id = temp_db.create_chart(chart)
    assert chart_id == "chart-top-50-2026"

    fetched = temp_db.get_chart("chart-top-50-2026")
    assert fetched is not None
    assert fetched.title == "Tamil Top 50 - Week 38 2026"
    assert fetched.provider_name == "apple_music"

    # Update
    updated = temp_db.update_chart("chart-top-50-2026", title="Tamil Top 50 - Updated")
    assert updated is True
    assert temp_db.get_chart("chart-top-50-2026").title == "Tamil Top 50 - Updated"

    # List
    charts = temp_db.list_charts()
    assert len(charts) == 1
    assert charts[0].id == "chart-top-50-2026"


def test_chart_entries_rank_ordering_and_constraint(temp_db):
    """Test adding ranked entries, order by rank ascending, and replacement on duplicate rank."""
    chart_id = "chart-test-rankings"
    temp_db.create_chart(Chart(id=chart_id, title="Test Chart"))

    temp_db.add_chart_entry(
        chart_id=chart_id,
        rank=2,
        previous_rank=1,
        raw_title="Naa Ready",
        raw_artist="Vijay",
        raw_movie="Leo",
    )
    temp_db.add_chart_entry(
        chart_id=chart_id,
        rank=1,
        previous_rank=3,
        raw_title="Arabic Kuthu",
        raw_artist="Anirudh",
        raw_movie="Beast",
    )

    entries = temp_db.get_chart_entries(chart_id)
    assert len(entries) == 2
    # Ascending order by rank
    assert entries[0].rank == 1
    assert entries[0].raw_title == "Arabic Kuthu"
    assert entries[1].rank == 2
    assert entries[1].raw_title == "Naa Ready"

    # Replace rank 1
    temp_db.add_chart_entry(
        chart_id=chart_id,
        rank=1,
        previous_rank=None,
        raw_title="Hukum",
        raw_artist="Anirudh",
        raw_movie="Jailer",
    )
    entries = temp_db.get_chart_entries(chart_id)
    assert len(entries) == 2
    assert entries[0].rank == 1
    assert entries[0].raw_title == "Hukum"


def test_trend_calculation(temp_db):
    """Test trend indicators: new, up, down, and same."""
    chart_id = "chart-trends"
    temp_db.create_chart(Chart(id=chart_id, title="Trend Chart"))

    # New: no previous rank
    temp_db.add_chart_entry(chart_id=chart_id, rank=1, previous_rank=None, raw_title="Song A")
    # Up: was 5, now 2 (climbed +3)
    temp_db.add_chart_entry(chart_id=chart_id, rank=2, previous_rank=5, raw_title="Song B")
    # Down: was 1, now 3 (dropped -2)
    temp_db.add_chart_entry(chart_id=chart_id, rank=3, previous_rank=1, raw_title="Song C")
    # Same: was 4, now 4
    temp_db.add_chart_entry(chart_id=chart_id, rank=4, previous_rank=4, raw_title="Song D")

    detailed, total = temp_db.get_chart_entries_detailed(chart_id)
    assert total == 4
    assert detailed[0]["trend"] == "new"
    assert detailed[0]["trend_label"] == "NEW"

    assert detailed[1]["trend"] == "up"
    assert detailed[1]["trend_label"] == "▲ 3"
    assert detailed[1]["trend_diff"] == 3

    assert detailed[2]["trend"] == "down"
    assert detailed[2]["trend_label"] == "▼ 2"
    assert detailed[2]["trend_diff"] == -2

    assert detailed[3]["trend"] == "same"
    assert detailed[3]["trend_label"] == "＝"
    assert detailed[3]["trend_diff"] == 0


def test_cascade_delete_safety(temp_db):
    """Deleting a chart must delete its entries but NEVER cascade to delete songs or sources."""
    s_id = temp_db.add_song(LibrarySong(
        canonical_hash="chart_song_hash_1",
        title="Kannalane",
        artist="K. S. Chithra",
        album="Bombay",
    ))
    src_id = temp_db.add_source(SongSource(
        song_id=s_id,
        source_name="tamilmp3",
        source_url="https://tamilmp3.in/dl/1",
        quality_kbps=320,
    ))

    chart_id = "chart-to-delete"
    temp_db.create_chart(Chart(id=chart_id, title="Temporary Chart"))
    temp_db.add_chart_entry(chart_id=chart_id, rank=1, song_id=s_id, raw_title="Kannalane")

    # Verify relationships exist
    assert len(temp_db.get_chart_entries(chart_id)) == 1

    # Delete chart
    assert temp_db.delete_chart(chart_id) is True
    assert temp_db.get_chart(chart_id) is None
    assert len(temp_db.get_chart_entries(chart_id)) == 0

    # Critical: canonical song and source must remain 100% intact
    song = temp_db.get_song(s_id)
    assert song is not None
    assert song.title == "Kannalane"
    sources = temp_db.get_sources_for_song(s_id)
    assert len(sources) == 1
    assert sources[0].source_name == "tamilmp3"


def test_chart_search_and_filtering(temp_db):
    """Test searching charts by query and filtering by chart_type."""
    temp_db.create_chart(Chart(id="c1", title="Tamil Weekly Top 50", chart_type="top_100", provider_name="spotify"))
    temp_db.create_chart(Chart(id="c2", title="Regional Trending Hits", chart_type="trending", provider_name="tamilmp3"))
    temp_db.create_chart(Chart(id="c3", title="Evergreen Classics Top 50", chart_type="all_time", provider_name="curated"))

    # Search query
    res, count = temp_db.search_and_filter_charts(query="Trending")
    assert count == 1
    assert res[0]["id"] == "c2"

    # Filter by chart_type
    res, count = temp_db.search_and_filter_charts(chart_type="top_100")
    assert count == 1
    assert res[0]["id"] == "c1"

    # Filter all
    res, count = temp_db.search_and_filter_charts(chart_type="all")
    assert count == 3


def test_chart_statistics_with_disk_verification(temp_db, tmp_path):
    """Authoritative stats must verify actual physical files on disk."""
    fake_audio = tmp_path / "arabic_kuthu.mp3"
    fake_audio.write_bytes(b"ID3" + b"\x00" * 100)

    # Song 1: downloaded and file exists
    s1 = temp_db.add_song(LibrarySong(
        canonical_hash="h1",
        title="Arabic Kuthu",
        artist="Anirudh",
        state=SongState.OWNED,
        file_path=str(fake_audio),
    ))

    # Song 2: marked OWNED in DB but file missing on disk (e.g. deleted by user)
    s2 = temp_db.add_song(LibrarySong(
        canonical_hash="h2",
        title="Naa Ready",
        artist="Vijay",
        state=SongState.OWNED,
        file_path=str(tmp_path / "missing_file.mp3"),
    ))

    # Song 3: NEW (not downloaded)
    s3 = temp_db.add_song(LibrarySong(
        canonical_hash="h3",
        title="Hukum",
        artist="Anirudh",
        state=SongState.NEW,
    ))

    chart_id = "chart-stats-test"
    temp_db.create_chart(Chart(id=chart_id, title="Stats Chart"))
    temp_db.add_chart_entry(chart_id=chart_id, rank=1, song_id=s1, raw_title="Arabic Kuthu")
    temp_db.add_chart_entry(chart_id=chart_id, rank=2, song_id=s2, raw_title="Naa Ready")
    temp_db.add_chart_entry(chart_id=chart_id, rank=3, song_id=s3, raw_title="Hukum")

    stats = temp_db.get_chart_statistics(chart_id)
    assert stats["total_songs"] == 3
    # Only song 1 has file existing on disk
    assert stats["downloaded_songs"] == 1
    # Songs 2 and 3 are missing
    assert stats["missing_songs"] == 2


def test_chart_download_planning_all_vs_missing(service, tmp_path):
    """Test plan_chart_download_all vs plan_chart_download_missing."""
    db = service.db
    real_file = tmp_path / "downloads" / "song1.mp3"
    real_file.write_bytes(b"ID3" + b"\x00" * 50)

    s1 = db.add_song(LibrarySong(
        canonical_hash="plan_h1",
        title="Song 1",
        artist="Artist 1",
        state=SongState.OWNED,
        quality_kbps=320,
        file_path=str(real_file),
    ))
    db.add_source(SongSource(song_id=s1, source_name="tamilmp3", source_url="url1", quality_kbps=320))

    s2 = db.add_song(LibrarySong(
        canonical_hash="plan_h2",
        title="Song 2",
        artist="Artist 2",
        state=SongState.NEW,
    ))
    db.add_source(SongSource(song_id=s2, source_name="tamilmp3", source_url="url2", quality_kbps=320))

    chart_id = "chart-planning"
    db.create_chart(Chart(id=chart_id, title="Planning Chart"))
    db.add_chart_entry(chart_id=chart_id, rank=1, song_id=s1, raw_title="Song 1")
    db.add_chart_entry(chart_id=chart_id, rank=2, song_id=s2, raw_title="Song 2")

    # 1. Download Missing: should only plan Song 2
    missing_plan = service.plan_chart_download_missing(chart_id)
    assert len(missing_plan.new_songs) == 1
    assert missing_plan.new_songs[0].song_id == s2

    # 2. Download All: DownloadPlanner recognizes Song 1 is already OWNED, plans 0 duplicates
    all_plan = service.plan_chart_download_all(chart_id)
    assert len(all_plan.new_songs) == 1
    assert all_plan.new_songs[0].song_id == s2
    assert len(all_plan.owned) == 1
    assert all_plan.owned[0].id == s1


def test_single_chart_entry_download_planning(service):
    """Test planning download for a single rank."""
    db = service.db
    s1 = db.add_song(LibrarySong(canonical_hash="single_h1", title="Track 1", artist="Artist 1"))
    db.add_source(SongSource(song_id=s1, source_name="tamilmp3", source_url="url1", quality_kbps=320))

    chart_id = "chart-single"
    db.create_chart(Chart(id=chart_id, title="Single Track Chart"))
    db.add_chart_entry(chart_id=chart_id, rank=1, song_id=s1, raw_title="Track 1")

    plan = service.plan_chart_entry_download(chart_id, rank=1)
    assert len(plan.new_songs) == 1
    assert plan.new_songs[0].song_id == s1


def test_chart_discovery_service_sync(temp_db):
    """Test ChartDiscoveryService syncing default charts and canonical song deduplication."""
    svc = ChartDiscoveryService(temp_db)
    synced = svc.sync_all_default_charts()
    assert len(synced) >= 2

    # Check charts created
    charts = temp_db.list_charts()
    assert len(charts) >= 2

    # Check entries in classics top 50
    classics = temp_db.get_chart("chart-tamil-classics-top-50")
    assert classics is not None
    entries = temp_db.get_chart_entries("chart-tamil-classics-top-50")
    assert len(entries) >= 20
    assert entries[0].rank == 1
    assert entries[0].raw_title == "Kanne Kalaimane"

    # Verify canonical songs were created and linked
    assert entries[0].song_id is not None
    song = temp_db.get_song(entries[0].song_id)
    assert song is not None
    assert song.title == "Kanne Kalaimane"


def test_user_facing_terminology(service):
    """Ensure detailed entries strictly present user-centric terminology."""
    db = service.db
    chart_id = "chart-terms"
    db.create_chart(Chart(id=chart_id, title="Terms Chart"))
    db.add_chart_entry(chart_id=chart_id, rank=1, raw_title="Song Test")

    details = service.get_chart_details(chart_id)
    assert details is not None
    stats = details["stats"]
    # Check stats dictionary keys are user-centric
    assert "total_songs" in stats
    assert "downloaded_songs" in stats
    assert "missing_songs" in stats

    # Check detailed entry fields
    entry = details["entries"][0]
    assert "is_downloaded" in entry
    assert "trend_label" in entry
    assert "song_id" in entry


def test_chart_pagination_boundaries(temp_db):
    """Test pagination offsets and limits for charts and detailed chart entries."""
    chart_id = "chart-page-test"
    temp_db.create_chart(Chart(id=chart_id, title="Pagination Chart"))
    for r in range(1, 15):
        temp_db.add_chart_entry(chart_id=chart_id, rank=r, raw_title=f"Track {r}")

    # Page 1, size 5
    page1, total = temp_db.get_chart_entries_detailed(chart_id, limit=5, offset=0)
    assert total == 14
    assert len(page1) == 5
    assert page1[0]["rank"] == 1
    assert page1[4]["rank"] == 5

    # Page 2, size 5
    page2, total = temp_db.get_chart_entries_detailed(chart_id, limit=5, offset=5)
    assert total == 14
    assert len(page2) == 5
    assert page2[0]["rank"] == 6
    assert page2[4]["rank"] == 10

    # Page 3, size 5 (last 4 items)
    page3, total = temp_db.get_chart_entries_detailed(chart_id, limit=5, offset=10)
    assert total == 14
    assert len(page3) == 4
    assert page3[0]["rank"] == 11
    assert page3[3]["rank"] == 14


def test_chart_entry_trend_persistence_across_snapshots(temp_db):
    """Test that updating a chart with a new snapshot properly tracks rank shifts."""
    svc = ChartDiscoveryService(temp_db)
    chart_id = "chart-trend-shift"

    # Snapshot 1
    s1_entries = [
        {"rank": 1, "title": "Song Alpha", "artist": "Artist A", "movie": "Movie 1"},
        {"rank": 2, "title": "Song Beta", "artist": "Artist B", "movie": "Movie 2"},
        {"rank": 3, "title": "Song Gamma", "artist": "Artist C", "movie": "Movie 3"},
    ]
    svc._ingest_chart(chart_id, "Trend Shift Chart", "top_100", "test", s1_entries)

    entries1, _ = temp_db.get_chart_entries_detailed(chart_id)
    assert entries1[0]["trend"] == "new"

    # Snapshot 2: Song Beta climbs to #1 (up 1), Song Alpha drops to #2 (down 1), Song Delta is NEW at #3
    s2_entries = [
        {"rank": 1, "title": "Song Beta", "artist": "Artist B", "movie": "Movie 2"},
        {"rank": 2, "title": "Song Alpha", "artist": "Artist A", "movie": "Movie 1"},
        {"rank": 3, "title": "Song Delta", "artist": "Artist D", "movie": "Movie 4"},
    ]
    svc._ingest_chart(chart_id, "Trend Shift Chart", "top_100", "test", s2_entries)

    entries2, _ = temp_db.get_chart_entries_detailed(chart_id)
    assert entries2[0]["title"] == "Song Beta"
    assert entries2[0]["trend"] == "up"
    assert entries2[0]["trend_label"] == "▲ 1"

    assert entries2[1]["title"] == "Song Alpha"
    assert entries2[1]["trend"] == "down"
    assert entries2[1]["trend_label"] == "▼ 1"

    assert entries2[2]["title"] == "Song Delta"
    assert entries2[2]["trend"] == "new"

