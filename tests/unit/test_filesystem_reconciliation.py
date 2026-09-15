"""Unit tests for filesystem reconciliation logic and storage calculation."""

from pathlib import Path
import pytest
from library.database import SQLiteDatabase
from library.models import LibrarySong, SongState


@pytest.mark.unit
def test_reconciliation_resets_missing_owned_files_to_new(tmp_path: Path):
    """Verify that songs marked OWNED with non-existent files are reconciled to NEW."""
    db_path = tmp_path / "test_reconcile.db"
    db = SQLiteDatabase(db_path)
    db.connect()

    # Add song marked OWNED with fake path
    fake_path = str(tmp_path / "does_not_exist.mp3")
    song_id = db.add_song(
        LibrarySong(
            title="Ghost Track",
            artist="Ghost Artist",
            state=SongState.OWNED,
            file_path=fake_path,
        )
    )

    reconciled_cnt = db.reconcile_filesystem_integrity()
    assert reconciled_cnt == 1

    song = db.get_song(song_id)
    assert song is not None
    assert song.state == SongState.NEW
    assert song.file_path is None


@pytest.mark.unit
def test_reconciliation_preserves_valid_physical_files(tmp_path: Path):
    """Verify that songs marked OWNED with valid physical files remain OWNED."""
    db_path = tmp_path / "test_reconcile_valid.db"
    db = SQLiteDatabase(db_path)
    db.connect()

    real_file = tmp_path / "actual_song.mp3"
    real_file.write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 400)

    song_id = db.add_song(
        LibrarySong(
            title="Real Track",
            artist="Real Artist",
            state=SongState.OWNED,
            file_path=str(real_file),
        )
    )

    reconciled_cnt = db.reconcile_filesystem_integrity()
    assert reconciled_cnt == 0

    song = db.get_song(song_id)
    assert song is not None
    assert song.state == SongState.OWNED
    assert song.file_path == str(real_file)
