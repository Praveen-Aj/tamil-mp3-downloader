"""
SQLite database management for the library system.

Provides SQLiteDatabase class for all database operations including
song management, source tracking, download history, and discovery context.
"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from library.models import (
    LibrarySong, SongSource, Download, LibraryLocation, DiscoveryContext,
    SongState, DownloadState
)
from library.migrator import DatabaseMigrator

logger = logging.getLogger(__name__)


class SQLiteDatabase:
    """
    SQLite database interface for the library system.

    Handles all database operations including:
    - Song and source management
    - Download tracking
    - Discovery context
    - Library locations
    """

    def __init__(self, db_path: Path):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._migrator = DatabaseMigrator(self)

    def connect(self) -> None:
        """Establish database connection and run migrations."""
        try:
            # Ensure parent directory exists
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            self._conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=30.0
            )
            self._conn.row_factory = sqlite3.Row

            # Run migrations
            self._migrator.migrate()

            logger.info(f"Database connected: {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
            logger.info("Database connection closed")

    def __enter__(self):
        """Context manager entry."""
        if not self._conn:
            self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    # ------------------------------------------------------------------
    # Song operations
    # ------------------------------------------------------------------

    def add_song(self, song: LibrarySong) -> int:
        """
        Add a song to the library.

        Args:
            song: LibrarySong to add

        Returns:
            ID of inserted song
        """
        with self._conn:
            cursor = self._conn.cursor()
            cursor.execute("""
                INSERT INTO songs (
                    canonical_hash, title_normalized, artist_normalized, album_normalized,
                    year, duration_seconds, title, artist, album, state,
                    quality_kbps, file_size_bytes, library_location_id, file_path,
                    first_discovered_at, last_seen_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                song.canonical_hash,
                song.title_normalized,
                song.artist_normalized,
                song.album_normalized,
                song.year,
                song.duration_seconds,
                song.title,
                song.artist,
                song.album,
                song.state.value,
                song.quality_kbps,
                song.file_size_bytes,
                song.library_location_id,
                song.file_path,
                song.first_discovered_at or datetime.now().isoformat(),
                song.last_seen_at or datetime.now().isoformat(),
            ))
            return cursor.lastrowid

    def get_song(self, song_id: int) -> Optional[LibrarySong]:
        """
        Get a song by ID.

        Args:
            song_id: Song ID

        Returns:
            LibrarySong if found, None otherwise
        """
        cursor = self._conn.cursor()
        cursor.execute("SELECT * FROM songs WHERE id = ?", (song_id,))
        row = cursor.fetchone()
        if row:
            return LibrarySong.from_row(row)
        return None

    def get_song_by_canonical_hash(
        self, canonical_hash: str
    ) -> Optional[LibrarySong]:
        """
        Get a song by canonical hash.

        Args:
            canonical_hash: Canonical hash

        Returns:
            LibrarySong if found, None otherwise
        """
        cursor = self._conn.cursor()
        cursor.execute("SELECT * FROM songs WHERE canonical_hash = ?", (canonical_hash,))
        row = cursor.fetchone()
        if row:
            return LibrarySong.from_row(row)
        return None

    def update_song_state(self, song_id: int, state: SongState) -> bool:
        """
        Update song state.

        Args:
            song_id: Song ID
            state: New state

        Returns:
            True if updated, False otherwise
        """
        with self._conn:
            cursor = self._conn.cursor()
            cursor.execute(
                "UPDATE songs SET state = ?, last_seen_at = ? WHERE id = ?",
                (state.value, datetime.now().isoformat(), song_id)
            )
            return cursor.rowcount > 0

    def update_song_file(
        self,
        song_id: int,
        file_path: str,
        file_size_bytes: int,
        quality_kbps: int,
        library_location_id: int,
    ) -> bool:
        """
        Update song file information after download.

        Args:
            song_id: Song ID
            file_path: Path to downloaded file
            file_size_bytes: File size
            quality_kbps: Quality in kbps
            library_location_id: Library location ID

        Returns:
            True if updated, False otherwise
        """
        with self._conn:
            cursor = self._conn.cursor()
            cursor.execute("""
                UPDATE songs SET
                    file_path = ?, file_size_bytes = ?, quality_kbps = ?,
                    library_location_id = ?, state = ?, last_seen_at = ?
                WHERE id = ?
            """, (
                file_path, file_size_bytes, quality_kbps,
                library_location_id, SongState.OWNED.value,
                datetime.now().isoformat(), song_id
            ))
            return cursor.rowcount > 0

    def get_songs_by_state(self, state: SongState, limit: Optional[int] = None) -> List[LibrarySong]:
        """
        Get songs by state.

        Args:
            state: Song state
            limit: Maximum number of results

        Returns:
            List of LibrarySong
        """
        cursor = self._conn.cursor()
        query = "SELECT * FROM songs WHERE state = ? ORDER BY first_discovered_at DESC"
        if limit:
            query += f" LIMIT {limit}"
        cursor.execute(query, (state.value,))
        return [LibrarySong.from_row(row) for row in cursor.fetchall()]

    def search_songs(self, query: str, limit: int = 50) -> List[LibrarySong]:
        """
        Search songs by title, artist, or album.

        Args:
            query: Search query
            limit: Maximum number of results

        Returns:
            List of matching LibrarySong
        """
        cursor = self._conn.cursor()
        search_pattern = f"%{query}%"
        cursor.execute("""
            SELECT * FROM songs
            WHERE title LIKE ? OR artist LIKE ? OR album LIKE ?
            ORDER BY last_seen_at DESC
            LIMIT ?
        """, (search_pattern, search_pattern, search_pattern, limit))
        return [LibrarySong.from_row(row) for row in cursor.fetchall()]

    # ------------------------------------------------------------------
    # Source operations
    # ------------------------------------------------------------------

    def add_source(self, source: SongSource) -> int:
        """
        Add a source variant for a song.

        Args:
            source: SongSource to add

        Returns:
            ID of inserted source
        """
        with self._conn:
            cursor = self._conn.cursor()
            cursor.execute("""
                INSERT INTO song_sources (
                    song_id, source_name, source_url, quality_kbps, file_size_bytes,
                    file_type, metadata_complete, is_available, reliability_score, discovered_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                source.song_id, source.source_name, source.source_url,
                source.quality_kbps, source.file_size_bytes, source.file_type,
                source.metadata_complete, source.is_available, source.reliability_score,
                source.discovered_at or datetime.now().isoformat(),
            ))
            return cursor.lastrowid

    def get_sources_for_song(self, song_id: int) -> List[SongSource]:
        """
        Get all source variants for a song.

        Args:
            song_id: Song ID

        Returns:
            List of SongSource
        """
        cursor = self._conn.cursor()
        cursor.execute("SELECT * FROM song_sources WHERE song_id = ?", (song_id,))
        return [SongSource.from_row(row) for row in cursor.fetchall()]

    def update_source_availability(self, source_id: int, is_available: bool) -> bool:
        """
        Update source availability.

        Args:
            source_id: Source ID
            is_available: New availability status

        Returns:
            True if updated, False otherwise
        """
        with self._conn:
            cursor = self._conn.cursor()
            cursor.execute("""
                UPDATE song_sources
                SET is_available = ?, availability_last_checked = ?
                WHERE id = ?
            """, (is_available, datetime.now().isoformat(), source_id))
            return cursor.rowcount > 0

    def update_source_reliability(self, source_id: int, reliability_score: float) -> bool:
        """
        Update source reliability score.

        Args:
            source_id: Source ID
            reliability_score: New reliability score (0.0-1.0)

        Returns:
            True if updated, False otherwise
        """
        with self._conn:
            cursor = self._conn.cursor()
            cursor.execute(
                "UPDATE song_sources SET reliability_score = ? WHERE id = ?",
                (reliability_score, source_id)
            )
            return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # Download operations
    # ------------------------------------------------------------------

    def add_download(self, download: Download) -> int:
        """
        Add a download record.

        Args:
            download: Download to add

        Returns:
            ID of inserted download
        """
        with self._conn:
            cursor = self._conn.cursor()
            cursor.execute("""
                INSERT INTO downloads (
                    song_id, song_source_id, planned_at, queued_at, started_at,
                    completed_at, failed_at, library_location_id, output_path,
                    file_size_bytes, download_speed_bps, state, error_message,
                    retry_count, was_upgrade, previous_file_path, previous_quality_kbps
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                download.song_id, download.song_source_id,
                download.planned_at, download.queued_at, download.started_at,
                download.completed_at, download.failed_at, download.library_location_id,
                download.output_path, download.file_size_bytes, download.download_speed_bps,
                download.state.value, download.error_message, download.retry_count,
                download.was_upgrade, download.previous_file_path, download.previous_quality_kbps,
            ))
            return cursor.lastrowid

    def update_download_state(self, download_id: int, state: DownloadState,
                              error_message: Optional[str] = None) -> bool:
        """
        Update download state.

        Args:
            download_id: Download ID
            state: New state
            error_message: Error message if failed

        Returns:
            True if updated, False otherwise
        """
        with self._conn:
            cursor = self._conn.cursor()
            if state == DownloadState.DOWNLOADING:
                cursor.execute(
                    "UPDATE downloads SET state = ?, started_at = ? WHERE id = ?",
                    (state.value, datetime.now().isoformat(), download_id)
                )
            elif state == DownloadState.COMPLETED:
                cursor.execute(
                    "UPDATE downloads SET state = ?, completed_at = ? WHERE id = ?",
                    (state.value, datetime.now().isoformat(), download_id)
                )
            elif state == DownloadState.FAILED:
                cursor.execute(
                    "UPDATE downloads SET state = ?, failed_at = ?, error_message = ? WHERE id = ?",
                    (state.value, datetime.now().isoformat(), error_message, download_id)
                )
            else:
                cursor.execute(
                    "UPDATE downloads SET state = ? WHERE id = ?",
                    (state.value, download_id)
                )
            return cursor.rowcount > 0

    def update_download_completed(
        self,
        download_id: int,
        output_path: str,
        file_size_bytes: int,
        download_speed_bps: Optional[float],
        was_upgrade: bool,
        previous_file_path: Optional[str],
        previous_quality_kbps: Optional[int],
        library_location_id: Optional[int],
    ) -> bool:
        """
        Record successful download completion details.

        Args:
            download_id: Download record ID
            output_path: Path where file was saved
            file_size_bytes: File size
            download_speed_bps: Average speed
            was_upgrade: Whether this was a quality upgrade
            previous_file_path: Old file path if upgrade
            previous_quality_kbps: Old quality if upgrade
            library_location_id: Library location ID

        Returns:
            True if updated, False otherwise
        """
        with self._conn:
            cursor = self._conn.cursor()
            cursor.execute("""
                UPDATE downloads SET
                    state = ?, completed_at = ?,
                    output_path = ?, file_size_bytes = ?,
                    download_speed_bps = ?,
                    was_upgrade = ?, previous_file_path = ?,
                    previous_quality_kbps = ?,
                    library_location_id = ?
                WHERE id = ?
            """, (
                DownloadState.COMPLETED.value,
                datetime.now().isoformat(),
                output_path, file_size_bytes,
                download_speed_bps,
                was_upgrade, previous_file_path,
                previous_quality_kbps,
                library_location_id,
                download_id,
            ))
            return cursor.rowcount > 0

    def get_downloads_for_song(self, song_id: int) -> List[Download]:
        """
        Get download history for a song.

        Args:
            song_id: Song ID

        Returns:
            List of Download
        """
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT * FROM downloads WHERE song_id = ? ORDER BY planned_at DESC",
            (song_id,)
        )
        return [Download.from_row(row) for row in cursor.fetchall()]

    # ------------------------------------------------------------------
    # Discovery context operations
    # ------------------------------------------------------------------

    def add_discovery_context(self, context: DiscoveryContext) -> int:
        """
        Add discovery context for a song.

        Args:
            context: DiscoveryContext to add

        Returns:
            ID of inserted context
        """
        with self._conn:
            cursor = self._conn.cursor()
            cursor.execute("""
                INSERT INTO discovery_context (
                    song_id, source_name, category, album_name, album_url, discovered_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                context.song_id, context.source_name, context.category,
                context.album_name, context.album_url,
                context.discovered_at or datetime.now().isoformat(),
            ))
            return cursor.lastrowid

    def get_discovery_contexts(self, song_id: int) -> List[DiscoveryContext]:
        """
        Get discovery contexts for a song.

        Args:
            song_id: Song ID

        Returns:
            List of DiscoveryContext
        """
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT * FROM discovery_context WHERE song_id = ? ORDER BY discovered_at DESC",
            (song_id,)
        )
        return [DiscoveryContext.from_row(row) for row in cursor.fetchall()]

    # ------------------------------------------------------------------
    # Library location operations
    # ------------------------------------------------------------------

    def add_library_location(self, location: LibraryLocation) -> int:
        """
        Add a library location.

        Args:
            location: LibraryLocation to add

        Returns:
            ID of inserted location
        """
        with self._conn:
            cursor = self._conn.cursor()
            cursor.execute("""
                INSERT INTO library_locations (path, name, is_primary, created_at)
                VALUES (?, ?, ?, ?)
            """, (
                location.path, location.name, location.is_primary,
                location.created_at or datetime.now().isoformat()
            ))
            return cursor.lastrowid

    def get_library_locations(self) -> List[LibraryLocation]:
        """
        Get all library locations.

        Returns:
            List of LibraryLocation
        """
        cursor = self._conn.cursor()
        cursor.execute("SELECT * FROM library_locations ORDER BY is_primary DESC, created_at")
        return [LibraryLocation.from_row(row) for row in cursor.fetchall()]

    def get_primary_library_location(self) -> Optional[LibraryLocation]:
        """
        Get the primary library location.

        Returns:
            LibraryLocation if found, None otherwise
        """
        cursor = self._conn.cursor()
        cursor.execute("SELECT * FROM library_locations WHERE is_primary = 1 LIMIT 1")
        row = cursor.fetchone()
        if row:
            return LibraryLocation.from_row(row)
        return None

    def set_primary_library_location(self, location_id: int) -> bool:
        """
        Set a library location as primary.

        Args:
            location_id: Location ID

        Returns:
            True if updated, False otherwise
        """
        with self._conn:
            cursor = self._conn.cursor()
            # First, unset all primary flags
            cursor.execute("UPDATE library_locations SET is_primary = 0")
            # Then set the new primary
            cursor.execute(
                "UPDATE library_locations SET is_primary = 1 WHERE id = ?",
                (location_id,)
            )
            return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # Statistics and maintenance
    # ------------------------------------------------------------------

    def get_library_stats(self) -> Dict[str, Any]:
        """
        Get library statistics.

        Returns:
            Dictionary with statistics
        """
        cursor = self._conn.cursor()

        # Total songs
        cursor.execute("SELECT COUNT(*) FROM songs")
        total_songs = cursor.fetchone()[0]

        # Songs by state
        cursor.execute("SELECT state, COUNT(*) FROM songs GROUP BY state")
        songs_by_state = {row[0]: row[1] for row in cursor.fetchall()}

        # Total sources
        cursor.execute("SELECT COUNT(*) FROM song_sources")
        total_sources = cursor.fetchone()[0]

        # Total downloads
        cursor.execute("SELECT COUNT(*) FROM downloads")
        total_downloads = cursor.fetchone()[0]

        # Downloads by state
        cursor.execute("SELECT state, COUNT(*) FROM downloads GROUP BY state")
        downloads_by_state = {row[0]: row[1] for row in cursor.fetchall()}

        return {
            'total_songs': total_songs,
            'songs_by_state': songs_by_state,
            'total_sources': total_sources,
            'total_downloads': total_downloads,
            'downloads_by_state': downloads_by_state,
        }

    def vacuum(self) -> None:
        """Run VACUUM to optimize database."""
        self._conn.execute("VACUUM")
        logger.info("Database vacuumed")
