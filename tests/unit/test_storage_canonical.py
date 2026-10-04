import pytest
import sqlite3
from pathlib import Path
from library.storage_manager import (
    get_canonical_download_path,
    get_primary_artist,
    resolve_canonical_path_for_song,
)


@pytest.fixture
def test_db():
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE movies (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            year INTEGER
        )
    """)
    cur.execute("""
        CREATE TABLE songs (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            title_normalized TEXT,
            artist TEXT,
            album TEXT,
            year INTEGER,
            file_path TEXT,
            file_size_bytes INTEGER,
            state TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE song_movies (
            id INTEGER PRIMARY KEY,
            song_id INTEGER,
            movie_id INTEGER,
            track_number INTEGER
        )
    """)

    # Seed test data: Movie "Master" (2021)
    cur.execute("INSERT INTO movies (id, title, year) VALUES (1, 'Master', 2021)")
    # Song "Vaathi Coming" linked to Movie "Master" with track_number 2
    cur.execute("""
        INSERT INTO songs (id, title, title_normalized, artist, album, year)
        VALUES (10, 'Vaathi Coming', 'vaathicoming', 'Anirudh Ravichander, Gana Balachandar', 'Master', 2021)
    """)
    cur.execute("INSERT INTO song_movies (song_id, movie_id, track_number) VALUES (10, 1, 2)")

    # Standalone single song "Enna Sona Independent"
    cur.execute("""
        INSERT INTO songs (id, title, title_normalized, artist, album, year)
        VALUES (20, 'Enna Sona', 'ennasona', 'Arijit Singh, AR Rahman', 'Single', 2017)
    """)

    conn.commit()
    yield conn
    conn.close()


def test_primary_artist_extraction():
    assert get_primary_artist("Anirudh Ravichander, Gana Balachandar") == "Anirudh Ravichander"
    assert get_primary_artist("A.R. Rahman feat. Sid Sriram") == "A.R. Rahman"
    assert get_primary_artist("Yuvan Shankar Raja and Dhibu") == "Yuvan Shankar Raja"
    assert get_primary_artist("Harris Jayaraj") == "Harris Jayaraj"
    assert get_primary_artist(None) == "Unknown Artist"


def test_movie_song_path_resolution(test_db, tmp_path):
    # Test 1: From Movies context
    path1, m1, _ = resolve_canonical_path_for_song(
        db=test_db,
        base_dir=tmp_path,
        song_id=10,
        song_title="Vaathi Coming",
    )
    expected_rel = Path("Movies") / "Master (2021)" / "02 - Vaathi Coming.mp3"
    assert path1 == tmp_path / expected_rel

    # Test 2: From Artist context (no movie_title explicitly passed, but resolved via DB)
    path2, m2, _ = resolve_canonical_path_for_song(
        db=test_db,
        base_dir=tmp_path,
        song_id=10,
        song_title="Vaathi Coming",
        artist="Anirudh Ravichander",
    )
    assert path2 == path1  # Resolves to the exact same canonical path!

    # Test 3: From Spotify context (only title known)
    path3, m3, _ = resolve_canonical_path_for_song(
        db=test_db,
        base_dir=tmp_path,
        song_title="Vaathi Coming (From Master)",
    )
    assert path3.parent == (tmp_path / "Movies" / "Master (2021)")


def test_standalone_song_resolves_to_singles(test_db, tmp_path):
    path, m_info, p_artist = resolve_canonical_path_for_song(
        db=test_db,
        base_dir=tmp_path,
        song_id=20,
        song_title="Enna Sona",
        artist="Arijit Singh, AR Rahman",
        album="Non Movie Album",
    )
    assert m_info is None
    expected_rel = Path("Singles") / "Arijit Singh - Enna Sona.mp3"
    assert path == tmp_path / expected_rel
