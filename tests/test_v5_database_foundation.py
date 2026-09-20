"""
Comprehensive test suite for V5.1 Database Foundation.
Validates:
1. Migration 4 from v3 -> v4 schema.
2. Fresh database initialization.
3. Preservation of existing songs, sources, and downloads.
4. CRUD and relationship operations for Movies, Artists, MovieActor, MovieComposer.
5. Song-Artist and Song-Movie M:N relationships.
6. UserSongMetadata rating constraints, favorite toggles, and notes.
7. Playlists and PlaylistItems uniqueness, ordering, and cascade deletes.
8. Charts and ChartEntries uniqueness, rank ordering, and cascade deletes.
9. Foreign key cascade integrity.
10. Migration idempotency and connection reopening.
"""

import pytest
import sqlite3
from datetime import datetime
from pathlib import Path

from library.database import SQLiteDatabase
from library.migrator import DatabaseMigrator
from library.models import (
    LibrarySong, SongState, SongSource, Download, DownloadState,
    Movie, Artist, MovieActor, MovieComposer, SongArtist, SongMovie,
    UserSongMetadata, Playlist, PlaylistItem, Chart, ChartEntry
)


@pytest.fixture
def temp_db(tmp_path) -> SQLiteDatabase:
    """Provides a fresh, connected SQLiteDatabase instance."""
    db_path = tmp_path / "test_library_v5.db"
    db = SQLiteDatabase(db_path)
    db.connect()
    yield db
    db.close()


def test_migration_v3_to_v4_preserves_data(tmp_path):
    """
    Simulate an existing v3 database with populated songs, sources, and downloads,
    then execute Migration 4 and verify all existing data is 100% intact.
    """
    db_path = tmp_path / "migration_v3_to_v4.db"
    
    # 1. Manually initialize up to Migration 3
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    migrator = DatabaseMigrator(None)
    for v in (1, 2, 3):
        statements = [s.strip() for s in migrator.MIGRATIONS[v].split(';') if s.strip()]
        for stmt in statements:
            conn.execute(stmt)
        conn.execute("INSERT INTO schema_version (version) VALUES (?)", (v,))
    conn.commit()

    # Insert pre-existing v3 records
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO songs (
            canonical_hash, title_normalized, artist_normalized, album_normalized,
            year, duration_seconds, title, artist, album, state, quality_kbps, file_path
        ) VALUES ('hash_v3_1', 'arabic kuthu', 'anirudh', 'beast', 2022, 278, 'Arabic Kuthu', 'Anirudh', 'Beast', 'OWNED', 160, 'C:/downloads/arabic.webm')
    """)
    song_id = cur.lastrowid

    cur.execute("""
        INSERT INTO song_sources (song_id, source_name, source_url, quality_kbps, is_available)
        VALUES (?, 'youtube', 'https://youtube.com/watch?v=123', 160, 1)
    """, (song_id,))
    source_id = cur.lastrowid

    cur.execute("""
        INSERT INTO downloads (song_id, song_source_id, state, output_path)
        VALUES (?, ?, 'COMPLETED', 'C:/downloads/arabic.webm')
    """, (song_id, source_id))
    dl_id = cur.lastrowid
    conn.commit()
    conn.close()

    # 2. Connect using SQLiteDatabase (which triggers Migration 4)
    db = SQLiteDatabase(db_path)
    db.connect()

    # Verify schema version is now 5
    cursor = db._conn.cursor()
    cursor.execute("SELECT MAX(version) FROM schema_version")
    assert cursor.fetchone()[0] == 5

    # Verify existing records are intact
    song = db.get_song(song_id)
    assert song is not None
    assert song.title == "Arabic Kuthu"
    assert song.state == SongState.OWNED
    assert song.file_path == "C:/downloads/arabic.webm"

    sources = db.get_sources_for_song(song_id)
    assert len(sources) == 1
    assert sources[0].source_name == "youtube"

    dl = db.get_download(dl_id)
    assert dl is not None
    assert dl.state == DownloadState.COMPLETED
    assert dl.output_path == "C:/downloads/arabic.webm"

    db.close()


def test_fresh_database_has_version_4_and_all_tables(temp_db):
    """Verify fresh database connection initializes all V5 tables, FTS5 index, and version 5."""
    cursor = temp_db._conn.cursor()
    cursor.execute("SELECT MAX(version) FROM schema_version")
    assert cursor.fetchone()[0] == 5

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    
    expected_tables = {
        "library_locations", "songs", "song_sources", "downloads",
        "discovery_context", "schema_version", "import_jobs", "import_job_items",
        "movies", "artists", "movie_actors", "movie_composers",
        "song_artists", "song_movies", "user_song_metadata",
        "playlists", "playlist_items", "charts", "chart_entries", "songs_fts"
    }
    assert expected_tables.issubset(tables)


def test_movie_crud(temp_db):
    """Verify Movie entity creation, retrieval, listing, and deletion."""
    movie = Movie(
        title="Leo",
        title_normalized="leo",
        year=2023,
        director="Lokesh Kanagaraj",
        poster_url="https://images.com/leo.jpg",
        track_count=7,
    )
    movie_id = temp_db.add_movie(movie)
    assert movie_id > 0

    # Idempotent insert returns existing ID
    assert temp_db.add_movie(movie) == movie_id

    fetched = temp_db.get_movie(movie_id)
    assert fetched is not None
    assert fetched.title == "Leo"
    assert fetched.director == "Lokesh Kanagaraj"
    assert fetched.year == 2023

    by_title = temp_db.get_movie_by_title("Leo")
    assert by_title is not None
    assert by_title.id == movie_id

    movies_list = temp_db.list_movies()
    assert len(movies_list) >= 1
    assert any(m.title == "Leo" for m in movies_list)

    # Delete movie
    assert temp_db.delete_movie(movie_id) is True
    assert temp_db.get_movie(movie_id) is None


def test_artist_crud(temp_db):
    """Verify Artist entity creation, retrieval, listing, and deletion."""
    artist = Artist(
        name="Anirudh Ravichander",
        name_normalized="anirudh ravichander",
        role="music_director",
        bio="Prolific Indian music composer and singer.",
    )
    artist_id = temp_db.add_artist(artist)
    assert artist_id > 0

    # Idempotent insert
    assert temp_db.add_artist(artist) == artist_id

    fetched = temp_db.get_artist(artist_id)
    assert fetched is not None
    assert fetched.name == "Anirudh Ravichander"
    assert fetched.role == "music_director"

    by_name = temp_db.get_artist_by_name("Anirudh Ravichander")
    assert by_name is not None
    assert by_name.id == artist_id

    # Filtered listing
    composers = temp_db.list_artists(role="music_director")
    assert any(a.name == "Anirudh Ravichander" for a in composers)

    singers = temp_db.list_artists(role="singer")
    assert not any(a.name == "Anirudh Ravichander" for a in singers)

    assert temp_db.delete_artist(artist_id) is True
    assert temp_db.get_artist(artist_id) is None


def test_movie_actors_and_composers_relationships(temp_db):
    """Verify linking movies to actors and composers with cascade delete behavior."""
    m_id = temp_db.add_movie(Movie(title="Jailer", title_normalized="jailer", year=2023))
    rajini_id = temp_db.add_artist(Artist(name="Rajinikanth", name_normalized="rajinikanth", role="actor"))
    anirudh_id = temp_db.add_artist(Artist(name="Anirudh Ravichander", name_normalized="anirudh ravichander", role="music_director"))

    # Add actor and composer
    assert temp_db.add_movie_actor(m_id, rajini_id, character_name="Tiger Muthuvel Pandian") is True
    assert temp_db.add_movie_composer(m_id, anirudh_id) is True

    # Retrieve actors
    actors = temp_db.get_movie_actors(m_id)
    assert len(actors) == 1
    actor, character = actors[0]
    assert actor.name == "Rajinikanth"
    assert character == "Tiger Muthuvel Pandian"

    # Retrieve composers
    composers = temp_db.get_movie_composers(m_id)
    assert len(composers) == 1
    assert composers[0].name == "Anirudh Ravichander"

    # Verify deleting movie cascades to movie_actors and movie_composers but preserves artists
    temp_db.delete_movie(m_id)
    assert len(temp_db.get_movie_actors(m_id)) == 0
    assert len(temp_db.get_movie_composers(m_id)) == 0
    assert temp_db.get_artist(rajini_id) is not None
    assert temp_db.get_artist(anirudh_id) is not None


def test_song_artists_and_song_movies_relationships(temp_db):
    """Verify normalized M:N relationships between canonical songs, artists, and movies."""
    # 1. Create canonical song
    s_id = temp_db.add_song(LibrarySong(
        canonical_hash="naa_ready_hash",
        title="Naa Ready",
        title_normalized="naa ready",
        artist="Anirudh Ravichander, Thalapathy Vijay",
        album="Leo",
        year=2023,
        duration_seconds=248,
    ))

    # 2. Create artists
    anirudh_id = temp_db.add_artist(Artist(name="Anirudh Ravichander", name_normalized="anirudh ravichander", role="music_director"))
    vijay_id = temp_db.add_artist(Artist(name="Thalapathy Vijay", name_normalized="thalapathy vijay", role="singer"))

    # 3. Create movie
    leo_id = temp_db.add_movie(Movie(title="Leo", title_normalized="leo", year=2023))

    # 4. Link song to artists (multi-artist credits)
    assert temp_db.add_song_artist(s_id, anirudh_id, role="composer") is True
    assert temp_db.add_song_artist(s_id, anirudh_id, role="singer") is True
    assert temp_db.add_song_artist(s_id, vijay_id, role="singer") is True

    credits = temp_db.get_song_artists(s_id)
    assert len(credits) == 3

    anirudh_songs = temp_db.get_artist_songs(anirudh_id)
    assert len(anirudh_songs) == 1
    assert anirudh_songs[0].title == "Naa Ready"

    # 5. Link song to movie
    assert temp_db.add_song_movie(s_id, leo_id, track_number=1) is True

    song_movies = temp_db.get_song_movies(s_id)
    assert len(song_movies) == 1
    assert song_movies[0].title == "Leo"

    movie_songs = temp_db.get_movie_songs(leo_id)
    assert len(movie_songs) == 1
    assert movie_songs[0].title == "Naa Ready"

    # 6. Deleting the movie does NOT delete the canonical song
    temp_db.delete_movie(leo_id)
    assert temp_db.get_song(s_id) is not None
    assert len(temp_db.get_song_movies(s_id)) == 0


def test_user_song_metadata_ratings_and_favorites(temp_db):
    """Verify 1-5 rating constraints, favorite toggles, and user notes."""
    s_id = temp_db.add_song(LibrarySong(
        canonical_hash="hukum_hash",
        title="Hukum",
        title_normalized="hukum",
        artist="Anirudh",
        album="Jailer",
    ))

    # Initially no metadata
    assert temp_db.get_user_metadata(s_id) is None

    # Set valid rating (1-5)
    assert temp_db.set_song_rating(s_id, 5) is True
    meta = temp_db.get_user_metadata(s_id)
    assert meta is not None
    assert meta.rating == 5
    assert meta.is_favorite is False

    # Invalid rating (> 5 or < 1) rejected with ValueError
    with pytest.raises(ValueError):
        temp_db.set_song_rating(s_id, 6)
    with pytest.raises(ValueError):
        temp_db.set_song_rating(s_id, 0)

    # Clear rating (rating=None)
    assert temp_db.set_song_rating(s_id, None) is True
    meta = temp_db.get_user_metadata(s_id)
    assert meta.rating is None

    # Toggle favorite
    new_fav = temp_db.toggle_song_favorite(s_id)
    assert new_fav is True
    fav_songs = temp_db.list_favorite_songs()
    assert len(fav_songs) == 1
    assert fav_songs[0].id == s_id

    # Toggle favorite off
    new_fav = temp_db.toggle_song_favorite(s_id)
    assert new_fav is False
    assert len(temp_db.list_favorite_songs()) == 0

    # Set full user metadata (notes & tags)
    full_meta = UserSongMetadata(
        song_id=s_id,
        rating=4,
        is_favorite=True,
        notes="Best Rajinikanth intro track",
        tags="mass,hype,workout",
    )
    assert temp_db.set_user_metadata(full_meta) is True
    updated = temp_db.get_user_metadata(s_id)
    assert updated.rating == 4
    assert updated.is_favorite is True
    assert updated.notes == "Best Rajinikanth intro track"
    assert updated.tags == "mass,hype,workout"


def test_playlists_and_playlist_items(temp_db):
    """Verify Playlist creation, item positioning, uniqueness, and cascade deletes."""
    p_id = temp_db.create_playlist(Playlist(
        name="Gym Tamil B変",
        description="High-energy Tamil gym workout tracks",
    ))
    assert p_id > 0

    s1_id = temp_db.add_song(LibrarySong(canonical_hash="song_1_hash", title="Vathi Coming", artist="Anirudh"))
    s2_id = temp_db.add_song(LibrarySong(canonical_hash="song_2_hash", title="Badass", artist="Anirudh"))

    # Add items to playlist
    item1_id = temp_db.add_playlist_item(p_id, s1_id, position=1)
    item2_id = temp_db.add_playlist_item(p_id, s2_id, position=2)
    assert item1_id > 0
    assert item2_id > 0

    # Duplicate insertion of same song in same playlist is ignored (unique constraint)
    dup_item_id = temp_db.add_playlist_item(p_id, s1_id)
    assert dup_item_id == 0

    # Fetch ordered songs
    songs = temp_db.get_playlist_songs(p_id)
    assert len(songs) == 2
    assert songs[0].id == s1_id
    assert songs[1].id == s2_id

    # Remove single item
    assert temp_db.remove_playlist_item(p_id, s1_id) is True
    assert len(temp_db.get_playlist_songs(p_id)) == 1

    # Delete playlist cascades to items but preserves canonical songs
    assert temp_db.delete_playlist(p_id) is True
    assert temp_db.get_playlist(p_id) is None
    assert temp_db.get_song(s1_id) is not None
    assert temp_db.get_song(s2_id) is not None


def test_charts_and_chart_entries(temp_db):
    """Verify Charts creation, ranked entries uniqueness, and cascade deletes."""
    chart_id = "chart-spotify-weekly-2026-w38"
    chart = Chart(
        id=chart_id,
        title="Spotify Tamil Top 50 - Week 38 2026",
        chart_type="weekly_top_50",
        provider_name="spotify",
        snapshot_date=datetime(2026, 9, 19, 12, 0, 0),
    )
    assert temp_db.create_chart(chart) == chart_id

    s_id = temp_db.add_song(LibrarySong(canonical_hash="chart_song_hash", title="Arabic Kuthu", artist="Anirudh"))

    # Add ranked entries
    temp_db.add_chart_entry(ChartEntry(
        chart_id=chart_id,
        rank=1,
        previous_rank=2,
        song_id=s_id,
        raw_title="Arabic Kuthu - Halamithi Habibo",
        raw_artist="Anirudh Ravichander, Jonita Gandhi",
        raw_movie="Beast",
    ))
    temp_db.add_chart_entry(ChartEntry(
        chart_id=chart_id,
        rank=2,
        previous_rank=1,
        song_id=None,
        raw_title="Naa Ready",
        raw_artist="Thalapathy Vijay",
        raw_movie="Leo",
    ))

    entries = temp_db.get_chart_entries(chart_id)
    assert len(entries) == 2
    assert entries[0].rank == 1
    assert entries[0].raw_title == "Arabic Kuthu - Halamithi Habibo"
    assert entries[0].song_id == s_id
    assert entries[1].rank == 2

    # Delete chart cascades to entries
    assert temp_db.delete_chart(chart_id) is True
    assert temp_db.get_chart(chart_id) is None
    assert len(temp_db.get_chart_entries(chart_id)) == 0
    # Canonical song is preserved
    assert temp_db.get_song(s_id) is not None


def test_migration_idempotency(temp_db):
    """Verify that calling migrator.migrate() repeatedly on an up-to-date DB is a safe no-op."""
    migrator = temp_db._migrator
    assert migrator._get_current_version() == 5
    # Run again: should log up to date and return safely
    migrator.migrate()
    assert migrator._get_current_version() == 5
