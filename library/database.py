"""
SQLite database management for the library system.

Provides SQLiteDatabase class for all database operations including
song management, source tracking, download history, and discovery context.
"""

import logging
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

from library.models import (
    LibrarySong, SongSource, Download, LibraryLocation, DiscoveryContext,
    SongState, DownloadState, ImportJob, ImportJobItem, JobStatus, ItemState,
    Movie, Artist, MovieActor, MovieComposer, SongArtist, SongMovie,
    UserSongMetadata, Playlist, PlaylistItem, Chart, ChartEntry
)
from library.migrator import DatabaseMigrator
from library.filter_engine import SongFilterCriteria, ComposableFilterEngine

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
        # Serialize ALL connection-level access (sqlite3 Connection is not
        # thread-safe even with check_same_thread=False)
        self._lock = threading.RLock()

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

    def execute_write(self, sql: str, params: tuple = ()) -> bool:
        """Execute a write SQL query in a thread-safe transaction."""
        with self._lock:
            with self._conn:
                cursor = self._conn.cursor()
                cursor.execute(sql, params)
                return cursor.rowcount > 0

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
        Add a song to the library, idempotently and thread-safely.

        Uses INSERT OR IGNORE so concurrent or repeated inserts of the same
        canonical_hash never raise an IntegrityError.  If the row already
        exists (race condition or explicit re-registration), the existing ID
        is returned via a SELECT fallback.

        Args:
            song: LibrarySong to add

        Returns:
            ID of the inserted or pre-existing song
        """
        with self._lock:
            with self._conn:
                cursor = self._conn.cursor()
                cursor.execute("""
                    INSERT OR IGNORE INTO songs (
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
                # rowcount == 1: inserted; == 0: ignored (row already exists)
                if cursor.rowcount == 1:
                    return cursor.lastrowid
                # Row already existed — retrieve its ID
                cursor.execute(
                    "SELECT id FROM songs WHERE canonical_hash = ?",
                    (song.canonical_hash,)
                )
                return cursor.fetchone()[0]


    def get_song(self, song_id: int) -> Optional[LibrarySong]:
        """
        Get a song by ID.

        Args:
            song_id: Song ID

        Returns:
            LibrarySong if found, None otherwise
        """
        with self._lock:
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
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("SELECT * FROM songs WHERE canonical_hash = ?", (canonical_hash,))
            row = cursor.fetchone()
            if row:
                return LibrarySong.from_row(row)
            return None

    def get_song_by_hash(self, canonical_hash: str) -> Optional[LibrarySong]:
        """Alias for get_song_by_canonical_hash."""
        return self.get_song_by_canonical_hash(canonical_hash)

    def update_song_state(
        self,
        song_id: int,
        state: SongState,
        file_path: Optional[str] = None,
        file_size_bytes: Optional[int] = None,
        quality_kbps: Optional[int] = None,
    ) -> bool:
        """
        Update song state and optional file attributes.
        """
        with self._lock:
            with self._conn:
                cursor = self._conn.cursor()
                if file_path is not None:
                    cursor.execute("""
                        UPDATE songs SET
                            state = ?, file_path = ?, file_size_bytes = ?,
                            quality_kbps = ?, last_seen_at = ?
                        WHERE id = ?
                    """, (
                        state.value, file_path, file_size_bytes,
                        quality_kbps, datetime.now().isoformat(), song_id
                    ))
                else:
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
        quality_kbps: Optional[int] = None,
        library_location_id: int = 1,
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
        with self._lock:
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

    def clear_song_download_state(self, song_id: int) -> bool:
        """
        Reset a song's downloaded file attributes and transition state back to NEW.

        Args:
            song_id: Song ID

        Returns:
            True if updated, False otherwise
        """
        with self._lock:
            with self._conn:
                cursor = self._conn.cursor()
                cursor.execute("""
                    UPDATE songs SET
                        file_path = NULL,
                        file_size_bytes = NULL,
                        quality_kbps = NULL,
                        state = ?,
                        last_seen_at = ?
                    WHERE id = ?
                """, (
                    SongState.NEW.value,
                    datetime.now().isoformat(),
                    song_id,
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
        with self._lock:
            cursor = self._conn.cursor()
            query = "SELECT * FROM songs WHERE state = ? ORDER BY first_discovered_at DESC"
            if limit:
                query += f" LIMIT {limit}"
            cursor.execute(query, (state.value,))
            return [LibrarySong.from_row(row) for row in cursor.fetchall()]

    def update_song_quality(self, song_id: int, quality_kbps: int) -> bool:
        """Update song quality in kbps."""
        with self._lock:
            with self._conn:
                cursor = self._conn.cursor()
                cursor.execute(
                    "UPDATE songs SET quality_kbps = ?, last_seen_at = ? WHERE id = ?",
                    (quality_kbps, datetime.now().isoformat(), song_id)
                )
                return cursor.rowcount > 0

    def search_songs(self, query: str, limit: int = 50) -> List[LibrarySong]:
        """
        Search songs by title, artist, or album.

        Args:
            query: Search query
            limit: Maximum number of results

        Returns:
            List of matching LibrarySong
        """
        with self._lock:
            cursor = self._conn.cursor()
            search_pattern = f"%{query}%"
            cursor.execute("""
                SELECT * FROM songs
                WHERE title LIKE ? OR artist LIKE ? OR album LIKE ?
                ORDER BY last_seen_at DESC
                LIMIT ?
            """, (search_pattern, search_pattern, search_pattern, limit))
            return [LibrarySong.from_row(row) for row in cursor.fetchall()]

    def search_and_filter_songs(
        self,
        criteria: SongFilterCriteria,
        sort_by: str = "id",
        ascending: bool = False,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """
        Execute composable search, filtering, sorting, and pagination across songs.

        Uses FTS5 virtual table for scalable, tokenized prefix search when query is present,
        with graceful fallback to LIKE matching if FTS5 query encounters an error.

        Args:
            criteria: Search and filter criteria
            sort_by: Field to sort by ('id', 'title', 'artist', 'album', 'quality', 'state', 'year', 'date_added', 'rank')
            ascending: Sort direction
            page: 1-indexed page number
            page_size: Maximum records per page

        Returns:
            Dict containing songs list, total items, total pages, current page, page size
        """
        engine = ComposableFilterEngine()
        with self._lock:
            try:
                count_sql, count_params, data_sql, data_params = engine.build_query(
                    criteria=criteria,
                    sort_by=sort_by,
                    ascending=ascending,
                    page=page,
                    page_size=page_size,
                    use_fts=True,
                )
                cursor = self._conn.cursor()
                cursor.execute(count_sql, count_params)
                total_items = cursor.fetchone()[0]
                total_pages = max(1, (total_items + page_size - 1) // page_size) if total_items > 0 else 1

                cursor.execute(data_sql, data_params)
                songs = [LibrarySong.from_row(row) for row in cursor.fetchall()]
            except Exception as e:
                logger.warning(f"FTS query failed, falling back to LIKE: {e}")
                count_sql, count_params, data_sql, data_params = engine.build_query(
                    criteria=criteria,
                    sort_by=sort_by,
                    ascending=ascending,
                    page=page,
                    page_size=page_size,
                    use_fts=False,
                )
                cursor = self._conn.cursor()
                cursor.execute(count_sql, count_params)
                total_items = cursor.fetchone()[0]
                total_pages = max(1, (total_items + page_size - 1) // page_size) if total_items > 0 else 1

                cursor.execute(data_sql, data_params)
                songs = [LibrarySong.from_row(row) for row in cursor.fetchall()]

            return {
                "songs": songs,
                "total_items": total_items,
                "total_pages": total_pages,
                "page": page,
                "page_size": page_size,
            }

    def get_filter_options(self) -> Dict[str, List[Any]]:
        """
        Get distinct available values for library filter dropdowns.

        Returns:
            Dict containing sorted unique sources, qualities, artists, and albums.
        """
        with self._lock:
            cursor = self._conn.cursor()
            # Sources from song_sources
            cursor.execute(
                "SELECT DISTINCT source_name FROM song_sources WHERE source_name IS NOT NULL AND TRIM(source_name) != '' ORDER BY source_name ASC"
            )
            sources = [r[0] for r in cursor.fetchall()]

            # Qualities from songs
            cursor.execute(
                "SELECT DISTINCT quality_kbps FROM songs WHERE quality_kbps IS NOT NULL AND quality_kbps > 0 ORDER BY quality_kbps DESC"
            )
            qualities = [r[0] for r in cursor.fetchall()]

            # Artists
            cursor.execute(
                "SELECT DISTINCT artist FROM songs WHERE artist IS NOT NULL AND TRIM(artist) != '' ORDER BY artist ASC LIMIT 200"
            )
            artists = [r[0] for r in cursor.fetchall()]

            # Albums
            cursor.execute(
                "SELECT DISTINCT album FROM songs WHERE album IS NOT NULL AND TRIM(album) != '' ORDER BY album ASC LIMIT 200"
            )
            albums = [r[0] for r in cursor.fetchall()]

            return {
                "sources": sources,
                "qualities": qualities,
                "artists": artists,
                "albums": albums,
            }

    def get_paginated_songs(
        self,
        query: str = "",
        state_filter: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
        sort_by: str = "id",
        ascending: bool = False,
    ) -> Dict[str, Any]:
        """
        Get paginated songs from SQLite with thread lock protection.
        Delegates to search_and_filter_songs for FTS5-powered indexing and composable criteria.

        Args:
            query: Search string for title, artist, album
            state_filter: "ALL", "OWNED", "UNOWNED", "DOWNLOADED", "NOT DOWNLOADED"
            page: 1-indexed page number
            page_size: Rows per page
            sort_by: Field name to sort by
            ascending: Sort direction

        Returns:
            Dict containing list of songs, total items count, total pages count, page, page_size
        """
        criteria = SongFilterCriteria.from_legacy_params(query=query, state_filter=state_filter)
        # If user searched and sort_by is default 'id', rank gives best relevance
        effective_sort = "rank" if (query and query.strip() and sort_by == "id") else sort_by
        return self.search_and_filter_songs(
            criteria=criteria,
            sort_by=effective_sort,
            ascending=ascending,
            page=page,
            page_size=page_size,
        )

    # ------------------------------------------------------------------
    # Source operations
    # ------------------------------------------------------------------

    def add_source(self, source: SongSource) -> int:
        """
        Add a source variant for a song, idempotently and thread-safely.

        Uses INSERT OR IGNORE on the (song_id, source_url) unique constraint
        so duplicate source URLs never raise IntegrityError.  Returns the
        existing row ID if the URL was already registered.

        Args:
            source: SongSource to add

        Returns:
            ID of inserted or pre-existing source
        """
        with self._lock:
            with self._conn:
                cursor = self._conn.cursor()
                cursor.execute("""
                    INSERT OR IGNORE INTO song_sources (
                        song_id, source_name, source_url, download_reference, quality_kbps, file_size_bytes,
                        file_type, metadata_complete, is_available, reliability_score, discovered_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    source.song_id, source.source_name, source.source_url, source.download_reference,
                    source.quality_kbps, source.file_size_bytes, source.file_type,
                    source.metadata_complete, source.is_available, source.reliability_score,
                    source.discovered_at or datetime.now().isoformat(),
                ))
                if cursor.rowcount == 1:
                    return cursor.lastrowid
                # Already existed — look it up
                cursor.execute(
                    "SELECT id FROM song_sources WHERE song_id = ? AND source_url = ?",
                    (source.song_id, source.source_url)
                )
                return cursor.fetchone()[0]


    def get_sources_for_song(self, song_id: int) -> List[SongSource]:
        """
        Get all source variants for a song.

        Args:
            song_id: Song ID

        Returns:
            List of SongSource
        """
        with self._lock:
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
        with self._lock:
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
        with self._lock:
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
        with self._lock:
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
        with self._lock:
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
        with self._lock:
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
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute(
                "SELECT * FROM downloads WHERE song_id = ? ORDER BY planned_at DESC",
                (song_id,)
            )
            return [Download.from_row(row) for row in cursor.fetchall()]

    def get_download(self, download_id: int) -> Optional[Download]:
        """Get a download by ID."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("SELECT * FROM downloads WHERE id = ?", (download_id,))
            row = cursor.fetchone()
            return Download.from_row(row) if row else None

    def get_all_downloads(self) -> List[Download]:
        """Get all downloads."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("SELECT * FROM downloads ORDER BY id DESC")
            return [Download.from_row(row) for row in cursor.fetchall()]

    def delete_download_record(self, download_id: int) -> bool:
        """Delete a download record by ID."""
        with self._lock:
            with self._conn:
                cursor = self._conn.cursor()
                cursor.execute("DELETE FROM downloads WHERE id = ?", (download_id,))
                return cursor.rowcount > 0

    def get_source_by_id(self, source_id: int) -> Optional[SongSource]:
        """Get a song source by ID."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("SELECT * FROM song_sources WHERE id = ?", (source_id,))
            row = cursor.fetchone()
            return SongSource.from_row(row) if row else None

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
        with self._lock:
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
        with self._lock:
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
        with self._lock:
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
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("SELECT * FROM library_locations ORDER BY is_primary DESC, created_at")
            return [LibraryLocation.from_row(row) for row in cursor.fetchall()]

    def get_primary_library_location(self) -> Optional[LibraryLocation]:
        """
        Get the primary library location.

        Returns:
            LibraryLocation if found, None otherwise
        """
        with self._lock:
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
        with self._lock:
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

    def update_source_reliability(self, source_id: int, score: float) -> bool:
        """
        Update source reliability score.

        Args:
            source_id: Source ID
            score: New reliability score (0.0 to 1.0)

        Returns:
            True if updated, False otherwise
        """
        with self._lock:
            with self._conn:
                cursor = self._conn.cursor()
                cursor.execute(
                    "UPDATE song_sources SET reliability_score = ? WHERE id = ?",
                    (max(0.0, min(1.0, score)), source_id)
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

    def reconcile_filesystem_integrity(self, clean_stale_jobs: bool = False) -> int:
        """
        Reconcile database records against the physical filesystem.

        Scans all songs marked as OWNED (Downloaded):
        If file_path is NULL, empty, or does not exist on disk,
        resets the song state to NEW and clears file path/size attributes.

        Returns:
            Number of orphaned records reconciled
        """
        import os
        reconciled_count = 0
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("SELECT id, file_path FROM songs WHERE state = ?", (SongState.OWNED.value,))
            rows = cursor.fetchall()
            orphans = []
            for row in rows:
                song_id, fpath = row[0], row[1]
                if not fpath or not os.path.isfile(fpath) or os.path.getsize(fpath) == 0:
                    orphans.append(song_id)

            if orphans:
                with self._conn:
                    for song_id in orphans:
                        cursor.execute("""
                            UPDATE songs SET
                                file_path = NULL,
                                file_size_bytes = NULL,
                                state = ?,
                                last_seen_at = ?
                            WHERE id = ?
                        """, (SongState.NEW.value, datetime.now().isoformat(), song_id))
                        reconciled_count += 1
            if clean_stale_jobs:
                self.clean_stale_transient_downloads()
        return reconciled_count

    def clean_stale_transient_downloads(self) -> int:
        """Clean up stale transient DOWNLOADING/QUEUED states from crashed/interrupted previous runs."""
        cleaned_count = 0
        with self._lock:
            with self._conn:
                cursor = self._conn.cursor()
                cursor.execute("""
                    UPDATE songs SET state = ?
                    WHERE state IN (?, ?) AND file_path IS NULL
                """, (SongState.NEW.value, SongState.DOWNLOADING.value, SongState.QUEUED.value))
                cursor.execute("""
                    UPDATE downloads SET state = ?, error_message = 'Interrupted process'
                    WHERE state IN (?, ?)
                """, (DownloadState.FAILED.value, DownloadState.DOWNLOADING.value, DownloadState.QUEUED.value))
                cleaned_count = cursor.rowcount
        return cleaned_count

    def vacuum(self) -> None:
        """Run VACUUM to optimize database."""
        self._conn.execute("VACUUM")
        logger.info("Database vacuumed")

    # ------------------------------------------------------------------
    # Persistent Import Jobs operations
    # ------------------------------------------------------------------

    def create_import_job(self, job: ImportJob) -> str:
        """Insert or replace an import job in the database."""
        with self._lock:
            with self._conn:
                now_str = datetime.now().isoformat()
                self._conn.execute("""
                    INSERT INTO import_jobs (
                        id, url, platform, content_type, title, artist,
                        total_tracks, artwork_url, status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        status=excluded.status,
                        updated_at=excluded.updated_at
                """, (
                    job.id, job.url, job.platform, job.content_type, job.title,
                    job.artist, job.total_tracks, job.artwork_url,
                    job.status.value,
                    job.created_at.isoformat() if job.created_at else now_str,
                    job.updated_at.isoformat() if job.updated_at else now_str,
                ))
                return job.id

    def get_import_job(self, job_id: str) -> Optional[ImportJob]:
        """Fetch an import job by ID."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("SELECT * FROM import_jobs WHERE id = ?", (job_id,))
            row = cursor.fetchone()
            return ImportJob.from_row(row) if row else None

    def get_recent_import_jobs(self, limit: int = 20) -> List[ImportJob]:
        """Fetch recent import jobs ordered by creation date."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("""
                SELECT * FROM import_jobs
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))
            return [ImportJob.from_row(row) for row in cursor.fetchall()]

    def update_import_job_status(self, job_id: str, status: JobStatus) -> bool:
        """Update status and timestamp of an import job."""
        with self._lock:
            with self._conn:
                cursor = self._conn.cursor()
                cursor.execute("""
                    UPDATE import_jobs
                    SET status = ?, updated_at = ?
                    WHERE id = ?
                """, (status.value, datetime.now().isoformat(), job_id))
                return cursor.rowcount > 0

    def add_import_job_items(self, items: List[ImportJobItem]) -> bool:
        """Batch insert import job items."""
        if not items:
            return True
        with self._lock:
            with self._conn:
                now_str = datetime.now().isoformat()
                data = [
                    (
                        item.job_id, item.track_index, item.title, item.artist, item.album,
                        item.duration_seconds, item.state.value, item.selected_provider,
                        item.selected_source_url, item.match_confidence, item.match_explanation,
                        item.error_message, item.download_id, item.canonical_song_id,
                        now_str, now_str
                    )
                    for item in items
                ]
                self._conn.executemany("""
                    INSERT INTO import_job_items (
                        job_id, track_index, title, artist, album, duration_seconds,
                        state, selected_provider, selected_source_url, match_confidence,
                        match_explanation, error_message, download_id, canonical_song_id,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, data)
                return True

    def get_import_job_items(self, job_id: str) -> List[ImportJobItem]:
        """Fetch all items for a given import job."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("""
                SELECT * FROM import_job_items
                WHERE job_id = ?
                ORDER BY track_index ASC
            """, (job_id,))
            return [ImportJobItem.from_row(row) for row in cursor.fetchall()]

    def update_import_job_item_state(
        self,
        item_id: int,
        state: ItemState,
        error_message: Optional[str] = None,
        download_id: Optional[int] = None,
        canonical_song_id: Optional[int] = None,
    ) -> bool:
        """Update state and metadata of a single job item."""
        with self._lock:
            with self._conn:
                cursor = self._conn.cursor()
                cursor.execute("""
                    UPDATE import_job_items
                    SET state = ?,
                        error_message = COALESCE(?, error_message),
                        download_id = COALESCE(?, download_id),
                        canonical_song_id = COALESCE(?, canonical_song_id),
                        updated_at = ?
                    WHERE id = ?
                """, (
                    state.value,
                    error_message,
                    download_id,
                    canonical_song_id,
                    datetime.now().isoformat(),
                    item_id
                ))
                return cursor.rowcount > 0

    def get_job_progress_stats(self, job_id: str) -> Dict[str, int]:
        """Get aggregate track status counts for an import job."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("""
                SELECT state, COUNT(*)
                FROM import_job_items
                WHERE job_id = ?
                GROUP BY state
            """, (job_id,))
            counts = {row[0]: row[1] for row in cursor.fetchall()}
            cursor.execute("SELECT COUNT(*) FROM import_job_items WHERE job_id = ?", (job_id,))
            total = cursor.fetchone()[0]
            counts['TOTAL'] = total
            return counts

    def delete_song(self, song_id: int) -> bool:
        """Delete a song and its associated sources and download records from the database."""
        with self._lock:
            with self._conn:
                cursor = self._conn.cursor()
                cursor.execute("DELETE FROM song_sources WHERE song_id = ?", (song_id,))
                cursor.execute("DELETE FROM downloads WHERE song_id = ?", (song_id,))
                cursor.execute("DELETE FROM songs WHERE id = ?", (song_id,))
                return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # V5.1 Discovery & Library Models: Movies
    # ------------------------------------------------------------------

    def add_movie(self, movie: Movie) -> int:
        """Add a movie to the catalog or return existing ID."""
        with self._lock:
            with self._conn:
                cursor = self._conn.cursor()
                cursor.execute("""
                    INSERT OR IGNORE INTO movies (
                        title, title_normalized, year, director, poster_url,
                        banner_url, local_poster_path, track_count, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    movie.title,
                    movie.title_normalized,
                    movie.year,
                    movie.director,
                    movie.poster_url,
                    movie.banner_url,
                    movie.local_poster_path,
                    movie.track_count,
                    (movie.created_at or datetime.now()).isoformat(),
                    (movie.updated_at or datetime.now()).isoformat(),
                ))
                if cursor.rowcount > 0:
                    return cursor.lastrowid
                cursor.execute("SELECT id FROM movies WHERE title = ?", (movie.title,))
                row = cursor.fetchone()
                return row[0] if row else 0

    def get_movie(self, movie_id: int) -> Optional[Movie]:
        """Get movie by database ID."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("SELECT * FROM movies WHERE id = ?", (movie_id,))
            row = cursor.fetchone()
            return Movie.from_row(row) if row else None

    def get_movie_by_title(self, title: str) -> Optional[Movie]:
        """Get movie by title."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("SELECT * FROM movies WHERE title = ?", (title,))
            row = cursor.fetchone()
            return Movie.from_row(row) if row else None

    def update_movie(self, movie: Movie) -> bool:
        """Update an existing movie record."""
        if not movie.id:
            raise ValueError("Movie ID is required for update")
        with self._lock:
            with self._conn:
                cursor = self._conn.cursor()
                cursor.execute("""
                    UPDATE movies SET
                        title = ?,
                        title_normalized = ?,
                        year = ?,
                        director = ?,
                        poster_url = ?,
                        banner_url = ?,
                        local_poster_path = ?,
                        track_count = ?,
                        updated_at = ?
                    WHERE id = ?
                """, (
                    movie.title,
                    movie.title_normalized,
                    movie.year,
                    movie.director,
                    movie.poster_url,
                    movie.banner_url,
                    movie.local_poster_path,
                    movie.track_count,
                    datetime.now().isoformat(),
                    movie.id,
                ))
                return cursor.rowcount > 0

    def list_movies(self, limit: int = 50, offset: int = 0) -> List[Movie]:
        """List movies ordered by year descending, title ascending."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("""
                SELECT * FROM movies
                ORDER BY year DESC, title ASC
                LIMIT ? OFFSET ?
            """, (limit, offset))
            return [Movie.from_row(r) for r in cursor.fetchall()]

    def search_and_filter_movies(
        self,
        query: str = "",
        min_year: Optional[int] = None,
        max_year: Optional[int] = None,
        sort_by: str = "year",
        ascending: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Search, filter, and paginate movies with aggregated song counts and download states.

        Returns:
            Tuple of (List of movie dictionaries with metadata and counts, total matching movie count)
        """
        with self._lock:
            cursor = self._conn.cursor()
            where_clauses = []
            params: List[Any] = []

            if query and query.strip():
                clean_q = f"%{query.strip()}%"
                where_clauses.append("(m.title LIKE ? OR m.director LIKE ? OR m.title_normalized LIKE ?)")
                params.extend([clean_q, clean_q, clean_q.lower()])

            if min_year is not None:
                where_clauses.append("m.year >= ?")
                params.append(min_year)

            if max_year is not None:
                where_clauses.append("m.year <= ?")
                params.append(max_year)

            where_str = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

            # 1. Total matching count
            count_sql = f"SELECT COUNT(*) FROM movies m {where_str}"
            cursor.execute(count_sql, tuple(params))
            total_count = cursor.fetchone()[0]

            # 2. Sort ordering
            direction = "ASC" if ascending else "DESC"
            sort_map = {
                "year": f"COALESCE(m.year, 0) {direction}, m.title ASC",
                "title": f"m.title {direction}",
                "tracks": f"total_songs {direction}, m.year DESC",
                "downloaded": f"downloaded_count {direction}, m.year DESC",
                "id": f"m.id {direction}",
            }
            order_by = sort_map.get(sort_by, f"COALESCE(m.year, 0) {direction}, m.title ASC")

            # 3. Query movies with aggregated counts
            query_sql = f"""
                SELECT
                    m.id,
                    m.title,
                    m.title_normalized,
                    m.year,
                    m.director,
                    m.poster_url,
                    m.banner_url,
                    m.local_poster_path,
                    m.track_count as stored_track_count,
                    COUNT(DISTINCT sm.song_id) as total_songs,
                    COUNT(DISTINCT CASE WHEN s.state = 'OWNED' THEN sm.song_id END) as downloaded_count,
                    COUNT(DISTINCT CASE WHEN s.state != 'OWNED' OR s.state IS NULL THEN sm.song_id END) as missing_count
                FROM movies m
                LEFT JOIN song_movies sm ON m.id = sm.movie_id
                LEFT JOIN songs s ON sm.song_id = s.id
                {where_str}
                GROUP BY m.id
                ORDER BY {order_by}
                LIMIT ? OFFSET ?
            """
            query_params = list(params) + [limit, offset]
            cursor.execute(query_sql, tuple(query_params))

            results = []
            for row in cursor.fetchall():
                tot_songs = row['total_songs']
                dl_count = row['downloaded_count']
                miss_count = row['missing_count']
                stored_count = row['stored_track_count'] or 0

                # Display track count is max of linked songs or stored track_count
                display_track_count = max(tot_songs, stored_count)
                # If there are stored tracks but fewer linked songs, adjust missing
                if display_track_count > tot_songs and tot_songs == 0:
                    miss_count = display_track_count

                results.append({
                    "id": row['id'],
                    "title": row['title'],
                    "title_normalized": row['title_normalized'],
                    "year": row['year'],
                    "director": row['director'],
                    "poster_url": row['poster_url'],
                    "banner_url": row['banner_url'],
                    "local_poster_path": row['local_poster_path'],
                    "total_songs": display_track_count,
                    "downloaded_count": dl_count,
                    "missing_count": miss_count,
                    "is_complete": (display_track_count > 0 and dl_count >= display_track_count),
                })

            return results, total_count

    def get_movie_download_stats(self, movie_id: int) -> Dict[str, int]:
        """Get verified download stats for a movie: total, downloaded, missing."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("""
                SELECT
                    COUNT(DISTINCT sm.song_id) as total,
                    COUNT(DISTINCT CASE WHEN s.state = 'OWNED' THEN sm.song_id END) as downloaded,
                    COUNT(DISTINCT CASE WHEN s.state != 'OWNED' OR s.state IS NULL THEN sm.song_id END) as missing
                FROM song_movies sm
                LEFT JOIN songs s ON sm.song_id = s.id
                WHERE sm.movie_id = ?
            """, (movie_id,))
            row = cursor.fetchone()
            if not row or row['total'] == 0:
                # Check if movie exists and has a stored track_count
                cursor.execute("SELECT track_count FROM movies WHERE id = ?", (movie_id,))
                m_row = cursor.fetchone()
                stored = m_row[0] if m_row and m_row[0] else 0
                return {"total": stored, "downloaded": 0, "missing": stored}

            tot = row['total'] or 0
            dl = row['downloaded'] or 0
            miss = row['missing'] or 0
            return {"total": tot, "downloaded": dl, "missing": miss}

    def get_movie_songs_detailed(self, movie_id: int) -> List[Dict[str, Any]]:
        """Get detailed song list for a movie with track numbers and download states."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("""
                SELECT
                    s.id as song_id,
                    sm.track_number,
                    s.title,
                    s.artist,
                    s.album,
                    s.year,
                    s.duration_seconds,
                    s.state,
                    s.quality_kbps,
                    s.file_size_bytes,
                    s.file_path,
                    (
                        SELECT src.source_name
                        FROM song_sources src
                        WHERE src.song_id = s.id
                        ORDER BY src.quality_kbps DESC, src.reliability_score DESC
                        LIMIT 1
                    ) as primary_source
                FROM song_movies sm
                JOIN songs s ON sm.song_id = s.id
                WHERE sm.movie_id = ?
                ORDER BY COALESCE(sm.track_number, 999), s.title ASC
            """, (movie_id,))
            results = []
            for r in cursor.fetchall():
                is_downloaded = (r['state'] == 'OWNED')
                results.append({
                    "song_id": r['song_id'],
                    "track_number": r['track_number'],
                    "title": r['title'],
                    "artist": r['artist'] or "Unknown Artist",
                    "album": r['album'] or "",
                    "year": r['year'],
                    "duration_seconds": r['duration_seconds'],
                    "state": r['state'],
                    "is_downloaded": is_downloaded,
                    "download_status_display": "✓ Downloaded" if is_downloaded else "Not Downloaded",
                    "quality_kbps": r['quality_kbps'],
                    "quality_display": f"{r['quality_kbps']} kbps" if r['quality_kbps'] else "320 kbps",
                    "file_path": r['file_path'],
                    "source": r['primary_source'] or "Regional",
                })
            return results

    def delete_movie(self, movie_id: int) -> bool:
        """Delete a movie by ID (does not delete associated songs)."""
        with self._lock:
            with self._conn:
                cursor = self._conn.cursor()
                cursor.execute("DELETE FROM movie_actors WHERE movie_id = ?", (movie_id,))
                cursor.execute("DELETE FROM movie_composers WHERE movie_id = ?", (movie_id,))
                cursor.execute("DELETE FROM song_movies WHERE movie_id = ?", (movie_id,))
                cursor.execute("DELETE FROM movies WHERE id = ?", (movie_id,))
                return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # V5.1 Discovery & Library Models: Artists
    # ------------------------------------------------------------------

    def add_artist(self, artist: Artist) -> int:
        """Add an artist to directory or return existing ID."""
        with self._lock:
            with self._conn:
                cursor = self._conn.cursor()
                cursor.execute("""
                    INSERT OR IGNORE INTO artists (
                        name, name_normalized, role, photo_url, local_photo_path,
                        bio, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    artist.name,
                    artist.name_normalized,
                    artist.role,
                    artist.photo_url,
                    artist.local_photo_path,
                    artist.bio,
                    (artist.created_at or datetime.now()).isoformat(),
                    (artist.updated_at or datetime.now()).isoformat(),
                ))
                if cursor.rowcount > 0:
                    return cursor.lastrowid
                cursor.execute("SELECT id FROM artists WHERE name = ?", (artist.name,))
                row = cursor.fetchone()
                return row[0] if row else 0

    def get_artist(self, artist_id: int) -> Optional[Artist]:
        """Get artist by database ID."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("SELECT * FROM artists WHERE id = ?", (artist_id,))
            row = cursor.fetchone()
            return Artist.from_row(row) if row else None

    def get_artist_by_name(self, name: str) -> Optional[Artist]:
        """Get artist by exact name."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("SELECT * FROM artists WHERE name = ?", (name,))
            row = cursor.fetchone()
            return Artist.from_row(row) if row else None

    def list_artists(self, role: Optional[str] = None, limit: int = 50, offset: int = 0) -> List[Artist]:
        """List artists optionally filtered by role."""
        with self._lock:
            cursor = self._conn.cursor()
            if role:
                cursor.execute("""
                    SELECT * FROM artists
                    WHERE role = ?
                    ORDER BY name ASC
                    LIMIT ? OFFSET ?
                """, (role, limit, offset))
            else:
                cursor.execute("""
                    SELECT * FROM artists
                    ORDER BY name ASC
                    LIMIT ? OFFSET ?
                """, (limit, offset))
            return [Artist.from_row(r) for r in cursor.fetchall()]

    def delete_artist(self, artist_id: int) -> bool:
        """Delete an artist by ID (does not delete associated songs)."""
        with self._lock:
            with self._conn:
                cursor = self._conn.cursor()
                cursor.execute("DELETE FROM movie_actors WHERE actor_id = ?", (artist_id,))
                cursor.execute("DELETE FROM movie_composers WHERE composer_id = ?", (artist_id,))
                cursor.execute("DELETE FROM song_artists WHERE artist_id = ?", (artist_id,))
                cursor.execute("DELETE FROM artists WHERE id = ?", (artist_id,))
                return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # V5.1 Relational Join Tables: Movie Actors & Composers
    # ------------------------------------------------------------------

    def add_movie_actor(self, movie_id: int, actor_id: int, character_name: Optional[str] = None) -> bool:
        """Link an actor to a movie."""
        with self._lock:
            with self._conn:
                cursor = self._conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO movie_actors (movie_id, actor_id, character_name)
                    VALUES (?, ?, ?)
                """, (movie_id, actor_id, character_name))
                return cursor.rowcount > 0

    def get_movie_actors(self, movie_id: int) -> List[Tuple[Artist, Optional[str]]]:
        """Get all actors in a movie with character names."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("""
                SELECT a.*, ma.character_name
                FROM artists a
                JOIN movie_actors ma ON a.id = ma.actor_id
                WHERE ma.movie_id = ?
                ORDER BY a.name ASC
            """, (movie_id,))
            return [(Artist.from_row(r), r['character_name']) for r in cursor.fetchall()]

    def add_movie_composer(self, movie_id: int, composer_id: int) -> bool:
        """Link a music director/composer to a movie."""
        with self._lock:
            with self._conn:
                cursor = self._conn.cursor()
                cursor.execute("""
                    INSERT OR IGNORE INTO movie_composers (movie_id, composer_id)
                    VALUES (?, ?)
                """, (movie_id, composer_id))
                return cursor.rowcount > 0

    def get_movie_composers(self, movie_id: int) -> List[Artist]:
        """Get all composers/music directors for a movie."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("""
                SELECT a.*
                FROM artists a
                JOIN movie_composers mc ON a.id = mc.composer_id
                WHERE mc.movie_id = ?
                ORDER BY a.name ASC
            """, (movie_id,))
            return [Artist.from_row(r) for r in cursor.fetchall()]

    # ------------------------------------------------------------------
    # V5.1 Relational Join Tables: Song Artists & Song Movies
    # ------------------------------------------------------------------

    def add_song_artist(self, song_id: int, artist_id: int, role: str = "singer") -> bool:
        """Link a canonical song to an artist with a role."""
        with self._lock:
            with self._conn:
                cursor = self._conn.cursor()
                cursor.execute("""
                    INSERT OR IGNORE INTO song_artists (song_id, artist_id, role)
                    VALUES (?, ?, ?)
                """, (song_id, artist_id, role))
                return cursor.rowcount > 0

    def get_song_artists(self, song_id: int) -> List[Tuple[Artist, str]]:
        """Get all credited artists for a canonical song."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("""
                SELECT a.*, sa.role
                FROM artists a
                JOIN song_artists sa ON a.id = sa.artist_id
                WHERE sa.song_id = ?
                ORDER BY sa.role ASC, a.name ASC
            """, (song_id,))
            return [(Artist.from_row(r), r['role']) for r in cursor.fetchall()]

    def get_artist_songs(self, artist_id: int, role: Optional[str] = None) -> List[LibrarySong]:
        """Get all canonical songs associated with an artist."""
        with self._lock:
            cursor = self._conn.cursor()
            if role:
                cursor.execute("""
                    SELECT s.*
                    FROM songs s
                    JOIN song_artists sa ON s.id = sa.song_id
                    WHERE sa.artist_id = ? AND sa.role = ?
                    ORDER BY s.title ASC
                """, (artist_id, role))
            else:
                cursor.execute("""
                    SELECT DISTINCT s.*
                    FROM songs s
                    JOIN song_artists sa ON s.id = sa.song_id
                    WHERE sa.artist_id = ?
                    ORDER BY s.title ASC
                """, (artist_id,))
            return [LibrarySong.from_row(r) for r in cursor.fetchall()]

    def add_song_movie(self, song_id: int, movie_id: int, track_number: Optional[int] = None) -> bool:
        """Link a canonical song to a movie."""
        with self._lock:
            with self._conn:
                cursor = self._conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO song_movies (song_id, movie_id, track_number)
                    VALUES (?, ?, ?)
                """, (song_id, movie_id, track_number))
                return cursor.rowcount > 0

    def get_song_movies(self, song_id: int) -> List[Movie]:
        """Get all movies featuring this canonical song."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("""
                SELECT m.*
                FROM movies m
                JOIN song_movies sm ON m.id = sm.movie_id
                WHERE sm.song_id = ?
                ORDER BY m.year DESC
            """, (song_id,))
            return [Movie.from_row(r) for r in cursor.fetchall()]

    def get_movie_songs(self, movie_id: int) -> List[LibrarySong]:
        """Get all canonical songs belonging to a movie ordered by track number."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("""
                SELECT s.*
                FROM songs s
                JOIN song_movies sm ON s.id = sm.song_id
                WHERE sm.movie_id = ?
                ORDER BY COALESCE(sm.track_number, 999), s.title ASC
            """, (movie_id,))
            return [LibrarySong.from_row(r) for r in cursor.fetchall()]

    # ------------------------------------------------------------------
    # V5.1 User Song Metadata: Ratings, Favorites, Personal Notes
    # ------------------------------------------------------------------

    def set_user_metadata(self, meta: UserSongMetadata) -> bool:
        """Set or update user metadata for a canonical song."""
        if meta.rating is not None and not (1 <= meta.rating <= 5):
            raise ValueError(f"Rating must be between 1 and 5 (got {meta.rating})")
        with self._lock:
            with self._conn:
                cursor = self._conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO user_song_metadata (
                        song_id, rating, is_favorite, notes, tags,
                        favorited_at, last_rated_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    meta.song_id,
                    meta.rating,
                    1 if meta.is_favorite else 0,
                    meta.notes,
                    meta.tags,
                    meta.favorited_at.isoformat() if meta.favorited_at else None,
                    meta.last_rated_at.isoformat() if meta.last_rated_at else None,
                    (meta.created_at or datetime.now()).isoformat(),
                    datetime.now().isoformat(),
                ))
                return cursor.rowcount > 0

    def get_user_metadata(self, song_id: int) -> Optional[UserSongMetadata]:
        """Get user metadata for a song."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("SELECT * FROM user_song_metadata WHERE song_id = ?", (song_id,))
            row = cursor.fetchone()
            return UserSongMetadata.from_row(row) if row else None

    def set_song_rating(self, song_id: int, rating: Optional[int]) -> bool:
        """Set rating (1-5 or None to clear) for a song."""
        if rating is not None and not (1 <= rating <= 5):
            raise ValueError(f"Rating must be between 1 and 5 (got {rating})")
        with self._lock:
            with self._conn:
                cursor = self._conn.cursor()
                cursor.execute("""
                    INSERT INTO user_song_metadata (song_id, rating, last_rated_at, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(song_id) DO UPDATE SET
                        rating = excluded.rating,
                        last_rated_at = excluded.last_rated_at,
                        updated_at = excluded.updated_at
                """, (song_id, rating, datetime.now().isoformat(), datetime.now().isoformat()))
                return cursor.rowcount > 0

    def toggle_song_favorite(self, song_id: int) -> bool:
        """Toggle favorite status for a song and return new state."""
        with self._lock:
            with self._conn:
                cursor = self._conn.cursor()
                cursor.execute("SELECT is_favorite FROM user_song_metadata WHERE song_id = ?", (song_id,))
                row = cursor.fetchone()
                new_state = True
                if row:
                    new_state = not bool(row[0])
                fav_at = datetime.now().isoformat() if new_state else None
                cursor.execute("""
                    INSERT INTO user_song_metadata (song_id, is_favorite, favorited_at, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(song_id) DO UPDATE SET
                        is_favorite = excluded.is_favorite,
                        favorited_at = excluded.favorited_at,
                        updated_at = excluded.updated_at
                """, (song_id, 1 if new_state else 0, fav_at, datetime.now().isoformat()))
                return new_state

    def list_favorite_songs(self) -> List[LibrarySong]:
        """List all canonical songs flagged as favorite."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("""
                SELECT s.*
                FROM songs s
                JOIN user_song_metadata m ON s.id = m.song_id
                WHERE m.is_favorite = 1
                ORDER BY m.favorited_at DESC, s.title ASC
            """)
            return [LibrarySong.from_row(r) for r in cursor.fetchall()]

    # ------------------------------------------------------------------
    # V5.1 Playlists & Playlist Items
    # ------------------------------------------------------------------

    def create_playlist(self, playlist: Playlist) -> int:
        """Create a user playlist or return existing ID."""
        with self._lock:
            with self._conn:
                cursor = self._conn.cursor()
                cursor.execute("""
                    INSERT OR IGNORE INTO playlists (
                        name, description, cover_url, is_smart, smart_criteria_json,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    playlist.name,
                    playlist.description,
                    playlist.cover_url,
                    1 if playlist.is_smart else 0,
                    playlist.smart_criteria_json,
                    (playlist.created_at or datetime.now()).isoformat(),
                    (playlist.updated_at or datetime.now()).isoformat(),
                ))
                if cursor.rowcount > 0:
                    return cursor.lastrowid
                cursor.execute("SELECT id FROM playlists WHERE name = ?", (playlist.name,))
                row = cursor.fetchone()
                return row[0] if row else 0

    def get_playlist(self, playlist_id: int) -> Optional[Playlist]:
        """Get playlist by ID."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("SELECT * FROM playlists WHERE id = ?", (playlist_id,))
            row = cursor.fetchone()
            return Playlist.from_row(row) if row else None

    def list_playlists(self) -> List[Playlist]:
        """List all user playlists."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("SELECT * FROM playlists ORDER BY name ASC")
            return [Playlist.from_row(r) for r in cursor.fetchall()]

    def delete_playlist(self, playlist_id: int) -> bool:
        """Delete a playlist (cascades to playlist_items, preserves songs)."""
        with self._lock:
            with self._conn:
                cursor = self._conn.cursor()
                cursor.execute("DELETE FROM playlist_items WHERE playlist_id = ?", (playlist_id,))
                cursor.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))
                return cursor.rowcount > 0

    def add_playlist_item(self, playlist_id: int, song_id: int, position: Optional[int] = None) -> int:
        """Add a song to a playlist. Auto-assigns next position if not specified."""
        with self._lock:
            with self._conn:
                cursor = self._conn.cursor()
                if position is None:
                    cursor.execute("SELECT COALESCE(MAX(position), 0) + 1 FROM playlist_items WHERE playlist_id = ?", (playlist_id,))
                    position = cursor.fetchone()[0]
                cursor.execute("""
                    INSERT OR IGNORE INTO playlist_items (playlist_id, song_id, position, added_at)
                    VALUES (?, ?, ?, ?)
                """, (playlist_id, song_id, position, datetime.now().isoformat()))
                return cursor.lastrowid if cursor.rowcount > 0 else 0

    def remove_playlist_item(self, playlist_id: int, song_id: int) -> bool:
        """Remove a song from a playlist."""
        with self._lock:
            with self._conn:
                cursor = self._conn.cursor()
                cursor.execute("DELETE FROM playlist_items WHERE playlist_id = ? AND song_id = ?", (playlist_id, song_id))
                return cursor.rowcount > 0

    def get_playlist_songs(self, playlist_id: int) -> List[LibrarySong]:
        """Get songs in a playlist ordered by position."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("""
                SELECT s.*
                FROM songs s
                JOIN playlist_items pi ON s.id = pi.song_id
                WHERE pi.playlist_id = ?
                ORDER BY pi.position ASC
            """, (playlist_id,))
            return [LibrarySong.from_row(r) for r in cursor.fetchall()]

    # ------------------------------------------------------------------
    # V5.1 Curated Charts & Snapshots
    # ------------------------------------------------------------------

    def create_chart(self, chart: Chart) -> str:
        """Create a chart snapshot."""
        with self._lock:
            with self._conn:
                cursor = self._conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO charts (
                        id, title, chart_type, provider_name, snapshot_date, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    chart.id,
                    chart.title,
                    chart.chart_type,
                    chart.provider_name,
                    chart.snapshot_date.isoformat() if chart.snapshot_date else datetime.now().isoformat(),
                    (chart.created_at or datetime.now()).isoformat(),
                ))
                return chart.id

    def get_chart(self, chart_id: str) -> Optional[Chart]:
        """Get chart snapshot by ID."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("SELECT * FROM charts WHERE id = ?", (chart_id,))
            row = cursor.fetchone()
            return Chart.from_row(row) if row else None

    def list_charts(self, chart_type: Optional[str] = None) -> List[Chart]:
        """List charts ordered by snapshot_date descending."""
        with self._lock:
            cursor = self._conn.cursor()
            if chart_type:
                cursor.execute("SELECT * FROM charts WHERE chart_type = ? ORDER BY snapshot_date DESC", (chart_type,))
            else:
                cursor.execute("SELECT * FROM charts ORDER BY snapshot_date DESC")
            return [Chart.from_row(r) for r in cursor.fetchall()]

    def delete_chart(self, chart_id: str) -> bool:
        """Delete chart (cascades to chart_entries, preserves songs)."""
        with self._lock:
            with self._conn:
                cursor = self._conn.cursor()
                cursor.execute("DELETE FROM chart_entries WHERE chart_id = ?", (chart_id,))
                cursor.execute("DELETE FROM charts WHERE id = ?", (chart_id,))
                return cursor.rowcount > 0

    def add_chart_entry(self, entry: ChartEntry) -> int:
        """Add a ranked track entry to a chart."""
        with self._lock:
            with self._conn:
                cursor = self._conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO chart_entries (
                        chart_id, rank, previous_rank, song_id, raw_title, raw_artist, raw_movie
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    entry.chart_id,
                    entry.rank,
                    entry.previous_rank,
                    entry.song_id,
                    entry.raw_title,
                    entry.raw_artist,
                    entry.raw_movie,
                ))
                return cursor.lastrowid

    def get_chart_entries(self, chart_id: str) -> List[ChartEntry]:
        """Get all ranked entries for a chart ordered by rank ascending."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("""
                SELECT * FROM chart_entries
                WHERE chart_id = ?
                ORDER BY rank ASC
            """, (chart_id,))
            return [ChartEntry.from_row(r) for r in cursor.fetchall()]
