"""Unit tests for DownloadPlanner candidate selection and prioritization."""

from pathlib import Path
import pytest
from library.database import SQLiteDatabase
from library.planner import DownloadPlanner
from library.models import LibrarySong, SongSource, SongState
from models.song import Song


@pytest.mark.unit
def test_plan_prefers_higher_quality(tmp_path: Path):
    db = SQLiteDatabase(tmp_path / "plan_test.db")
    db.connect()
    planner = DownloadPlanner(db)

    song_128 = Song(
        name="Test Song",
        artist="Artist",
        quality="128kbps",
        url="http://example.com/128.mp3",
    )
    song_320 = Song(
        name="Test Song",
        artist="Artist",
        quality="320kbps",
        url="http://example.com/320.mp3",
    )

    plan = planner.plan_downloads([song_128, song_320], source_name="masstamilan")
    assert len(plan.new_songs) == 1
    # 320kbps is ranked higher than 128kbps
    assert "320" in plan.new_songs[0].quality_str or plan.new_songs[0].primary.quality_kbps == 320


@pytest.mark.unit
def test_plan_skips_owned_songs(tmp_path: Path):
    from library.discovery import song_to_canonical

    db = SQLiteDatabase(tmp_path / "plan_owned.db")
    db.connect()

    real_file = tmp_path / "arabic_kuthu.mp3"
    real_file.write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 400)

    discovered = Song(
        name="Arabic Kuthu",
        url="http://example.com/arabic.mp3",
        artist="Anirudh Ravichander",
        album_title="Beast",
    )
    identity = song_to_canonical(discovered)

    # Pre-add song as OWNED with physical file and matching quality
    song_id = db.add_song(
        LibrarySong(
            title="Arabic Kuthu",
            artist="Anirudh Ravichander",
            album="Beast",
            canonical_hash=identity.hash,
            state=SongState.OWNED,
            file_path=str(real_file),
            quality_kbps=320,
        )
    )

    planner = DownloadPlanner(db)
    plan = planner.plan_downloads([discovered], source_name="masstamilan")
    # Already owned -> no download planned
    assert len(plan.new_songs) == 0
    assert len(plan.owned) == 1

