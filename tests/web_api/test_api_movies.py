"""
Tests for Movies API Endpoints.
"""

def test_list_movies(api_test_env):
    """Verify movie listing and pagination."""
    client = api_test_env["client"]
    res = client.get("/api/movies")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["total"] >= 1
    assert any(it.get("name") == "Leo" or it.get("title") == "Leo" for it in data["items"])


def test_get_movie_details(api_test_env):
    """Verify movie details endpoint returns cast and songs."""
    client = api_test_env["client"]
    m1_id = api_test_env["m1_id"]
    res = client.get(f"/api/movies/{m1_id}")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["movie"].get("name") == "Leo" or data["movie"].get("title") == "Leo"

    assert len(data["songs"]) >= 2


def test_movie_download_planning(api_test_env):
    """Verify movie download planning for all vs missing."""
    client = api_test_env["client"]
    m1_id = api_test_env["m1_id"]
    res = client.post(f"/api/movies/{m1_id}/plan?mode=missing")
    assert res.status_code == 200
    data = res.json()["data"]
    assert "to_download" in data
    assert "to_skip" in data


def test_movie_track_count_reconciliation(api_test_env):
    """Regression test for DEFECT-03: movie track_count accurately reflects linked song count."""
    service = api_test_env["service"]
    db = service.db
    m1_id = api_test_env["m1_id"]

    # Deliberately corrupt track_count to an arbitrary number
    with db._lock, db._conn:
        db._conn.execute("UPDATE movies SET track_count = 999 WHERE id = ?", (m1_id,))

    # Run canonical reconciliation
    reconciled = db.reconcile_movie_track_counts()
    assert reconciled >= 1

    # Verify track_count is restored to actual linked songs count
    movie = db.get_movie(m1_id)
    actual_count = db._conn.execute(
        "SELECT COUNT(*) FROM song_movies WHERE movie_id = ?", (m1_id,)
    ).fetchone()[0]
    assert movie.track_count == actual_count


def test_movie_year_reconciliation(api_test_env):
    """Regression test for DEFECT-04: recover movie release years from authoritative canonical data."""
    service = api_test_env["service"]
    db = service.db

    # Create a movie with NULL year but linked to a song with year 2024
    from library.models import Movie, LibrarySong, SongState
    m_id = db.add_movie(Movie(title="Devara Part 1", year=None))
    s_id = db.add_song(LibrarySong(
        title="Fear Song",
        artist="Anirudh Ravichander",
        year=2024,
        state=SongState.NEW,
    ))
    with db._lock, db._conn:
        db._conn.execute(
            "INSERT INTO song_movies (song_id, movie_id) VALUES (?, ?)", (s_id, m_id)
        )

    # Reconcile release years
    recovered = db.reconcile_movie_release_years()
    assert recovered >= 1

    # Verify year was recovered accurately without manual guesswork
    movie = db.get_movie(m_id)
    assert movie.year == 2024
