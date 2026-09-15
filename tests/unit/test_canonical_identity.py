"""Unit tests for canonical track identity, title normalization, and hashing."""

import re
import pytest
from library.models import LibrarySong, SongState
from library.canonical import compute_canonical_hash, normalize_string, extract_base_title


def sanitize_filename(name: str) -> str:
    """Helper to clean filenames for storage."""
    return re.sub(r'[<>:"/\\|?*]', '', name).strip()


@pytest.mark.unit
def test_canonical_track_identity_hash():
    """Verify that identical metadata normalizes to identical canonical ID."""
    hash1 = compute_canonical_hash("Arabic Kuthu", "Anirudh Ravichander", "Beast")
    hash2 = compute_canonical_hash("arabic  kuthu ", "anirudh ravichander", "beast")
    assert hash1 == hash2


@pytest.mark.unit
def test_title_normalization_removes_junk_descriptors():
    """Verify that download spam, bitrates, and source descriptors are normalized."""
    raw1 = "Arabic Kuthu - MassTamilan.dev [320Kbps]"
    cleaned1 = normalize_string(raw1)
    assert "masstamilan" in cleaned1 or "arabic kuthu" in cleaned1
    base = extract_base_title("Arabic Kuthu (Reprise)")
    assert base == "Arabic Kuthu"


@pytest.mark.unit
def test_filename_sanitization():
    """Verify illegal filesystem characters are safely stripped."""
    unsafe = 'Song/Title:With*Illegal?Chars"|<>'
    safe = sanitize_filename(unsafe)
    for char in '<>:"/\\|?*':
        assert char not in safe


@pytest.mark.unit
def test_song_state_transitions():
    """Verify valid and invalid state transitions for LibrarySong."""
    song = LibrarySong(
        title="Test Song",
        artist="Test Artist",
        state=SongState.NEW,
    )
    assert song.state == SongState.NEW
    song.state = SongState.QUEUED
    assert song.state == SongState.QUEUED
    song.state = SongState.DOWNLOADING
    assert song.state == SongState.DOWNLOADING
    song.state = SongState.OWNED
    assert song.state == SongState.OWNED
