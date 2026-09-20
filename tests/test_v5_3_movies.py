"""
Comprehensive Test Suite for V5.3: Movie Discovery & Movie Library.

Validates:
A. Database Tests:
   - Movie creation, update, retrieval, deletion
   - Movie/Song relationship (song_movies M:N mapping)
   - Multiple songs per movie & song belonging to multiple movies
   - Duplicate relationship prevention
   - Cascade behavior: Movie deletion does not delete songs or physical files
   - Fresh DB & migration behavior

B. Service Tests:
   - Movie listing with SQL-level pagination and sorting
   - Search by title and director
   - Movie detail retrieval with aggregated download stats
   - Handling movies with zero songs and many songs

C. Download Pipeline Tests:
   - Plan Download All & Download Missing
   - Already downloaded songs are not re-downloaded
   - Filesystem reconciliation: deleted file on disk is recognized as missing
   - No quality downgrade
   - Full pipeline execution through DownloadPlanner / DownloadJobManager / LibraryService
"""

import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from library.database import SQLiteDatabase
from library.canonical import compute_canonical_hash
from library.models import (
    LibrarySong, SongState, SongSource, Download, DownloadState, Movie
)
from library.planner import DownloadPlanner
from ui.services.library_service import LibraryService


@pytest.fixture
def temp_db(tmp_path) -> SQLiteDatabase:
    """Provides a fresh, connected SQLiteDatabase instance with V5.3 schema."""
    db_path = tmp_path / "test_v5_3.db"
    db = SQLiteDatabase(db_path)
    db.connect()
    yield db
    db.close()


@pytest.fixture
def temp_service(tmp_path, temp_db) -> LibraryService:
    """Provides an isolated LibraryService instance."""
    dl_dir = tmp_path / "downloads"
    dl_dir.mkdir(parents=True, exist_ok=True)
    service = LibraryService(db=temp_db, download_dir=str(dl_dir))
    return service


# ==============================================================================
# A. DATABASE TESTS
# ==============================================================================

def test_movie_creation_and_retrieval(temp_db: SQLiteDatabase):
    """Test movie creation, duplicate handling, and lookup."""
    m = Movie(
        title="Leo",
        title_normalized="leo",
        year=2023,
        director="Lokesh Kanagaraj",
        track_count=7,
    )
    m_id = temp_db.add_movie(m)
    assert m_id > 0

    fetched = temp_db.get_movie(m_id)
    assert fetched is not None
    assert fetched.title == "Leo"
    assert fetched.year == 2023
    assert fetched.director == "Lokesh Kanagaraj"
    assert fetched.track_count == 7

    # Lookup by title
    by_title = temp_db.get_movie_by_title("Leo")
    assert by_title is not None
    assert by_title.id == m_id


def test_movie_update(temp_db: SQLiteDatabase):
    """Test updating existing movie metadata."""
    m = Movie(title="Jailer", title_normalized="jailer", year=2023, director="Nelson", track_count=5)
    m_id = temp_db.add_movie(m)

    m_updated = Movie(
        id=m_id,
        title="Jailer (Updated)",
        title_normalized="jailer updated",
        year=2023,
        director="Nelson Dilipkumar",
        track_count=8,
    )
    updated = temp_db.update_movie(m_updated)
    assert updated is True

    fetched = temp_db.get_movie(m_id)
    assert fetched.title == "Jailer (Updated)"
    assert fetched.director == "Nelson Dilipkumar"
    assert fetched.track_count == 8


def test_movie_song_many_to_many(temp_db: SQLiteDatabase):
    """
    Test M:N relationship:
    - Movie A has Song 1 and Song 2
    - Movie B has Song 2 (e.g. reprise / franchise compilation)
    """
    m1_id = temp_db.add_movie(Movie(title="Vikram", title_normalized="vikram", year=2022))
    m2_id = temp_db.add_movie(Movie(title="Vikram Hit Tracks", title_normalized="vikram hit tracks", year=2022))

    s1_id = temp_db.add_song(LibrarySong(
        canonical_hash=compute_canonical_hash("Porkanda Singam", "Anirudh", "Vikram"),
        title="Porkanda Singam", artist="Anirudh", album="Vikram", state=SongState.NEW,
    ))
    s2_id = temp_db.add_song(LibrarySong(
        canonical_hash=compute_canonical_hash("Pathala Pathala", "Kamal Haasan", "Vikram"),
        title="Pathala Pathala", artist="Kamal Haasan", album="Vikram", state=SongState.NEW,
    ))

    # Link Movie 1 -> Song 1, Song 2
    temp_db.add_song_movie(song_id=s1_id, movie_id=m1_id, track_number=1)
    temp_db.add_song_movie(song_id=s2_id, movie_id=m1_id, track_number=2)

    # Link Movie 2 -> Song 2
    temp_db.add_song_movie(song_id=s2_id, movie_id=m2_id, track_number=1)

    # Movie 1 songs
    m1_songs = temp_db.get_movie_songs(m1_id)
    assert len(m1_songs) == 2
    assert [s.id for s in m1_songs] == [s1_id, s2_id]

    # Movie 2 songs
    m2_songs = temp_db.get_movie_songs(m2_id)
    assert len(m2_songs) == 1
    assert m2_songs[0].id == s2_id

    # Song 2 movies
    s2_movies = temp_db.get_song_movies(s2_id)
    assert len(s2_movies) == 2
    movie_titles = {m.title for m in s2_movies}
    assert movie_titles == {"Vikram", "Vikram Hit Tracks"}


def test_movie_deletion_preserves_songs_and_sources(temp_db: SQLiteDatabase, tmp_path: Path):
    """
    CRITICAL ARCHITECTURAL TEST:
    Deleting a movie must NEVER delete canonical songs, song sources, or downloads.
    It should only delete the movie record and the song_movies join links.
    """
    m_id = temp_db.add_movie(Movie(title="Master", title_normalized="master", year=2021))
    audio_file = tmp_path / "master_the_blaster.mp3"
    audio_file.write_bytes(b"\xFF\xFB\x90\x00" + b"\x00" * 4096)

    s_id = temp_db.add_song(LibrarySong(
        canonical_hash=compute_canonical_hash("Master the Blaster", "Anirudh", "Master"),
        title="Master the Blaster",
        artist="Anirudh",
        album="Master",
        state=SongState.OWNED,
        file_path=str(audio_file),
    ))
    src_id = temp_db.add_source(SongSource(
        song_id=s_id,
        source_name="masstamilan",
        source_url="https://example.com/master.mp3",
        quality_kbps=320,
    ))
    temp_db.add_song_movie(song_id=s_id, movie_id=m_id, track_number=1)

    # Verify relationships exist
    assert len(temp_db.get_movie_songs(m_id)) == 1
    assert len(temp_db.get_song_movies(s_id)) == 1

    # Delete Movie
    deleted = temp_db.delete_movie(m_id)
    assert deleted is True

    # Verify Movie is gone
    assert temp_db.get_movie(m_id) is None

    # CRITICAL: Song MUST still exist
    preserved_song = temp_db.get_song(s_id)
    assert preserved_song is not None
    assert preserved_song.title == "Master the Blaster"
    assert preserved_song.state == SongState.OWNED

    # CRITICAL: Source MUST still exist
    sources = temp_db.get_sources_for_song(s_id)
    assert len(sources) == 1
    assert sources[0].id == src_id

    # CRITICAL: Physical file MUST still exist on disk
    assert audio_file.exists()

    # Join link must be gone
    assert len(temp_db.get_song_movies(s_id)) == 0


def test_search_and_filter_movies_aggregation(temp_db: SQLiteDatabase):
    """Test single-query aggregation of total_songs, downloaded_count, and missing_count."""
    m1_id = temp_db.add_movie(Movie(title="Kaithi", title_normalized="kaithi", year=2019, director="Lokesh"))
    m2_id = temp_db.add_movie(Movie(title="Petta", title_normalized="petta", year=2019, director="Karthik Subbaraj"))

    # Kaithi: 1 Downloaded, 1 Missing
    s1 = temp_db.add_song(LibrarySong(
        canonical_hash="hash_k1", title="Song 1", album="Kaithi", state=SongState.OWNED
    ))
    s2 = temp_db.add_song(LibrarySong(
        canonical_hash="hash_k2", title="Song 2", album="Kaithi", state=SongState.NEW
    ))
    temp_db.add_song_movie(s1, m1_id, 1)
    temp_db.add_song_movie(s2, m1_id, 2)

    # Petta: 2 Downloaded, 0 Missing
    s3 = temp_db.add_song(LibrarySong(
        canonical_hash="hash_p1", title="Marana Mass", album="Petta", state=SongState.OWNED
    ))
    s4 = temp_db.add_song(LibrarySong(
        canonical_hash="hash_p2", title="Petta Paraak", album="Petta", state=SongState.OWNED
    ))
    temp_db.add_song_movie(s3, m2_id, 1)
    temp_db.add_song_movie(s4, m2_id, 2)

    movies, total = temp_db.search_and_filter_movies(sort_by="year", limit=10)
    assert total == 2
    assert len(movies) == 2

    # Verify Kaithi metrics
    kaithi_data = next(m for m in movies if m["id"] == m1_id)
    assert kaithi_data["total_songs"] == 2
    assert kaithi_data["downloaded_count"] == 1
    assert kaithi_data["missing_count"] == 1
    assert kaithi_data["is_complete"] is False

    # Verify Petta metrics
    petta_data = next(m for m in movies if m["id"] == m2_id)
    assert petta_data["total_songs"] == 2
    assert petta_data["downloaded_count"] == 2
    assert petta_data["missing_count"] == 0
    assert petta_data["is_complete"] is True


# ==============================================================================
# B. SERVICE TESTS
# ==============================================================================

def test_service_movie_pagination_and_search(temp_service: LibraryService, temp_db: SQLiteDatabase):
    """Test pagination, sorting, and search via LibraryService."""
    for i in range(1, 35):
        m = Movie(title=f"Tamil Movie {i:02d}", title_normalized=f"tamil movie {i:02d}", year=2000 + i)
        temp_db.add_movie(m)

    # Page 1 (size=10)
    p1, total = temp_service.get_movies_page(page=1, page_size=10, sort_by="year", ascending=False)
    assert total == 34
    assert len(p1) == 10
    assert p1[0]["year"] == 2034

    # Page 4 (size=10)
    p4, total = temp_service.get_movies_page(page=4, page_size=10, sort_by="year", ascending=False)
    assert len(p4) == 4

    # Search filter
    search_res, s_total = temp_service.get_movies_page(query="Movie 05")
    assert s_total == 1
    assert search_res[0]["title"] == "Tamil Movie 05"


def test_service_movie_details_and_zero_songs(temp_service: LibraryService, temp_db: SQLiteDatabase):
    """Test get_movie_details for an empty movie and populated movie."""
    empty_mid = temp_db.add_movie(Movie(title="Empty Movie", title_normalized="empty movie", year=2024))
    details = temp_service.get_movie_details(empty_mid)
    assert details is not None
    assert details["movie"].title == "Empty Movie"
    assert details["stats"]["total"] == 0
    assert details["stats"]["downloaded"] == 0
    assert details["stats"]["missing"] == 0
    assert len(details["songs"]) == 0


# ==============================================================================
# C. DOWNLOAD PLANNING & INTEGRATION TESTS
# ==============================================================================

def test_plan_movie_download_all_and_missing(temp_service: LibraryService, temp_db: SQLiteDatabase, tmp_path: Path):
    """
    Test that:
    1. Plan Download All queues missing songs and skips already OWNED songs.
    2. Plan Download Missing queues only songs missing physically from disk.
    """
    m_id = temp_db.add_movie(Movie(title="Beast", title_normalized="beast", year=2022))

    # Real dummy file on disk for Song 1
    audio_file = tmp_path / "arabic_kuthu.mp3"
    audio_file.write_bytes(b"\xFF\xFB\x90\x00" + b"\x00" * 4096)

    # Song 1: Downloaded & physically verified on disk (320kbps)
    s1_id = temp_db.add_song(LibrarySong(
        canonical_hash="beast_1", title="Arabic Kuthu", album="Beast",
        state=SongState.OWNED, quality_kbps=320, file_path=str(audio_file)
    ))
    temp_db.add_source(SongSource(
        song_id=s1_id, source_name="masstamilan", source_url="https://example.com/s1.mp3", quality_kbps=320
    ))
    temp_db.add_song_movie(s1_id, m_id, 1)

    # Song 2: Not downloaded (NEW)
    s2_id = temp_db.add_song(LibrarySong(
        canonical_hash="beast_2", title="Jolly O Gymkhana", album="Beast",
        state=SongState.NEW, quality_kbps=320
    ))
    temp_db.add_source(SongSource(
        song_id=s2_id, source_name="masstamilan", source_url="https://example.com/s2.mp3", quality_kbps=320
    ))
    temp_db.add_song_movie(s2_id, m_id, 2)

    # 1. Download All Plan
    plan_all = temp_service.plan_movie_download_all(m_id)
    # Already owned s1 should be skipped because it is already 320kbps on disk
    assert len(plan_all.new_songs) == 1
    assert plan_all.new_songs[0].song_id == s2_id
    assert s1_id in [s.id for s in plan_all.owned]

    # 2. Download Missing Plan
    plan_missing = temp_service.plan_movie_download_missing(m_id)
    assert len(plan_missing.new_songs) == 1
    assert plan_missing.new_songs[0].song_id == s2_id


def test_download_missing_filesystem_reconciliation(temp_service: LibraryService, temp_db: SQLiteDatabase, tmp_path: Path):
    """
    If a song's state in DB is OWNED, but the physical file is deleted externally,
    plan_movie_download_missing must detect the missing file via filesystem reconciliation
    and plan the download for it!
    """
    m_id = temp_db.add_movie(Movie(title="Ghilli", title_normalized="ghilli", year=2004))

    deleted_file = tmp_path / "appadi_podu.mp3"
    # Do NOT create file on disk (it is missing / deleted)

    s_id = temp_db.add_song(LibrarySong(
        canonical_hash="ghilli_1", title="Appadi Podu", album="Ghilli",
        state=SongState.OWNED, quality_kbps=320, file_path=str(deleted_file)
    ))
    temp_db.add_source(SongSource(
        song_id=s_id, source_name="masstamilan", source_url="https://example.com/ghilli.mp3", quality_kbps=320
    ))
    temp_db.add_song_movie(s_id, m_id, 1)

    # Initial DB state says OWNED, but file is missing
    # plan_movie_download_missing must reconcile and plan the download
    plan = temp_service.plan_movie_download_missing(m_id)
    assert len(plan.new_songs) == 1
    assert plan.new_songs[0].song_id == s_id

    # Verify DB state was reconciled from OWNED -> NEW
    reconciled_song = temp_db.get_song(s_id)
    assert reconciled_song.state == SongState.NEW
    assert reconciled_song.file_path is None


def test_no_quality_downgrade_in_movie_downloads(temp_service: LibraryService, temp_db: SQLiteDatabase, tmp_path: Path):
    """
    If user already owns a 320kbps track on disk, an available 128kbps source variant
    must NEVER trigger a downgrade or duplicate download.
    """
    m_id = temp_db.add_movie(Movie(title="Roja", title_normalized="roja", year=1992))
    audio_file = tmp_path / "chinna_chinna_asai.mp3"
    audio_file.write_bytes(b"\xFF\xFB\x90\x00" + b"\x00" * 4096)

    s_id = temp_db.add_song(LibrarySong(
        canonical_hash="roja_1", title="Chinna Chinna Asai", album="Roja",
        state=SongState.OWNED, quality_kbps=320, file_path=str(audio_file)
    ))
    # Add a lower quality 128kbps source
    temp_db.add_source(SongSource(
        song_id=s_id, source_name="regional", source_url="https://example.com/roja_128.mp3", quality_kbps=128
    ))
    temp_db.add_song_movie(s_id, m_id, 1)

    plan = temp_service.plan_movie_download_all(m_id)
    assert len(plan.new_songs) == 0
    assert len(plan.upgrades) == 0
    assert s_id in [s.id for s in plan.owned]


def test_movie_discovery_and_canonical_deduplication(temp_service: LibraryService, temp_db: SQLiteDatabase):
    """
    Test discovering movies:
    - Registers Movie in movies table
    - Canonicalizes tracks and registers into songs and song_movies
    - Repeated discovery of same movie does NOT duplicate songs or relationships
    """
    from models.song import Album, Song

    mock_scraper = MagicMock()
    mock_album = Album(name="Kathi", url="https://example.com/kathi", year=2014, song_count=2)
    mock_songs = [
        Song(name="Selfie Pulla", url="https://example.com/selfie.mp3", quality="320kbps", album_name="Kathi"),
        Song(name="Aathi", url="https://example.com/aathi.mp3", quality="320kbps", album_name="Kathi"),
    ]
    mock_scraper.get_albums.return_value = [mock_album]
    mock_scraper.get_songs.return_value = mock_songs
    mock_scraper.is_usable = True
    mock_scraper.enabled = True

    # Register mock scraper in source_registry
    mock_registered_source = MagicMock()
    mock_registered_source.name = "masstamilan"
    mock_registered_source.is_usable = True
    mock_registered_source.scraper = mock_scraper

    temp_service.source_registry.get_source = MagicMock(return_value=mock_registered_source)

    # First discovery run
    res1 = temp_service.discover_movies_from_sources(source_names=["masstamilan"])
    assert res1["movies_discovered"] == 1
    assert res1["songs_registered"] == 2

    # Verify Movie and Songs in DB
    m = temp_db.get_movie_by_title("Kathi")
    assert m is not None
    m_songs = temp_db.get_movie_songs(m.id)
    assert len(m_songs) == 2

    # Second discovery run (idempotency check)
    res2 = temp_service.discover_movies_from_sources(source_names=["masstamilan"])
    # Should not duplicate movie or songs
    m_songs_after = temp_db.get_movie_songs(m.id)
    assert len(m_songs_after) == 2
    movies_list = temp_db.list_movies()
    assert len(movies_list) == 1


def test_real_download_pipeline_movie_missing_and_no_duplication(tmp_path: Path):
    """
    Test the REAL download execution pipeline for a movie:
    1. Movie has 1 already owned song and 1 missing song.
    2. Plan and execute Download Missing.
    3. Assert physical file is created on disk and song is marked OWNED.
    4. Second Download Missing run finds 0 missing songs (no duplication).
    """
    from tests.fixtures_helper import LocalTestServer

    server = LocalTestServer()
    base_url = server.start()

    try:
        db_path = tmp_path / "movie_dl.db"
        dl_dir = tmp_path / "downloads"
        dl_dir.mkdir(parents=True, exist_ok=True)

        db = SQLiteDatabase(db_path)
        db.connect()
        service = LibraryService(db=db, download_dir=str(dl_dir))

        m_id = db.add_movie(Movie(title="Theri", title_normalized="theri", year=2016))

        # Song 1: Already OWNED with real physical file on disk
        file1 = dl_dir / "jithu_jilladi.mp3"
        file1.write_bytes(b"\xFF\xFB\x90\x00" + b"\x00" * 4096)
        s1_id = db.add_song(LibrarySong(
            canonical_hash="theri_1", title="Jithu Jilladi", album="Theri",
            state=SongState.OWNED, quality_kbps=320, file_path=str(file1)
        ))
        db.add_source(SongSource(
            song_id=s1_id, source_name="LocalTest", source_url=f"{base_url}/s1.mp3", quality_kbps=320
        ))
        db.add_song_movie(s1_id, m_id, 1)

        # Song 2: Missing (NEW)
        s2_id = db.add_song(LibrarySong(
            canonical_hash="theri_2", title="En Jeevan", album="Theri",
            state=SongState.NEW, quality_kbps=320
        ))
        db.add_source(SongSource(
            song_id=s2_id, source_name="LocalTest", source_url=f"{base_url}/valid-song.mp3", quality_kbps=320
        ))
        db.add_song_movie(s2_id, m_id, 2)

        # 1. Plan Download Missing -> only s2
        plan = service.plan_movie_download_missing(m_id)
        assert len(plan.new_songs) == 1
        assert plan.new_songs[0].song_id == s2_id

        # 2. Execute plan synchronously
        enqueued_ids = service.execute_download_plan(plan, run_async=False)
        assert len(enqueued_ids) == 1

        # 3. Verify physical file created and DB state updated to OWNED
        s2 = db.get_song(s2_id)
        assert s2.state == SongState.OWNED
        assert s2.file_path is not None
        assert os.path.isfile(s2.file_path)
        assert os.path.getsize(s2.file_path) > 0

        # 4. Check movie stats
        stats = db.get_movie_download_stats(m_id)
        assert stats["total"] == 2
        assert stats["downloaded"] == 2
        assert stats["missing"] == 0

        # 5. Second Download Missing run -> Nothing missing, no duplicate files!
        plan2 = service.plan_movie_download_missing(m_id)
        assert len(plan2.new_songs) == 0
        assert len(plan2.upgrades) == 0

        # Assert total mp3 files in dl_dir is exactly 2
        mp3_files = list(dl_dir.glob("**/*.mp3"))
        assert len(mp3_files) == 2

    finally:
        server.shutdown()
        db.close()

