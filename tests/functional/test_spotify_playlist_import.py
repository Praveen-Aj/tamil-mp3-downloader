"""
Functional tests for Spotify playlist resolution and full multi-track import execution.
Tests complete lifecycle: URL -> analyze -> candidates -> execute_job -> physical files -> DB state.
"""

from pathlib import Path
import pytest
import json

from library.database import SQLiteDatabase
from library.jobs.job_manager import ImportJobManager
from ui.services.library_service import LibraryService
from library.models import ImportJob, ImportJobItem, ItemState, JobStatus, SongState
from library.url_resolver.spotify import SpotifyResolver
from library.url_resolver.base import PlatformType, ContentType
from tests.fixtures_helper import LocalTestServer


@pytest.fixture(scope="module")
def local_server():
    server = LocalTestServer()
    url = server.start()
    yield url
    server.shutdown()


@pytest.mark.functional
def test_spotify_resolver_parses_modern_embed_structure():
    """Verify that SpotifyResolver extracts track title and artist from subtitle in __NEXT_DATA__."""
    sample_embed_html = """
    <html>
    <head>
    <script id="__NEXT_DATA__" type="application/json">
    {
      "props": {
        "pageProps": {
          "state": {
            "data": {
              "entity": {
                "type": "playlist",
                "name": "Top Tamil Hits",
                "trackList": [
                  {
                    "title": "Arabic Kuthu",
                    "subtitle": "Anirudh Ravichander, Jonita Gandhi",
                    "duration": 280000,
                    "uri": "spotify:track:12345"
                  },
                  {
                    "title": "Naan Pizhai",
                    "subtitle": "Anirudh Ravichander",
                    "duration": 240000,
                    "uri": "spotify:track:67890"
                  }
                ]
              }
            }
          }
        }
      }
    }
    </script>
    </head>
    <body></body>
    </html>
    """
    resolver = SpotifyResolver()
    # Mock requests.get to return sample_embed_html
    class MockResponse:
        status_code = 200
        text = sample_embed_html

    import unittest.mock as mock
    with mock.patch("requests.get", return_value=MockResponse()):
        resolved = resolver.resolve("https://open.spotify.com/playlist/37i9dQZF1DX4sWSpwq3LiO")

    assert resolved.platform == PlatformType.SPOTIFY
    assert resolved.content_type == ContentType.PLAYLIST
    assert resolved.title == "Top Tamil Hits"
    assert len(resolved.tracks) == 2
    
    t1 = resolved.tracks[0]
    assert t1.title == "Arabic Kuthu"
    assert t1.artist == "Anirudh Ravichander, Jonita Gandhi"
    assert t1.duration_seconds == 280

    t2 = resolved.tracks[1]
    assert t2.title == "Naan Pizhai"
    assert t2.artist == "Anirudh Ravichander"
    assert t2.duration_seconds == 240


@pytest.mark.functional
def test_unextractable_playlist_does_not_create_fake_song_item(tmp_path: Path):
    """
    Verify that when a playlist contains 0 extractable tracks or fails resolution,
    analyze_url does NOT create a fake single-track song item with 'Unknown Artist',
    but marks the job as FAILED and items as empty.
    """
    from library.url_resolver.base import ResolvedContent, ContentType, PlatformType
    db_path = tmp_path / "empty_pl.db"
    db = SQLiteDatabase(db_path)
    db.connect()
    job_mgr = ImportJobManager(db)

    # Simulate resolved content with 0 tracks and error
    mock_resolved = ResolvedContent(
        platform=PlatformType.SPOTIFY,
        content_type=ContentType.PLAYLIST,
        title="Empty or Private Playlist",
        tracks=[],
        raw_url="https://open.spotify.com/playlist/empty",
        error_message="Could not enumerate tracks from Spotify collection page.",
    )

    import unittest.mock as mock
    with mock.patch("library.jobs.job_manager.UniversalUrlDetector.resolve", return_value=mock_resolved):
        job, items = job_mgr.analyze_url("https://open.spotify.com/playlist/empty")

    assert job.status == JobStatus.FAILED
    assert job.total_tracks == 0
    # Items should be empty - not 1 fake song
    assert len(items) == 0


@pytest.mark.functional
def test_playlist_full_execute_job_produces_physical_files(tmp_path: Path, local_server: str):
    """
    Verify that ImportJobManager.execute_job() downloads actual files,
    writes them to disk, updates item states to COMPLETED, and registers songs in DB.
    """
    db_path = tmp_path / "import_exec.db"
    dl_dir = tmp_path / "downloads"
    dl_dir.mkdir(parents=True, exist_ok=True)

    db = SQLiteDatabase(db_path)
    db.connect()
    job_mgr = ImportJobManager(db)

    job_id = "job-exec-test-1"
    job = ImportJob(
        id=job_id,
        url="https://open.spotify.com/playlist/test1",
        title="Test Batch",
        platform="Spotify",
        content_type="Playlist",
        total_tracks=2,
        status=JobStatus.READY,
    )
    db.create_import_job(job)

    # 2 items pointing to valid local server audio streams
    item1 = ImportJobItem(
        job_id=job_id,
        track_index=1,
        title="Song Alpha",
        artist="Artist A",
        album="Album A",
        state=ItemState.READY,
        selected_provider="direct_http",
        selected_source_url=f"{local_server}/track1.mp3",
    )
    item2 = ImportJobItem(
        job_id=job_id,
        track_index=2,
        title="Song Beta",
        artist="Artist B",
        album="Album B",
        state=ItemState.READY,
        selected_provider="direct_http",
        selected_source_url=f"{local_server}/track2.mp3",
    )
    db.add_import_job_items([item1, item2])

    items_before = db.get_import_job_items(job_id)
    assert len(items_before) == 2
    item_ids = [items_before[0].id, items_before[1].id]

    # Execute job through manager
    res = job_mgr.execute_job(
        job_id=job_id,
        item_ids=item_ids,
        output_dir=dl_dir,
    )

    assert res["completed"] == 2
    assert res["failed"] == 0

    # Verify physical files
    files = list(dl_dir.glob("*.mp3"))
    assert len(files) == 2
    for f in files:
        assert f.exists()
        assert f.stat().st_size > 0

    # Verify DB records
    items_after = db.get_import_job_items(job_id)
    assert all(it.state == ItemState.COMPLETED for it in items_after)
    
    # Verify registered songs in songs table
    owned_songs = db.get_songs_by_state(SongState.OWNED)
    assert len(owned_songs) == 2
    for s in owned_songs:
        assert s.file_path is not None
        assert Path(s.file_path).exists()


@pytest.mark.functional
def test_playlist_partial_failure_handling(tmp_path: Path, local_server: str):
    """
    Verify that if 1 of 2 tracks fails (404) and has no viable fallbacks,
    the successful track writes to disk, the failed track is marked FAILED,
    and NO fake OWNED record is created.
    """
    db_path = tmp_path / "import_partial.db"
    dl_dir = tmp_path / "downloads"
    dl_dir.mkdir(parents=True, exist_ok=True)

    db = SQLiteDatabase(db_path)
    db.connect()
    job_mgr = ImportJobManager(db)

    job_id = "job-partial-test"
    job = ImportJob(
        id=job_id,
        url="https://open.spotify.com/playlist/partial",
        title="Partial Playlist",
        platform="Spotify",
        content_type="Playlist",
        total_tracks=2,
        status=JobStatus.READY,
    )
    db.create_import_job(job)

    item_good = ImportJobItem(
        job_id=job_id,
        track_index=1,
        title="Good Song",
        artist="Good Artist",
        state=ItemState.READY,
        selected_provider="direct_http",
        selected_source_url=f"{local_server}/track1.mp3",
    )
    item_bad = ImportJobItem(
        job_id=job_id,
        track_index=2,
        title="Broken Song",
        artist="Bad Artist",
        state=ItemState.READY,
        selected_provider="direct_http",
        selected_source_url=f"{local_server}/not-found.mp3",
    )
    db.add_import_job_items([item_good, item_bad])

    items = db.get_import_job_items(job_id)
    item_ids = [items[0].id, items[1].id]

    import unittest.mock as mock
    # Prevent live YouTube fallback for the broken item so it deterministically fails
    with mock.patch.object(job_mgr.provider_registry, "search_and_rank_candidates", return_value=[]):
        res = job_mgr.execute_job(
            job_id=job_id,
            item_ids=item_ids,
            output_dir=dl_dir,
        )

    assert res["completed"] == 1
    assert res["failed"] == 1

    # Exactly 1 physical file on disk
    files = list(dl_dir.glob("*.mp3"))
    assert len(files) == 1

    # Items state check
    items_after = db.get_import_job_items(job_id)
    assert items_after[0].state == ItemState.COMPLETED
    assert items_after[1].state == ItemState.FAILED

    # Only 1 owned song in DB
    owned_songs = db.get_songs_by_state(SongState.OWNED)
    assert len(owned_songs) == 1
    assert owned_songs[0].title == "Good Song"
