"""
Tests for Phase 1: Core Library Infrastructure.

Tests database connection, schema creation, canonical identity system,
and model serialization.
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime

from library.database import SQLiteDatabase
from library.models import LibrarySong, SongSource, LibraryLocation, SongState
from library.canonical import compute_canonical_hash, CanonicalIdentity
from library.migrator import DatabaseMigrator


class TestCanonicalIdentity:
    """Test canonical identity system."""

    def test_compute_canonical_hash_deterministic(self):
        """Test that canonical hash is deterministic."""
        hash1 = compute_canonical_hash("Song Title", "Artist", "Album", 2020, 180)
        hash2 = compute_canonical_hash("Song Title", "Artist", "Album", 2020, 180)
        assert hash1 == hash2

    def test_compute_canonical_hash_different_metadata(self):
        """Test that different metadata produces different hashes."""
        hash1 = compute_canonical_hash("Song Title", "Artist", "Album", 2020, 180)
        hash2 = compute_canonical_hash("Different Title", "Artist", "Album", 2020, 180)
        assert hash1 != hash2

    def test_compute_canonical_hash_case_insensitive(self):
        """Test that canonicalization is case-insensitive."""
        hash1 = compute_canonical_hash("Song Title", "Artist", "Album")
        hash2 = compute_canonical_hash("song title", "artist", "album")
        assert hash1 == hash2

    def test_compute_canonical_hash_strip_variants(self):
        """Test that variant suffixes are stripped when requested."""
        hash1 = compute_canonical_hash("Song Title", "Artist", "Album", strip_variants=True)
        hash2 = compute_canonical_hash("Song Title - Remix", "Artist", "Album", strip_variants=True)
        # Should be same when variants are stripped
        assert hash1 == hash2

        # But different when not stripped
        hash3 = compute_canonical_hash("Song Title", "Artist", "Album", strip_variants=False)
        hash4 = compute_canonical_hash("Song Title - Remix", "Artist", "Album", strip_variants=False)
        assert hash3 != hash4

    def test_canonical_identity_creation(self):
        """Test CanonicalIdentity creation."""
        identity = CanonicalIdentity.from_metadata(
            "Song Title", "Artist", "Album", 2020, 180
        )
        assert identity.title_original == "Song Title"
        assert identity.artist_original == "Artist"
        assert identity.album_original == "Album"
        assert identity.year == 2020
        assert identity.duration_seconds == 180
        assert identity.hash  # Should have a hash

    def test_canonical_identity_matching(self):
        """Test CanonicalIdentity matching."""
        identity1 = CanonicalIdentity.from_metadata("Song Title", "Artist", "Album", 2020)
        identity2 = CanonicalIdentity.from_metadata("Song Title", "Artist", "Album", 2020)
        assert identity1.matches(identity2)

    def test_canonical_identity_no_match_remix(self):
        """Test that remix versions don't match by default."""
        identity1 = CanonicalIdentity.from_metadata("Song Title", "Artist", "Album", 2020)
        identity2 = CanonicalIdentity.from_metadata("Song Title - Remix", "Artist", "Album", 2020)
        # By default, variants are not stripped, so they should have different hashes
        assert identity1.hash != identity2.hash
        # The second identity should have has_variant=True
        assert identity2.has_variant == True
        # And therefore should not match
        assert not identity1.matches(identity2)

    def test_canonical_identity_match_with_strip_variants(self):
        """Test that remix versions match when variants are stripped."""
        identity1 = CanonicalIdentity.from_metadata("Song Title", "Artist", "Album", 2020, strip_variants=True)
        identity2 = CanonicalIdentity.from_metadata("Song Title - Remix", "Artist", "Album", 2020, strip_variants=True)
        # When variants are stripped, they should have the same hash
        assert identity1.hash == identity2.hash
        # The second identity should still have has_variant=True (original title preserved)
        assert identity2.has_variant == True
        # But when stripped for matching, they should match
        assert identity1.matches(identity2)


class TestDatabaseSchema:
    """Test database schema and migrations."""

    def test_database_connection(self, tmp_path):
        """Test database connection and schema creation."""
        db_path = tmp_path / "test.db"
        db = SQLiteDatabase(db_path)
        db.connect()

        # Check that tables were created
        cursor = db._conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
        """)
        tables = [row[0] for row in cursor.fetchall()]

        expected_tables = [
            'library_locations', 'songs', 'song_sources',
            'downloads', 'discovery_context', 'schema_version'
        ]
        for table in expected_tables:
            assert table in tables, f"Table {table} not found"

        db.close()

    def test_schema_version_tracking(self, tmp_path):
        """Test schema version tracking."""
        db_path = tmp_path / "test.db"
        db = SQLiteDatabase(db_path)
        db.connect()

        # Check schema version
        cursor = db._conn.cursor()
        cursor.execute("SELECT MAX(version) FROM schema_version")
        version = cursor.fetchone()[0]
        assert version == DatabaseMigrator.CURRENT_VERSION

        db.close()

    def test_migration_incremental(self, tmp_path):
        """Test that migrations run incrementally."""
        db_path = tmp_path / "test.db"
        db = SQLiteDatabase(db_path)
        db.connect()

        # First connection should create schema
        cursor = db._conn.cursor()
        cursor.execute("SELECT MAX(version) FROM schema_version")
        version = cursor.fetchone()[0]
        assert version == DatabaseMigrator.CURRENT_VERSION

        # Second connection should not re-run migrations
        db2 = SQLiteDatabase(db_path)
        db2.connect()
        cursor2 = db2._conn.cursor()
        cursor2.execute("SELECT MAX(version) FROM schema_version")
        version2 = cursor2.fetchone()[0]
        assert version2 == DatabaseMigrator.CURRENT_VERSION

        db2.close()
        db.close()


class TestLibraryModels:
    """Test library model operations."""

    def test_add_library_location(self, tmp_path):
        """Test adding a library location."""
        db_path = tmp_path / "test.db"
        db = SQLiteDatabase(db_path)
        db.connect()

        location = LibraryLocation(
            path="/music/library",
            name="My Library",
            is_primary=True
        )
        location_id = db.add_library_location(location)

        assert location_id > 0

        # Retrieve and verify
        retrieved = db.get_library_locations()
        assert len(retrieved) == 1
        assert retrieved[0].name == "My Library"
        assert retrieved[0].is_primary == True

        db.close()

    def test_add_song(self, tmp_path):
        """Test adding a song to the library."""
        db_path = tmp_path / "test.db"
        db = SQLiteDatabase(db_path)
        db.connect()

        # First add a library location
        location = LibraryLocation(path="/music", name="Library")
        location_id = db.add_library_location(location)

        # Add a song
        song = LibrarySong(
            canonical_hash="test_hash_123",
            title_normalized="song title",
            artist_normalized="artist",
            album_normalized="album",
            title="Song Title",
            artist="Artist",
            album="Album",
            year=2020,
            state=SongState.NEW,
            library_location_id=location_id
        )
        song_id = db.add_song(song)

        assert song_id > 0

        # Retrieve and verify
        retrieved = db.get_song(song_id)
        assert retrieved is not None
        assert retrieved.title == "Song Title"
        assert retrieved.artist == "Artist"
        assert retrieved.state == SongState.NEW

        db.close()

    def test_get_song_by_canonical_hash(self, tmp_path):
        """Test retrieving song by canonical hash."""
        db_path = tmp_path / "test.db"
        db = SQLiteDatabase(db_path)
        db.connect()

        song = LibrarySong(
            canonical_hash="test_hash_456",
            title_normalized="song title",
            artist_normalized="artist",
            album_normalized="album",
            title="Song Title",
            artist="Artist",
            album="Album",
            state=SongState.NEW
        )
        db.add_song(song)

        # Retrieve by hash
        retrieved = db.get_song_by_canonical_hash("test_hash_456")
        assert retrieved is not None
        assert retrieved.title == "Song Title"

        # Non-existent hash
        not_found = db.get_song_by_canonical_hash("nonexistent")
        assert not_found is None

        db.close()

    def test_update_song_state(self, tmp_path):
        """Test updating song state."""
        db_path = tmp_path / "test.db"
        db = SQLiteDatabase(db_path)
        db.connect()

        song = LibrarySong(
            canonical_hash="test_hash_789",
            title_normalized="song title",
            artist_normalized="artist",
            album_normalized="album",
            title="Song Title",
            state=SongState.NEW
        )
        song_id = db.add_song(song)

        # Update state
        success = db.update_song_state(song_id, SongState.OWNED)
        assert success

        # Verify
        retrieved = db.get_song(song_id)
        assert retrieved.state == SongState.OWNED

        db.close()

    def test_add_source(self, tmp_path):
        """Test adding a source variant."""
        db_path = tmp_path / "test.db"
        db = SQLiteDatabase(db_path)
        db.connect()

        # Add a song first
        song = LibrarySong(
            canonical_hash="test_hash_source",
            title_normalized="song title",
            artist_normalized="artist",
            album_normalized="album",
            title="Song Title",
            state=SongState.NEW
        )
        song_id = db.add_song(song)

        # Add source
        source = SongSource(
            song_id=song_id,
            source_name="isaimini",
            source_url="https://example.com/song.mp3",
            quality_kbps=320,
            file_size_bytes=5242880
        )
        source_id = db.add_source(source)

        assert source_id > 0

        # Retrieve and verify
        sources = db.get_sources_for_song(song_id)
        assert len(sources) == 1
        assert sources[0].source_name == "isaimini"
        assert sources[0].quality_kbps == 320

        db.close()

    def test_library_stats(self, tmp_path):
        """Test library statistics."""
        db_path = tmp_path / "test.db"
        db = SQLiteDatabase(db_path)
        db.connect()

        # Add some test data
        location = LibraryLocation(path="/music", name="Library")
        db.add_library_location(location)

        for i in range(5):
            song = LibrarySong(
                canonical_hash=f"hash_{i}",
                title_normalized=f"song_{i}",
                artist_normalized="artist",
                album_normalized="album",
                title=f"Song {i}",
                state=SongState.NEW
            )
            db.add_song(song)

        # Get stats
        stats = db.get_library_stats()
        assert stats['total_songs'] == 5
        assert 'songs_by_state' in stats
        assert stats['songs_by_state'].get('NEW', 0) == 5

        db.close()


class TestIntegration:
    """Integration tests for library components."""

    def test_full_workflow(self, tmp_path):
        """Test a complete workflow with all components."""
        db_path = tmp_path / "test.db"
        db = SQLiteDatabase(db_path)
        db.connect()

        # 1. Create canonical identity
        identity = CanonicalIdentity.from_metadata(
            "Test Song", "Test Artist", "Test Album", 2020
        )

        # 2. Add library location
        location = LibraryLocation(
            path="/test/library",
            name="Test Library",
            is_primary=True
        )
        location_id = db.add_library_location(location)

        # 3. Add song using canonical hash
        song = LibrarySong(
            canonical_hash=identity.hash,
            title_normalized=identity.title_normalized,
            artist_normalized=identity.artist_normalized,
            album_normalized=identity.album_normalized,
            title=identity.title_original,
            artist=identity.artist_original,
            album=identity.album_original,
            year=identity.year,
            state=SongState.NEW,
            library_location_id=location_id
        )
        song_id = db.add_song(song)

        # 4. Add source variant
        source = SongSource(
            song_id=song_id,
            source_name="isaimini",
            source_url="https://example.com/song.mp3",
            quality_kbps=320
        )
        db.add_source(source)

        # 5. Verify everything
        retrieved_song = db.get_song(song_id)
        assert retrieved_song.title == "Test Song"
        assert retrieved_song.canonical_hash == identity.hash

        sources = db.get_sources_for_song(song_id)
        assert len(sources) == 1
        assert sources[0].quality_kbps == 320

        db.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
