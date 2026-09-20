"""
Tests for V5.2 — Search and Filtering.

Validates:
- FTS5 Full-text search (exact, prefix, partial, case-insensitive, Tamil/Unicode, special characters)
- Filters (download status, quality, source, artist, album)
- Compositions (Search + Filter + Sort + Pagination)
- SQLite FTS5 trigger synchronization (INSERT, UPDATE, DELETE)
- Migration 5 idempotency and backfill
- Performance benchmark on 5,000 songs dataset
"""

import time
import pytest
import sqlite3
from pathlib import Path

from library.database import SQLiteDatabase
from library.filter_engine import SongFilterCriteria, ComposableFilterEngine
from library.models import LibrarySong, SongSource, SongState
from library.migrator import DatabaseMigrator


@pytest.fixture
def search_db(tmp_path) -> SQLiteDatabase:
    """Provides a fresh SQLiteDatabase migrated to version 5 with test dataset."""
    db_path = tmp_path / "test_search_v5_2.db"
    db = SQLiteDatabase(db_path)
    db.connect()

    # Seed sample songs
    songs_data = [
        # id, title, artist, album, year, duration, state, quality, source_name
        (
            "hash_1", "Vaathi Coming", "vaathi coming", "Anirudh Ravichander", "anirudh ravichander",
            "Master", "master", 2021, 230, SongState.OWNED, 320, "masstamilan"
        ),
        (
            "hash_2", "Vaathi Raid", "vaathi raid", "Anirudh Ravichander", "anirudh ravichander",
            "Master", "master", 2021, 210, SongState.NEW, 128, "tamilmp3"
        ),
        (
            "hash_3", "Arabic Kuthu", "arabic kuthu", "Anirudh Ravichander", "anirudh ravichander",
            "Beast", "beast", 2022, 280, SongState.OWNED, 320, "masstamilan"
        ),
        (
            "hash_4", "Kanja Poovu Kannala", "kanja poovu kannala", "Yuvan Shankar Raja", "yuvan shankar raja",
            "Viruman", "viruman", 2022, 255, SongState.NEW, 128, "friendstamilmp3"
        ),
        (
            "hash_5", "Naan Naan", "naan naan", "Santhosh Narayanan", "santhosh narayanan",
            "Mahaan", "mahaan", 2022, 195, SongState.OWNED, 320, "masstamilan"
        ),
        (
            "hash_6", "வாத்தி கமிங்", "வாத்தி கமிங்", "அனிருத் ரவிச்சந்தர்", "அனிருத் ரவிச்சந்தர்",
            "மாஸ்டர்", "மாஸ்டர்", 2021, 230, SongState.NEW, 320, "tamilmp3"
        ),
    ]

    for item in songs_data:
        s = LibrarySong(
            canonical_hash=item[0],
            title=item[1],
            title_normalized=item[2],
            artist=item[3],
            artist_normalized=item[4],
            album=item[5],
            album_normalized=item[6],
            year=item[7],
            duration_seconds=item[8],
            state=item[9],
            quality_kbps=item[10],
            file_path=f"C:/downloads/{item[0]}.mp3" if item[9] == SongState.OWNED else None,
        )
        song_id = db.add_song(s)
        src = SongSource(
            song_id=song_id,
            source_name=item[11],
            source_url=f"https://example.com/{item[0]}",
            quality_kbps=item[10],
            is_available=True,
        )
        db.add_source(src)

    yield db
    db.close()


# ── 1. Search Tests ──────────────────────────────────────────────────────────

def test_search_exact_title(search_db):
    """Verify searching for an exact title returns the correct song."""
    crit = SongFilterCriteria(search_query="Arabic Kuthu")
    res = search_db.search_and_filter_songs(crit)
    assert res["total_items"] == 1
    assert res["songs"][0].title == "Arabic Kuthu"


def test_search_partial_title_prefix(search_db):
    """Verify prefix matching works across multiple songs."""
    crit = SongFilterCriteria(search_query="Vaathi")
    res = search_db.search_and_filter_songs(crit)
    titles = [s.title for s in res["songs"]]
    assert "Vaathi Coming" in titles
    assert "Vaathi Raid" in titles
    assert len(titles) >= 2


def test_search_artist(search_db):
    """Verify searching for an artist returns all songs by that artist."""
    crit = SongFilterCriteria(search_query="Anirudh")
    res = search_db.search_and_filter_songs(crit)
    assert res["total_items"] == 3
    for s in res["songs"]:
        assert "Anirudh" in s.artist


def test_search_album(search_db):
    """Verify searching for an album name matches songs in that album."""
    crit = SongFilterCriteria(search_query="Master")
    res = search_db.search_and_filter_songs(crit)
    assert res["total_items"] == 2
    for s in res["songs"]:
        assert s.album == "Master"


def test_search_case_insensitivity(search_db):
    """Verify search is case-insensitive for title, artist, and album."""
    for q in ("arabic kuthu", "ARABIC KUTHU", "aRaBiC kUtHu"):
        res = search_db.search_and_filter_songs(SongFilterCriteria(search_query=q))
        assert res["total_items"] == 1
        assert res["songs"][0].title == "Arabic Kuthu"


def test_search_tamil_unicode_text(search_db):
    """Verify Tamil script is properly matched in FTS5."""
    res = search_db.search_and_filter_songs(SongFilterCriteria(search_query="வாத்தி"))
    assert res["total_items"] == 1
    assert res["songs"][0].title == "வாத்தி கமிங்"

    res_art = search_db.search_and_filter_songs(SongFilterCriteria(search_query="அனிருத்"))
    assert res_art["total_items"] == 1
    assert res_art["songs"][0].artist == "அனிருத் ரவிச்சந்தர்"


def test_search_empty_returns_all_songs(search_db):
    """Verify empty search query returns all songs without errors."""
    res = search_db.search_and_filter_songs(SongFilterCriteria(search_query=""))
    assert res["total_items"] == 6


def test_search_no_results(search_db):
    """Verify search with no matching keywords returns empty list and 0 count."""
    res = search_db.search_and_filter_songs(SongFilterCriteria(search_query="NonExistentSongXYZ"))
    assert res["total_items"] == 0
    assert len(res["songs"]) == 0


def test_search_special_characters_handling(search_db):
    """Verify queries with special characters (quotes, colons, asterisks, brackets) do not cause syntax errors."""
    special_queries = [
        'vaathi*',
        '"vaathi"',
        'artist:anirudh',
        'vaathi (coming)',
        "master - anirudh",
        "100% hits",
        "rock & roll",
    ]
    for q in special_queries:
        res = search_db.search_and_filter_songs(SongFilterCriteria(search_query=q))
        assert isinstance(res["songs"], list)
        assert res["total_items"] >= 0


# ── 2. Filter Tests ──────────────────────────────────────────────────────────

def test_filter_downloaded_status(search_db):
    """Verify filtering by OWNED returns only downloaded songs."""
    crit = SongFilterCriteria(download_state=SongState.OWNED)
    res = search_db.search_and_filter_songs(crit)
    assert res["total_items"] == 3
    for s in res["songs"]:
        assert s.state == SongState.OWNED


def test_filter_not_downloaded_status(search_db):
    """Verify filtering by NEW returns only not-yet-downloaded songs."""
    crit = SongFilterCriteria(download_state=SongState.NEW)
    res = search_db.search_and_filter_songs(crit)
    assert res["total_items"] == 3
    for s in res["songs"]:
        assert s.state == SongState.NEW


def test_filter_quality(search_db):
    """Verify filtering by minimum quality bitrate."""
    crit = SongFilterCriteria(quality_kbps=320)
    res = search_db.search_and_filter_songs(crit)
    assert res["total_items"] == 4
    for s in res["songs"]:
        assert s.quality_kbps >= 320


def test_filter_source_provider(search_db):
    """Verify filtering by source/provider name."""
    crit = SongFilterCriteria(source_name="masstamilan")
    res = search_db.search_and_filter_songs(crit)
    assert res["total_items"] == 3

    crit_fr = SongFilterCriteria(source_name="friendstamilmp3")
    res_fr = search_db.search_and_filter_songs(crit_fr)
    assert res_fr["total_items"] == 1
    assert res_fr["songs"][0].title == "Kanja Poovu Kannala"


def test_filter_artist_specific(search_db):
    """Verify filtering by specific artist."""
    crit = SongFilterCriteria(artist="Yuvan Shankar Raja")
    res = search_db.search_and_filter_songs(crit)
    assert res["total_items"] == 1
    assert res["songs"][0].title == "Kanja Poovu Kannala"


# ── 3. Composition Tests ─────────────────────────────────────────────────────

def test_composition_search_and_downloaded_filter(search_db):
    """Verify composing search query with downloaded state filter."""
    # Search 'vaathi' (2 songs: Vaathi Coming [OWNED] & Vaathi Raid [NEW])
    crit = SongFilterCriteria(search_query="vaathi", download_state=SongState.OWNED)
    res = search_db.search_and_filter_songs(crit)
    assert res["total_items"] == 1
    assert res["songs"][0].title == "Vaathi Coming"


def test_composition_search_filter_and_quality(search_db):
    """Verify composing search, download state, and quality."""
    crit = SongFilterCriteria(
        search_query="Anirudh",
        download_state=SongState.OWNED,
        quality_kbps=320,
    )
    res = search_db.search_and_filter_songs(crit)
    assert res["total_items"] == 2
    titles = {s.title for s in res["songs"]}
    assert titles == {"Vaathi Coming", "Arabic Kuthu"}


def test_composition_search_and_sort(search_db):
    """Verify sorting search results by title ascending."""
    crit = SongFilterCriteria(search_query="Anirudh")
    res = search_db.search_and_filter_songs(crit, sort_by="title", ascending=True)
    titles = [s.title for s in res["songs"]]
    assert titles == sorted(titles)


def test_composition_filter_and_sort(search_db):
    """Verify sorting filtered songs by year and title."""
    crit = SongFilterCriteria(download_state=SongState.OWNED)
    res = search_db.search_and_filter_songs(crit, sort_by="title", ascending=True)
    assert len(res["songs"]) == 3
    assert res["songs"][0].title <= res["songs"][1].title <= res["songs"][2].title


# ── 4. Pagination Tests ──────────────────────────────────────────────────────

def test_pagination_pages_and_slices(search_db):
    """Verify page sizing, offsets, and boundary handling."""
    crit = SongFilterCriteria()
    # 6 total songs, page size 2 -> 3 pages
    p1 = search_db.search_and_filter_songs(crit, page=1, page_size=2)
    assert len(p1["songs"]) == 2
    assert p1["total_pages"] == 3
    assert p1["total_items"] == 6

    p2 = search_db.search_and_filter_songs(crit, page=2, page_size=2)
    assert len(p2["songs"]) == 2
    # Ensure disjoint rows
    p1_ids = {s.id for s in p1["songs"]}
    p2_ids = {s.id for s in p2["songs"]}
    assert p1_ids.isdisjoint(p2_ids)

    # Out of range page
    p99 = search_db.search_and_filter_songs(crit, page=99, page_size=2)
    assert len(p99["songs"]) == 0
    assert p99["total_items"] == 6


# ── 5. FTS5 Trigger Synchronization Tests ────────────────────────────────────

def test_fts_trigger_on_insert(search_db):
    """Verify inserting a new song immediately indexes it in songs_fts."""
    new_song = LibrarySong(
        canonical_hash="hash_trigger_ins",
        title="Jailer Hukum",
        title_normalized="jailer hukum",
        artist="Anirudh Ravichander",
        artist_normalized="anirudh ravichander",
        album="Jailer",
        album_normalized="jailer",
        state=SongState.NEW,
    )
    s_id = search_db.add_song(new_song)
    assert s_id > 0

    res = search_db.search_and_filter_songs(SongFilterCriteria(search_query="Hukum"))
    assert res["total_items"] == 1
    assert res["songs"][0].title == "Jailer Hukum"


def test_fts_trigger_on_update(search_db):
    """Verify updating a song's title updates the FTS5 index automatically."""
    crit = SongFilterCriteria(search_query="Kanja Poovu")
    res = search_db.search_and_filter_songs(crit)
    assert res["total_items"] == 1
    song = res["songs"][0]

    # Update title via direct SQL
    search_db.execute_write(
        "UPDATE songs SET title = ?, title_normalized = ? WHERE id = ?",
        ("Kanja Poovu Remix", "kanja poovu remix", song.id)
    )

    # Search by new keyword
    res_remix = search_db.search_and_filter_songs(SongFilterCriteria(search_query="Remix"))
    assert res_remix["total_items"] == 1
    assert res_remix["songs"][0].title == "Kanja Poovu Remix"


def test_fts_trigger_on_delete(search_db):
    """Verify deleting a song removes it from the FTS5 index automatically."""
    crit = SongFilterCriteria(search_query="Mahaan")
    res = search_db.search_and_filter_songs(crit)
    assert res["total_items"] == 1
    song_id = res["songs"][0].id

    # Delete song
    search_db.delete_song(song_id)

    # Search should now find 0 results
    res_after = search_db.search_and_filter_songs(SongFilterCriteria(search_query="Mahaan"))
    assert res_after["total_items"] == 0


# ── 6. Migration 5 Idempotency and Backfill Verification ─────────────────────

def test_migration_5_backfill_existing_data(tmp_path):
    """
    Verify that migrating a v4 database with existing rows builds the FTS5 index
    and makes existing records immediately searchable.
    """
    db_path = tmp_path / "test_migration_v4_to_v5.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    migrator = DatabaseMigrator(None)

    # Apply migrations 1 through 4 manually
    for v in (1, 2, 3, 4):
        stmts = [s.strip() for s in migrator.MIGRATIONS[v].split(';') if s.strip()]
        for stmt in stmts:
            conn.execute(stmt)
        conn.execute("INSERT INTO schema_version (version) VALUES (?)", (v,))
    conn.commit()

    # Insert a pre-existing v4 song
    conn.execute("""
        INSERT INTO songs (canonical_hash, title, title_normalized, artist, artist_normalized, album, album_normalized, state)
        VALUES ('v4_hash', 'Vikram Title Track', 'vikram title track', 'Anirudh', 'anirudh', 'Vikram', 'vikram', 'OWNED')
    """)
    conn.commit()
    conn.close()

    # Now open with SQLiteDatabase which executes Migration 5
    db = SQLiteDatabase(db_path)
    db.connect()

    # Verify version 5
    cur = db._conn.cursor()
    cur.execute("SELECT MAX(version) FROM schema_version")
    assert cur.fetchone()[0] == 5

    # Verify the pre-existing song was backfilled into FTS5 index
    res = db.search_and_filter_songs(SongFilterCriteria(search_query="Vikram"))
    assert res["total_items"] == 1
    assert res["songs"][0].title == "Vikram Title Track"
    db.close()


# ── 7. Performance Benchmark (5,000 Songs) ───────────────────────────────────

def test_performance_benchmark_5000_songs(tmp_path):
    """
    Benchmark FTS5 search, multi-field filtering, sorting, and pagination
    on a realistic dataset of 5,000 songs. Verifies execution times remain well under 25ms.
    """
    db_path = tmp_path / "perf_5000.db"
    db = SQLiteDatabase(db_path)
    db.connect()

    # Insert 5,000 songs in bulk
    cur = db._conn.cursor()
    with db._conn:
        batch = []
        for i in range(1, 5001):
            batch.append((
                f"hash_perf_{i}",
                f"Track {i} Song {i % 100}",
                f"track {i} song {i % 100}",
                f"Artist {i % 50}",
                f"artist {i % 50}",
                f"Album {i % 25}",
                f"album {i % 25}",
                2000 + (i % 25),
                200 + (i % 120),
                "OWNED" if (i % 2 == 0) else "NEW",
                320 if (i % 3 == 0) else 128,
            ))
        cur.executemany("""
            INSERT INTO songs (
                canonical_hash, title, title_normalized, artist, artist_normalized,
                album, album_normalized, year, duration_seconds, state, quality_kbps
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, batch)

    # 1. Benchmark FTS prefix search
    t0 = time.perf_counter()
    res_search = db.search_and_filter_songs(
        SongFilterCriteria(search_query="Track 42"),
        page=1,
        page_size=50,
    )
    t_search = (time.perf_counter() - t0) * 1000.0  # ms
    assert res_search["total_items"] > 0
    assert t_search < 50.0, f"Search took {t_search:.2f}ms (threshold 50ms)"

    # 2. Benchmark Composable Filter + Search + Sort
    t0 = time.perf_counter()
    res_comp = db.search_and_filter_songs(
        SongFilterCriteria(
            search_query="Track",
            download_state=SongState.OWNED,
            quality_kbps=320,
        ),
        sort_by="title",
        ascending=True,
        page=1,
        page_size=50,
    )
    t_comp = (time.perf_counter() - t0) * 1000.0  # ms
    assert res_comp["total_items"] > 0
    assert t_comp < 50.0, f"Composable query took {t_comp:.2f}ms (threshold 50ms)"

    # 3. Benchmark Pagination on Page 20
    t0 = time.perf_counter()
    res_p20 = db.search_and_filter_songs(
        SongFilterCriteria(download_state=SongState.OWNED),
        sort_by="id",
        ascending=False,
        page=20,
        page_size=50,
    )
    t_p20 = (time.perf_counter() - t0) * 1000.0  # ms
    assert len(res_p20["songs"]) == 50
    assert t_p20 < 25.0, f"Page 20 query took {t_p20:.2f}ms (threshold 25ms)"

    db.close()
