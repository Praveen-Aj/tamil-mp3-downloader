import pytest
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch
from library.providers.youtube_provider import YouTubeProvider


def test_temp_cleanup_on_failure(tmp_path):
    from library.providers.base import AudioCandidate

    output_dir = tmp_path / "downloads"
    output_dir.mkdir()

    prov = YouTubeProvider()
    cand = AudioCandidate(
        title="Test Song",
        source_url="https://www.youtube.com/watch?v=mock123",
        provider_name="youtube",
    )

    # Simulate yt_dlp failing during extract
    with patch("yt_dlp.YoutubeDL") as mock_ydl:
        mock_instance = MagicMock()
        mock_instance.download.side_effect = RuntimeError("Simulated network failure")
        mock_ydl.return_value.__enter__.return_value = mock_instance

        res = prov.download(
            candidate=cand,
            output_dir=output_dir,
            filename_stem="test_song",
        )

        assert res.success is False
        # Verify no .tmp directory remains
        tmp_folder = output_dir / ".tmp"
        if tmp_folder.exists():
            assert len(list(tmp_folder.iterdir())) == 0
        # Verify no partial or 0-byte file remains in output_dir
        assert not (output_dir / "test_song.mp3").exists()


def test_0_byte_and_part_cleanup(tmp_path):
    output_dir = tmp_path / "downloads"
    output_dir.mkdir()

    # Create dummy debris
    zero_byte_mp3 = output_dir / "corrupted.mp3"
    zero_byte_mp3.write_bytes(b"")

    part_file = output_dir / "incomplete.mp3.part"
    part_file.write_bytes(b"partial content")

    webm_debris = output_dir / "temp_video.webm"
    webm_debris.write_bytes(b"webm content")

    # Storage manager migration removes all 0-byte, .part, and debris
    import sqlite3
    from library.storage_manager import migrate_storage_to_canonical

    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE movies (id INTEGER PRIMARY KEY, title TEXT, year INTEGER)")
    conn.execute("CREATE TABLE songs (id INTEGER PRIMARY KEY, title TEXT, artist TEXT, album TEXT, year INTEGER, file_path TEXT, file_size_bytes INTEGER)")
    conn.execute("CREATE TABLE song_movies (id INTEGER PRIMARY KEY, song_id INTEGER, movie_id INTEGER, track_number INTEGER)")
    conn.commit()

    report = migrate_storage_to_canonical(conn, output_dir, dry_run=False)
    conn.close()

    assert not zero_byte_mp3.exists()
    assert not part_file.exists()
    assert len(report["temporary_artifacts_removed"]) >= 2
