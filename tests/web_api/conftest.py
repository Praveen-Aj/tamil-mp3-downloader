"""
Pytest Fixtures for FastAPI V6 API Testing.
"""

import sys
from pathlib import Path
from typing import Dict, Generator, Any

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pytest
from fastapi.testclient import TestClient

from api.app import app
from api.deps import get_service, set_service
from library.database import SQLiteDatabase
from library.models import (
    LibrarySong, SongSource, SongState, Movie, Artist,
    MovieActor, MovieComposer, SongArtist, SongMovie,
    Chart, ChartEntry, Playlist
)
from library.service import LibraryService


@pytest.fixture
def api_test_env(tmp_path: Path) -> Generator[Dict, None, None]:
    """Sets up an isolated database, download directory, and configured service."""
    db_path = tmp_path / "test_api_library.db"
    dl_dir = tmp_path / "downloads"
    dl_dir.mkdir(parents=True, exist_ok=True)

    db = SQLiteDatabase(db_path)
    db.connect()

    service = LibraryService(db=db, download_dir=str(dl_dir))

    # Seed Sample Data
    # 1. Movie
    m1_id = db.add_movie(Movie(title="Leo", year=2023))
    # 2. Artist
    a1_id = db.add_artist(Artist(name="Anirudh Ravichander"))
    # 3. Songs
    # Create a real dummy audio file for streaming test
    audio_file = dl_dir / "Badass - Anirudh.mp3"
    audio_file.write_bytes(b"\xFF\xFB\x90\x64\x00" + b"AUDIO_DATA_PAYLOAD" * 200)

    s1_id = db.add_song(LibrarySong(
        title="Badass",
        artist="Anirudh Ravichander",
        album="Leo",
        year=2023,
        state=SongState.OWNED,
        file_path=str(audio_file),
    ))
    db.add_source(SongSource(
        song_id=s1_id,
        source_name="masstamilan",
        source_url="https://masstamilan.dev/badass.mp3",
        quality_kbps=320,
    ))
    db.add_song_movie(song_id=s1_id, movie_id=m1_id, track_number=1)
    db.add_song_artist(song_id=s1_id, artist_id=a1_id, role="composer")

    s2_id = db.add_song(LibrarySong(
        title="Naa Ready",
        artist="Vijay, Anirudh",
        album="Leo",
        year=2023,
        state=SongState.NEW,
    ))
    db.add_source(SongSource(
        song_id=s2_id,
        source_name="masstamilan",
        source_url="https://masstamilan.dev/naa-ready.mp3",
        quality_kbps=320,
    ))
    db.add_song_movie(song_id=s2_id, movie_id=m1_id, track_number=2)


    # 4. Chart
    chart_id = db.create_chart(Chart(
        id="tamil_top_20",
        title="Tamil Top 20",
        chart_type="top_songs",
        provider_name="regional",
    ))
    db.add_chart_entry(ChartEntry(chart_id=chart_id, song_id=s1_id, rank=1, raw_title="Badass"))
    db.add_chart_entry(ChartEntry(chart_id=chart_id, song_id=s2_id, rank=2, raw_title="Naa Ready"))


    # 5. Playlist
    playlist_id = db.create_playlist(Playlist(
        name="Gym Hits",
        description="High energy tracks",
    ))
    db.add_playlist_item(playlist_id, s1_id)

    # Override service dependency
    app.dependency_overrides[get_service] = lambda: service
    set_service(service)

    client = TestClient(app)

    yield {
        "client": client,
        "service": service,
        "db": db,
        "dl_dir": dl_dir,
        "s1_id": s1_id,
        "s2_id": s2_id,
        "m1_id": m1_id,
        "a1_id": a1_id,
        "chart_id": chart_id,
        "playlist_id": playlist_id,
        "audio_file": audio_file,
    }

    app.dependency_overrides.clear()
