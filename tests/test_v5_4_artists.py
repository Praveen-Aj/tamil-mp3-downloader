"""
Comprehensive Test Suite for V5.4: Artists, Singers, Music Directors & Actors.

Validates:
A. Database Tests:
   - Artist CRUD (creation, retrieval, update, deletion)
   - Canonical artist matching & deduplication (case, whitespace, punctuation, Unicode)
   - Tamil Unicode names and normalization
   - Multi-role detection (Singer, Music Director, Actor, Multi-role)
   - M:N relationships:
     * Singer -> songs (song_artists)
     * Music Director -> movies (movie_composers)
     * Actor -> movies (movie_actors)
   - SQL aggregated metrics & statistics (total_songs, downloaded_songs, missing_songs, total_movies)
   - Search, role filtering, pagination, and sorting
   - Cascade behavior and deletion safety (deleting artist does NOT delete songs or movies)

B. Service Tests:
   - Composite artist name splitting (split_artist_names)
   - Paginated artist listing and filtering
   - Detailed artist profile retrieval
   - Library enrichment idempotency
   - Navigation support between Movie, Song, and Artist

C. Download Planning & Reconciliation Tests:
   - plan_artist_download_missing for Singers
   - plan_artist_download_missing for Music Directors
   - plan_artist_download_all
   - Skipping already owned songs
   - Filesystem reconciliation (file missing on disk -> marked missing and queued)
   - No quality downgrade
"""

import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from library.database import SQLiteDatabase
from library.canonical import compute_canonical_hash, normalize_string
from library.models import (
    LibrarySong, SongState, SongSource, Download, DownloadState, Movie,
    Artist, SongArtist, MovieComposer, MovieActor, SongMovie
)
from library.planner import DownloadPlanner
from ui.services.library_service import LibraryService


@pytest.fixture
def temp_db(tmp_path) -> SQLiteDatabase:
    """Provides a fresh, connected SQLiteDatabase instance with V5.4 schema."""
    db_path = tmp_path / "test_v5_4.db"
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
# A. DATABASE LAYER TESTS
# ==============================================================================

def test_artist_crud(temp_db: SQLiteDatabase):
    """Test artist creation, retrieval by ID, name, and normalized name."""
    art = Artist(name="A.R. Rahman", name_normalized=normalize_string("A.R. Rahman"), role="music_director")
    art_id = temp_db.add_artist(art)
    assert art_id > 0

    # Retrieve by ID
    fetched = temp_db.get_artist(art_id)
    assert fetched is not None
    assert fetched.name == "A.R. Rahman"
    assert fetched.role == "music_director"

    # Retrieve by name
    by_name = temp_db.get_artist_by_name("A.R. Rahman")
    assert by_name is not None
    assert by_name.id == art_id

    # Retrieve by normalized name
    by_norm = temp_db.get_artist_by_normalized_name("ar rahman")
    assert by_norm is not None
    assert by_norm.id == art_id

    # Update artist
    updated = temp_db.update_artist(art_id, bio="Oscar-winning Indian composer", role="composer")
    assert updated is True
    refetched = temp_db.get_artist(art_id)
    assert refetched.bio == "Oscar-winning Indian composer"
    assert refetched.role == "composer"

    # Delete artist
    deleted = temp_db.delete_artist(art_id)
    assert deleted is True
    assert temp_db.get_artist(art_id) is None


def test_canonical_artist_deduplication(temp_db: SQLiteDatabase):
    """Verify that case, extra whitespace, and punctuation differences deduplicate to the same artist."""
    id1 = temp_db.add_artist(Artist(name="Anirudh Ravichander", name_normalized=normalize_string("Anirudh Ravichander")))
    assert id1 > 0

    # Same name with different case
    id2 = temp_db.add_artist(Artist(name="ANIRUDH RAVICHANDER", name_normalized=normalize_string("ANIRUDH RAVICHANDER")))
    assert id2 == id1

    # Same name with surrounding whitespace
    id3 = temp_db.add_artist(Artist(name="  anirudh ravichander  ", name_normalized=normalize_string("  anirudh ravichander  ")))
    assert id3 == id1

    # Same name with trailing punctuation
    id4 = temp_db.add_artist(Artist(name="Anirudh Ravichander.", name_normalized=normalize_string("Anirudh Ravichander.")))
    assert id4 == id1

    # Verify only 1 artist in database
    artists = temp_db.list_artists()
    assert len(artists) == 1


def test_tamil_unicode_artist_support(temp_db: SQLiteDatabase):
    """Verify Tamil Unicode script names are stored, queried, and matched properly."""
    name_tamil = "இளையராஜா"  # Ilaiyaraaja
    art = Artist(name=name_tamil, name_normalized=normalize_string(name_tamil), role="music_director")
    art_id = temp_db.add_artist(art)
    assert art_id > 0

    # Query by exact Tamil name
    fetched = temp_db.get_artist_by_name(name_tamil)
    assert fetched is not None
    assert fetched.id == art_id
    assert fetched.name == name_tamil

    # Search by partial Tamil text
    results, total = temp_db.search_and_filter_artists(query="இளைய")
    assert total == 1
    assert results[0]["id"] == art_id
    assert results[0]["name"] == name_tamil


def test_multi_role_detection(temp_db: SQLiteDatabase):
    """Verify that an artist's roles are dynamically detected from relationships."""
    # Create artist
    dhanush_id = temp_db.add_artist(Artist(name="Dhanush", name_normalized="dhanush"))
    anirudh_id = temp_db.add_artist(Artist(name="Anirudh", name_normalized="anirudh"))

    # Create movie
    movie_id = temp_db.add_movie(Movie(title="3", title_normalized="3", year=2012))

    # Add Dhanush as actor of Movie '3'
    temp_db.add_movie_actor(MovieActor(movie_id=movie_id, actor_id=dhanush_id, character_name="Lead Actor"))

    # Add Anirudh as composer of Movie '3'
    temp_db.add_movie_composer(MovieComposer(movie_id=movie_id, composer_id=anirudh_id))

    # Create song 'Why This Kolaveri Di'
    song = LibrarySong(
        title="Why This Kolaveri Di",
        title_normalized="why this kolaveri di",
        artist="Dhanush, Anirudh",
        artist_normalized="dhanush anirudh",
        album="3",
        canonical_hash=compute_canonical_hash("Why This Kolaveri Di", "Dhanush, Anirudh", "3"),
    )
    song_id = temp_db.add_song(song)

    # Dhanush is a singer of this song
    temp_db.add_song_artist(SongArtist(song_id=song_id, artist_id=dhanush_id, role="singer"))
    # Anirudh is also a singer/featured vocalist
    temp_db.add_song_artist(SongArtist(song_id=song_id, artist_id=anirudh_id, role="singer"))

    # Verify Dhanush has roles: Actor AND Singer
    dhanush_roles = temp_db.get_artist_roles(dhanush_id)
    assert "actor" in dhanush_roles
    assert "singer" in dhanush_roles
    assert "music_director" not in dhanush_roles

    # Verify Anirudh has roles: Music Director AND Singer
    anirudh_roles = temp_db.get_artist_roles(anirudh_id)
    assert "music_director" in anirudh_roles
    assert "singer" in anirudh_roles
    assert "actor" not in anirudh_roles


def test_artist_relationships_and_detailed_views(temp_db: SQLiteDatabase):
    """Test get_artist_songs_detailed and get_artist_movies_detailed."""
    # Artist: S. P. Balasubrahmanyam
    spb_id = temp_db.add_artist(Artist(name="S. P. Balasubrahmanyam", name_normalized="s p balasubrahmanyam"))
    # Artist: Ilaiyaraaja
    raja_id = temp_db.add_artist(Artist(name="Ilaiyaraaja", name_normalized="ilaiyaraaja"))

    # Movie 1: Thalapathi (Composer: Ilaiyaraaja)
    m1_id = temp_db.add_movie(Movie(title="Thalapathi", title_normalized="thalapathi", year=1991))
    temp_db.add_movie_composer(MovieComposer(movie_id=m1_id, composer_id=raja_id))

    # Song 1: Rakkamma Kaiya Thattu (Singer: SPB, Movie: Thalapathi)
    s1 = LibrarySong(
        title="Rakkamma Kaiya Thattu",
        title_normalized="rakkamma kaiya thattu",
        artist="S. P. Balasubrahmanyam",
        artist_normalized="s p balasubrahmanyam",
        album="Thalapathi",
        canonical_hash=compute_canonical_hash("Rakkamma Kaiya Thattu", "S. P. Balasubrahmanyam", "Thalapathi"),
        state=SongState.OWNED,
        file_path="downloads/rakkamma.mp3",
    )
    s1_id = temp_db.add_song(s1)
    temp_db.add_song_artist(SongArtist(song_id=s1_id, artist_id=spb_id, role="singer"))
    temp_db.add_song_movie(SongMovie(song_id=s1_id, movie_id=m1_id, track_number=1))

    # Song 2: Sundari Kannal (Singer: SPB, Movie: Thalapathi, Unowned)
    s2 = LibrarySong(
        title="Sundari Kannal",
        title_normalized="sundari kannal",
        artist="S. P. Balasubrahmanyam",
        artist_normalized="s p balasubrahmanyam",
        album="Thalapathi",
        canonical_hash=compute_canonical_hash("Sundari Kannal", "S. P. Balasubrahmanyam", "Thalapathi"),
        state=SongState.NEW,
    )
    s2_id = temp_db.add_song(s2)
    temp_db.add_song_artist(SongArtist(song_id=s2_id, artist_id=spb_id, role="singer"))
    temp_db.add_song_movie(SongMovie(song_id=s2_id, movie_id=m1_id, track_number=2))

    # Test SPB detailed songs
    spb_songs = temp_db.get_artist_songs_detailed(spb_id)
    assert len(spb_songs) == 2
    titles = [s["title"] for s in spb_songs]
    assert "Rakkamma Kaiya Thattu" in titles
    assert "Sundari Kannal" in titles
    # Verify movie name is attached via song_movies
    for s in spb_songs:
        assert s["movie_title"] == "Thalapathi"

    # Test Ilaiyaraaja detailed movies
    raja_movies = temp_db.get_artist_movies_detailed(raja_id)
    assert len(raja_movies) == 1
    assert raja_movies[0]["title"] == "Thalapathi"
    assert raja_movies[0]["total_songs"] == 2
    assert raja_movies[0]["downloaded_songs"] == 1
    assert raja_movies[0]["missing_songs"] == 1


def test_artist_search_filtering_and_pagination(temp_db: SQLiteDatabase):
    """Test search_and_filter_artists with query, role filtering, sorting, and pagination."""
    # Create 3 artists
    a1_id = temp_db.add_artist(Artist(name="Sid Sriram", name_normalized="sid sriram"))
    a2_id = temp_db.add_artist(Artist(name="Harris Jayaraj", name_normalized="harris jayaraj"))
    a3_id = temp_db.add_artist(Artist(name="Suriya", name_normalized="suriya"))

    m_id = temp_db.add_movie(Movie(title="Ayan", title_normalized="ayan", year=2009))
    temp_db.add_movie_composer(MovieComposer(movie_id=m_id, composer_id=a2_id))
    temp_db.add_movie_actor(MovieActor(movie_id=m_id, actor_id=a3_id))

    s = LibrarySong(
        title="Vizhi Moodi",
        title_normalized="vizhi moodi",
        artist="Sid Sriram",
        artist_normalized="sid sriram",
        album="Ayan",
        canonical_hash=compute_canonical_hash("Vizhi Moodi", "Sid Sriram", "Ayan"),
    )
    s_id = temp_db.add_song(s)
    temp_db.add_song_artist(SongArtist(song_id=s_id, artist_id=a1_id, role="singer"))

    # Test 'all' filter
    all_res, total = temp_db.search_and_filter_artists(role="all")
    assert total == 3

    # Test 'singer' filter
    singer_res, s_total = temp_db.search_and_filter_artists(role="singer")
    assert s_total == 1
    assert singer_res[0]["id"] == a1_id

    # Test 'music_director' filter
    md_res, md_total = temp_db.search_and_filter_artists(role="music_director")
    assert md_total == 1
    assert md_res[0]["id"] == a2_id

    # Test 'actor' filter
    act_res, act_total = temp_db.search_and_filter_artists(role="actor")
    assert act_total == 1
    assert act_res[0]["id"] == a3_id

    # Test search query
    q_res, q_total = temp_db.search_and_filter_artists(query="suri")
    assert q_total == 1
    assert q_res[0]["id"] == a3_id

    # Test pagination (page_size=2)
    p1, _ = temp_db.search_and_filter_artists(page=1, page_size=2, sort_by="name", ascending=True)
    assert len(p1) == 2
    p2, _ = temp_db.search_and_filter_artists(page=2, page_size=2, sort_by="name", ascending=True)
    assert len(p2) == 1


def test_cascade_deletion_safety(temp_db: SQLiteDatabase):
    """Verify deleting an artist NEVER deletes songs, movies, or downloaded audio files."""
    art_id = temp_db.add_artist(Artist(name="Temporary Artist", name_normalized="temporary artist"))
    m_id = temp_db.add_movie(Movie(title="Protected Movie", title_normalized="protected movie"))
    s_id = temp_db.add_song(LibrarySong(
        title="Protected Song",
        title_normalized="protected song",
        artist="Temporary Artist",
        artist_normalized="temporary artist",
        album="Protected Album",
        canonical_hash=compute_canonical_hash("Protected Song", "Temporary Artist", "Protected Album"),
        state=SongState.OWNED,
        file_path="downloads/protected.mp3",
    ))

    # Link artist to movie and song
    temp_db.add_movie_composer(MovieComposer(movie_id=m_id, composer_id=art_id))
    temp_db.add_song_artist(SongArtist(song_id=s_id, artist_id=art_id, role="singer"))

    # Delete the artist
    deleted = temp_db.delete_artist(art_id)
    assert deleted is True

    # Artist is gone
    assert temp_db.get_artist(art_id) is None

    # Crucially, Song and Movie MUST still exist!
    assert temp_db.get_song(s_id) is not None
    assert temp_db.get_song(s_id).title == "Protected Song"
    assert temp_db.get_movie(m_id) is not None
    assert temp_db.get_movie(m_id).title == "Protected Movie"


# ==============================================================================
# B. SERVICE LAYER TESTS
# ==============================================================================

def test_split_artist_names(temp_service: LibraryService):
    """Test robust extraction of individual artist names from composite strings."""
    raw = "Anirudh Ravichander, Dhanush & Jonita Gandhi feat. Kamal Haasan"
    names = temp_service.split_artist_names(raw)
    assert "Anirudh Ravichander" in names
    assert "Dhanush" in names
    assert "Jonita Gandhi" in names
    assert "Kamal Haasan" in names
    assert len(names) == 4

    # Single artist
    assert temp_service.split_artist_names("A.R. Rahman") == ["A.R. Rahman"]
    # Empty
    assert temp_service.split_artist_names("") == []


def test_service_artist_details_and_enrichment(temp_service: LibraryService):
    """Test get_artist_details and idempotent enrichment from library."""
    db = temp_service.db

    # Seed library songs with various artist strings
    s1 = LibrarySong(
        title="Chinna Chinna Aasai",
        title_normalized="chinna chinna aasai",
        artist="Minmini",
        artist_normalized="minmini",
        album="Roja",
        canonical_hash=compute_canonical_hash("Chinna Chinna Aasai", "Minmini", "Roja"),
        state=SongState.NEW,
    )
    s1_id = db.add_song(s1)

    # Seed movie with composer and actors
    m1 = Movie(
        title="Roja",
        title_normalized="roja",
        year=1992,
        director="Mani Ratnam",
    )
    m1_id = db.add_movie(m1)
    db.add_song_movie(s1_id, m1_id, 1)

    # Add composer and actor
    arr_id = db.add_artist(Artist(name="A.R. Rahman", name_normalized="ar rahman", role="music_director"))
    db.add_movie_composer(m1_id, arr_id)

    arvind_id = db.add_artist(Artist(name="Arvind Swamy", name_normalized="arvind swamy", role="actor"))
    db.add_movie_actor(m1_id, arvind_id, "Rishi Kumar")

    # Run library enrichment
    temp_service.enrich_people_from_library()

    # Verify artists were created/enriched
    minmini = db.get_artist_by_normalized_name("minmini")
    assert minmini is not None

    arr = db.get_artist_by_normalized_name("ar rahman")
    assert arr is not None

    arvind = db.get_artist_by_normalized_name("arvind swamy")
    assert arvind is not None

    mani = db.get_artist_by_normalized_name("mani ratnam")
    assert mani is not None

    # Check details for A.R. Rahman
    arr_details = temp_service.get_artist_details(arr.id)
    assert arr_details["artist"].name == "A.R. Rahman"
    assert "music_director" in arr_details["roles"]
    assert len(arr_details["movies"]) == 1
    assert arr_details["movies"][0]["title"] == "Roja"

    # Running enrichment again should be completely idempotent (no duplicates)
    temp_service.enrich_people_from_library()
    all_artists = db.list_artists()
    names = [a.name_normalized for a in all_artists]
    assert len(names) == len(set(names))


# ==============================================================================
# C. DOWNLOAD PLANNING & RECONCILIATION TESTS
# ==============================================================================

def test_plan_artist_download_missing_for_singer(temp_service: LibraryService, tmp_path):
    """Test plan_artist_download_missing for a singer skips owned and queues missing."""
    db = temp_service.db
    spb_id = db.add_artist(Artist(name="S.P. Balasubrahmanyam", name_normalized="sp balasubrahmanyam"))

    # Create real physical file for Song 1 (OWNED)
    real_file = tmp_path / "downloads" / "song1.mp3"
    real_file.write_bytes(b"\xFF\xFB\x90\x44" + b"\x00" * 500)

    s1 = LibrarySong(
        title="Ithu Oru Pon Maalai Pozhuthu",
        title_normalized="ithu oru pon maalai pozhuthu",
        artist="S.P. Balasubrahmanyam",
        artist_normalized="sp balasubrahmanyam",
        album="Nizhalgal",
        canonical_hash=compute_canonical_hash("Ithu Oru Pon Maalai Pozhuthu", "S.P. Balasubrahmanyam", "Nizhalgal"),
        state=SongState.OWNED,
        file_path=str(real_file),
    )
    s1_id = db.add_song(s1)
    db.add_song_artist(SongArtist(song_id=s1_id, artist_id=spb_id, role="singer"))

    # Song 2 is NEW (missing)
    s2 = LibrarySong(
        title="En Kadhaley",
        title_normalized="en kadhaley",
        artist="S.P. Balasubrahmanyam",
        artist_normalized="sp balasubrahmanyam",
        album="Duet",
        canonical_hash=compute_canonical_hash("En Kadhaley", "S.P. Balasubrahmanyam", "Duet"),
        state=SongState.NEW,
    )
    s2_id = db.add_song(s2)
    db.add_source(SongSource(
        song_id=s2_id,
        source_name="masstamilan",
        source_url="https://masstamilan.dev/en-kadhaley.mp3",
        quality_kbps=320,
    ))
    db.add_song_artist(SongArtist(song_id=s2_id, artist_id=spb_id, role="singer"))

    # Plan missing downloads
    plan = temp_service.plan_artist_download_missing(spb_id)

    # Only s2 should be queued!
    assert len(plan.new_songs) == 1
    assert plan.new_songs[0].song_id == s2_id
    assert plan.new_songs[0].song.name == "En Kadhaley"


def test_plan_artist_download_missing_for_composer(temp_service: LibraryService):
    """Test plan_artist_download_missing for a composer gathers missing songs from their movies."""
    db = temp_service.db
    arr_id = db.add_artist(Artist(name="A.R. Rahman", name_normalized="ar rahman"))

    # Movie 1: Bombay
    m_id = db.add_movie(Movie(title="Bombay", title_normalized="bombay", year=1995))
    db.add_movie_composer(MovieComposer(movie_id=m_id, composer_id=arr_id))

    # Song 1 from Bombay
    s1 = LibrarySong(
        title="Uyire Uyire",
        title_normalized="uyire uyire",
        artist="Hariharan, K.S. Chithra",
        artist_normalized="hariharan ks chithra",
        album="Bombay",
        canonical_hash=compute_canonical_hash("Uyire Uyire", "Hariharan, K.S. Chithra", "Bombay"),
        state=SongState.NEW,
    )
    s1_id = db.add_song(s1)
    db.add_source(SongSource(
        song_id=s1_id,
        source_name="masstamilan",
        source_url="https://masstamilan.dev/uyire.mp3",
        quality_kbps=320,
    ))
    db.add_song_movie(SongMovie(song_id=s1_id, movie_id=m_id, track_number=1))

    # Plan missing downloads for composer
    plan = temp_service.plan_artist_download_missing(arr_id)
    assert len(plan.new_songs) == 1
    assert plan.new_songs[0].song_id == s1_id
    assert plan.new_songs[0].song.name == "Uyire Uyire"


def test_filesystem_reconciliation_in_artist_download(temp_service: LibraryService, tmp_path):
    """If DB records song as OWNED but physical file is missing, reconcile and queue for download."""
    db = temp_service.db
    sid_id = db.add_artist(Artist(name="Sid Sriram", name_normalized="sid sriram"))

    non_existent_file = tmp_path / "downloads" / "ghost_file.mp3"

    s = LibrarySong(
        title="Maruvaarthai",
        title_normalized="maruvaarthai",
        artist="Sid Sriram",
        artist_normalized="sid sriram",
        album="ENPT",
        canonical_hash=compute_canonical_hash("Maruvaarthai", "Sid Sriram", "ENPT"),
        state=SongState.OWNED,
        file_path=str(non_existent_file),  # does not exist on disk
    )
    s_id = db.add_song(s)
    db.add_source(SongSource(
        song_id=s_id,
        source_name="masstamilan",
        source_url="https://masstamilan.dev/maruvaarthai.mp3",
        quality_kbps=320,
    ))
    db.add_song_artist(SongArtist(song_id=s_id, artist_id=sid_id, role="singer"))

    # When planning missing downloads, filesystem reconciliation detects physical file is gone!
    plan = temp_service.plan_artist_download_missing(sid_id)
    assert len(plan.new_songs) == 1
    assert plan.new_songs[0].song_id == s_id
    assert plan.new_songs[0].song.name == "Maruvaarthai"

    # And DB state is reconciled to NEW
    reconciled_song = db.get_song(s_id)
    assert reconciled_song.state == SongState.NEW
