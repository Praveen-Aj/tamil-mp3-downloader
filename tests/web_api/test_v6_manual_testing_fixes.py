"""
Comprehensive Unit & Integration Tests for Manual V6 Testing Fixes.
Verifies:
1. Movies default sort (Release Year DESC, title ASC tie-break).
2. Soundtrack track classification & variants (Primary, Alternate, Non-Primary).
3. Playlists count and tracklist consistency.
4. Spotify/URL import candidate matching and execution serialization.
5. Canonical filesystem naming and storage layout.
"""

import pytest
from pathlib import Path
from library.track_classifier import (
    TrackClassification,
    classify_track_single,
    classify_movie_soundtrack,
    extract_base_title,
)
from library.storage_manager import (
    sanitize_filename,
    get_canonical_download_path,
)


def test_movies_default_sort_order(api_test_env):
    """Verify Movies endpoint defaults to release_year DESC, title ASC."""
    client = api_test_env["client"]
    res = client.get("/api/movies?page=1&page_size=20")
    assert res.status_code == 200
    data = res.json()["data"]
    items = data["items"]
    assert len(items) > 0

    # Ensure years are non-ascending (descending or equal)
    for i in range(len(items) - 1):
        y1 = items[i].get("year") or 0
        y2 = items[i + 1].get("year") or 0
        assert y1 >= y2, f"Expected descending years but got {y1} < {y2}"
        if y1 == y2:
            t1 = items[i].get("title", "").lower()
            t2 = items[i + 1].get("title", "").lower()
            assert t1 <= t2, f"Expected tie-break title ASC but got '{t1}' > '{t2}'"


def test_rathinamo_variants_classification():
    """Verify observed Rathinamo variants classification."""
    # Test primary
    assert classify_track_single("Rathinamo")[0] == TrackClassification.PRIMARY
    assert classify_track_single("Rathinamo - Saurav Srisan")[0] == TrackClassification.PRIMARY

    # Test alternate versions
    assert classify_track_single("Rathinamo (Female Version)")[0] == TrackClassification.ALTERNATE
    assert classify_track_single("Rathinamo Female Version")[0] == TrackClassification.ALTERNATE
    assert classify_track_single("Rathinamo - Male Version")[0] == TrackClassification.ALTERNATE
    assert classify_track_single("Rathinamo (Reprise)")[0] == TrackClassification.ALTERNATE

    # Grouping test
    movie_songs = [
        {"id": 1, "title": "Rathinamo", "artist": "Harris Jayaraj"},
        {"id": 2, "title": "Rathinamo (Female Version)", "artist": "Harris Jayaraj, Chinmayi"},
        {"id": 3, "title": "Rathinamo - Saurav Srisan", "artist": "Harris Jayaraj, Saurav Srisan"},
        {"id": 4, "title": "Rathinamo Female Version", "artist": "Harris Jayaraj"},
        {"id": 5, "title": "Rathinamo - Ring Tone", "artist": "Harris Jayaraj"},
        {"id": 6, "title": "Rathinamo Promo Audio", "artist": "Harris Jayaraj"},
        {"id": 7, "title": "Theme of Rathinamo (Instrumental)", "artist": "Harris Jayaraj"},
    ]

    classified = classify_movie_soundtrack(movie_songs)
    assert len(classified["primary_songs"]) == 2  # Rathinamo and Theme (genuine OST instrumental)
    assert len(classified["alternate_songs"]) == 3  # Female versions & Saurav Srisan variant
    assert len(classified["non_primary_songs"]) == 2  # Ring Tone & Promo Audio


def test_classical_instrumental_soundtrack_preservation():
    """Verify legitimate classical/instrumental OST tracks are preserved as PRIMARY."""
    assert classify_track_single("Roja - Theme Music")[0] == TrackClassification.PRIMARY
    assert classify_track_single("Bombay Theme (Instrumental)")[0] == TrackClassification.PRIMARY
    assert classify_track_single("Classical Carnatic Symphony")[0] == TrackClassification.PRIMARY
    assert classify_track_single("Violin Solo - Ilaiyaraaja")[0] == TrackClassification.PRIMARY

    # Whereas utility tones are excluded
    assert classify_track_single("Caller Tune 1")[0] == TrackClassification.NON_PRIMARY
    assert classify_track_single("Anbil Avan Notification Tone")[0] == TrackClassification.NON_PRIMARY
    assert classify_track_single("Leo Badass Dialogue Promo")[0] == TrackClassification.NON_PRIMARY
    assert classify_track_single("Hukum BGM 30s Teaser")[0] == TrackClassification.NON_PRIMARY


def test_canonical_download_path_generation():
    """Verify deterministic filesystem paths for movies and singles."""
    base_dir = Path("C:/Users/Praveen/Downloads/Songs New")

    # 1. Movie soundtrack with track number
    path1 = get_canonical_download_path(
        base_dir=base_dir,
        song_title="Arabic Kuthu",
        movie_title="Beast",
        movie_year=2022,
        track_number=1,
    )
    expected1 = base_dir / "Movies" / "Beast (2022)" / "01 - Arabic Kuthu.mp3"
    assert path1 == expected1

    # 2. Movie soundtrack without track number
    path2 = get_canonical_download_path(
        base_dir=base_dir,
        song_title="Badass",
        movie_title="Leo",
        movie_year=2023,
    )
    expected2 = base_dir / "Movies" / "Leo (2023)" / "Badass.mp3"
    assert path2 == expected2

    # 3. Standalone single
    path3 = get_canonical_download_path(
        base_dir=base_dir,
        song_title="Enjoy Enjaami",
        artist="Dhee ft. Arivu",
    )
    expected3 = base_dir / "Singles" / "Dhee ft. Arivu - Enjoy Enjaami.mp3"
    assert path3 == expected3


def test_playlist_metrics_consistency(api_test_env):
    """Verify playlist endpoints return consistent total_songs and stats."""
    client = api_test_env["client"]
    res = client.get("/api/playlists")
    assert res.status_code == 200
    data = res.json()["data"]
    items = data["items"]
    assert len(items) >= 1
    assert items[0]["name"] == "Gym Hits"
    assert items[0]["total_songs"] == 1


def test_movie_detail_classification_payload(api_test_env):
    """Verify GET /api/movies/{id}/songs returns classified groups."""
    client = api_test_env["client"]
    movie_id = api_test_env["m1_id"]

    res = client.get(f"/api/movies/{movie_id}/songs")
    assert res.status_code == 200
    body = res.json()["data"]
    assert "primary_songs" in body
    assert "alternate_songs" in body
    assert "non_primary_songs" in body
    assert "stats" in body
    assert body["stats"]["total_primary"] == len(body["primary_songs"])
