"""
SQLite database management for the library system.

Provides SQLiteDatabase class for all database operations including
song management, source tracking, download history, and discovery context.
"""

import logging
import os
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
from library.canonical import normalize_string, normalize_artist_name, compute_canonical_hash, clean_song_title

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

            # Sanitize legacy scraper titles and prune unowned zip stubs
            try:
                self.sanitize_existing_song_titles()
            except Exception as e:
                logger.warning(f"Could not sanitize legacy song titles: {e}")

            logger.info(f"Database connected: {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    def sanitize_existing_song_titles(self) -> int:
        """
        Sanitize legacy raw scraper strings (e.g. 'Download <song> 128kbps', '320kbps ZIP')
        in the songs table to canonical metadata, and prune unowned ZIP records.
        """
        cleaned_count = 0
        with self._lock:
            with self._conn:
                cursor = self._conn.cursor()
                # 1. Prune unowned ZIP archive dummy rows
                cursor.execute("""
                    DELETE FROM songs
                    WHERE (title LIKE '%ZIP%' OR title LIKE '%.zip%')
                      AND (state != 'OWNED' OR state IS NULL)
                      AND (file_path IS NULL OR file_path = '')
                """)

                # 2. Find songs with raw download / bitrate boilerplate in title
                cursor.execute("""
                    SELECT id, title, artist, album, year, duration_seconds, state, canonical_hash, file_path
                    FROM songs
                    WHERE title LIKE 'Download %'
                       OR title LIKE 'Listen to %'
                       OR title LIKE '%kbps%'
                       OR title LIKE '%\n%'
                """)
                rows = cursor.fetchall()
                for r in rows:
                    sid = r['id']
                    old_title = r['title']
                    clean_t = clean_song_title(old_title)
                    if clean_t and clean_t != old_title:
                        norm_t = normalize_string(clean_t)
                        new_hash = compute_canonical_hash(
                            clean_t, r['artist'] or '', r['album'] or '', r['year'], r['duration_seconds']
                        )
                        cursor.execute("SELECT id, state, file_path FROM songs WHERE canonical_hash = ? AND id != ?", (new_hash, sid))
                        existing = cursor.fetchone()
                        if existing:
                            target_id = existing['id']
                            cursor.execute("UPDATE OR IGNORE song_sources SET song_id = ? WHERE song_id = ?", (target_id, sid))
                            cursor.execute("UPDATE OR IGNORE song_movies SET song_id = ? WHERE song_id = ?", (target_id, sid))
                            cursor.execute("UPDATE OR IGNORE song_artists SET song_id = ? WHERE song_id = ?", (target_id, sid))
                            if r['state'] != 'OWNED' and not r['file_path']:
                                cursor.execute("DELETE FROM songs WHERE id = ?", (sid,))
                        else:
                            cursor.execute("""
                                UPDATE songs
                                SET title = ?, title_normalized = ?, canonical_hash = ?
                                WHERE id = ?
                            """, (clean_t, norm_t, new_hash, sid))
                        cleaned_count += 1
        return cleaned_count

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
                if not song.canonical_hash:
                    song.canonical_hash = compute_canonical_hash(
                        song.title or "",
                        song.artist or "",
                        song.album or "",
                        song.year,
                        song.duration_seconds
                    )
                if not song.title_normalized:
                    song.title_normalized = normalize_string(song.title or "")
                if not song.artist_normalized and song.artist:
                    song.artist_normalized = normalize_string(song.artist or "")
                if not song.album_normalized and song.album:
                    song.album_normalized = normalize_string(song.album or "")
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

    def list_songs(self, limit: Optional[int] = None, offset: int = 0) -> List[LibrarySong]:
        """List all songs in library with optional pagination."""
        with self._lock:
            cursor = self._conn.cursor()
            query = "SELECT * FROM songs ORDER BY id ASC"
            if limit:
                query += f" LIMIT {limit} OFFSET {offset}"
            cursor.execute(query)
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
        If file exists, verifies and synchronizes file_size_bytes against physical disk truth.

        Returns:
            Number of orphaned records reconciled
        """
        import os
        from pathlib import Path
        reconciled_count = 0
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("SELECT id, file_path, file_size_bytes FROM songs WHERE state = ?", (SongState.OWNED.value,))
            rows = cursor.fetchall()
            orphans = []
            updates = []
            for row in rows:
                song_id, fpath, db_size = row[0], row[1], row[2]
                target = Path(fpath) if fpath else None
                if target and not target.is_absolute():
                    if target.exists():
                        target = target.resolve()
                    else:
                        from config.settings import settings
                        out_dir = Path(settings.output_dir).resolve()
                        cand = (out_dir / target).resolve()
                        if cand.exists():
                            target = cand
                        else:
                            cand2 = (out_dir / target.name).resolve()
                            if cand2.exists():
                                target = cand2

                if not target or not target.is_file() or target.stat().st_size == 0:
                    orphans.append(song_id)
                else:
                    actual_size = target.stat().st_size
                    norm_path = str(target)
                    if db_size is None or db_size != actual_size or fpath != norm_path:
                        updates.append((norm_path, actual_size, song_id))

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
            if updates:
                with self._conn:
                    for norm_path, actual_size, song_id in updates:
                        cursor.execute("""
                            UPDATE songs SET
                                file_path = ?,
                                file_size_bytes = ?,
                                last_seen_at = ?
                            WHERE id = ?
                        """, (norm_path, actual_size, datetime.now().isoformat(), song_id))
            if clean_stale_jobs:
                self.clean_stale_transient_downloads()
        return reconciled_count

    def reconcile_artist_duplicates(self) -> int:
        """
        Detect and merge duplicate canonical artist rows resulting from punctuation/whitespace variants
        (e.g., 'A. R. Rahman', 'A.R. Rahman', 'A R Rahman' -> 'a r rahman').
        Re-points song_artists, movie_composers, and movie_actors to the canonical survivor artist
        and removes the duplicate rows.

        Returns:
            Number of duplicate artist records merged
        """
        merged_count = 0
        with self._lock:
            with self._conn:
                cursor = self._conn.cursor()
                # 1. Update all existing artists' name_normalized using normalize_artist_name
                cursor.execute("SELECT id, name, name_normalized FROM artists")
                rows = cursor.fetchall()
                for aid, aname, old_norm in rows:
                    new_norm = normalize_artist_name(aname)
                    if new_norm and new_norm != old_norm:
                        cursor.execute("UPDATE artists SET name_normalized = ? WHERE id = ?", (new_norm, aid))

                # 2. Find all normalized names that have duplicates
                cursor.execute("""
                    SELECT name_normalized, COUNT(*) as cnt
                    FROM artists
                    GROUP BY name_normalized
                    HAVING cnt > 1
                """)
                dup_groups = cursor.fetchall()

                for norm_name, _ in dup_groups:
                    cursor.execute("""
                        SELECT a.id, a.name,
                            (SELECT COUNT(*) FROM song_artists sa WHERE sa.artist_id = a.id) as s_cnt,
                            (SELECT COUNT(*) FROM movie_composers mc WHERE mc.composer_id = a.id) as mc_cnt,
                            (SELECT COUNT(*) FROM movie_actors ma WHERE ma.actor_id = a.id) as ma_cnt
                        FROM artists a
                        WHERE a.name_normalized = ?
                        ORDER BY (s_cnt + mc_cnt + ma_cnt) DESC, a.id ASC
                    """, (norm_name,))
                    candidates = cursor.fetchall()
                    if len(candidates) < 2:
                        continue

                    survivor_id = candidates[0][0]
                    dup_ids = [c[0] for c in candidates[1:]]

                    for dup_id in dup_ids:
                        # Re-point song_artists
                        cursor.execute("""
                            UPDATE OR IGNORE song_artists
                            SET artist_id = ?
                            WHERE artist_id = ?
                        """, (survivor_id, dup_id))
                        cursor.execute("DELETE FROM song_artists WHERE artist_id = ?", (dup_id,))

                        # Re-point movie_composers
                        cursor.execute("""
                            UPDATE OR IGNORE movie_composers
                            SET composer_id = ?
                            WHERE composer_id = ?
                        """, (survivor_id, dup_id))
                        cursor.execute("DELETE FROM movie_composers WHERE composer_id = ?", (dup_id,))

                        # Re-point movie_actors
                        cursor.execute("""
                            UPDATE OR IGNORE movie_actors
                            SET actor_id = ?
                            WHERE actor_id = ?
                        """, (survivor_id, dup_id))
                        cursor.execute("DELETE FROM movie_actors WHERE actor_id = ?", (dup_id,))

                        # Delete duplicate artist
                        cursor.execute("DELETE FROM artists WHERE id = ?", (dup_id,))
                        merged_count += 1
                        logger.info(f"Merged duplicate artist ID {dup_id} into canonical survivor ID {survivor_id} ({norm_name})")

        return merged_count

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
        """Add an artist to directory or return existing ID using canonical normalization."""
        if not artist.name_normalized:
            artist.name_normalized = normalize_artist_name(artist.name)
        with self._lock:
            with self._conn:
                cursor = self._conn.cursor()
                # Check canonical normalized existence first
                cursor.execute(
                    "SELECT id FROM artists WHERE name_normalized = ? OR name = ?",
                    (artist.name_normalized, artist.name)
                )
                row = cursor.fetchone()
                if row:
                    return row[0]

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
                cursor.execute(
                    "SELECT id FROM artists WHERE name_normalized = ? OR name = ?",
                    (artist.name_normalized, artist.name)
                )
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
        """Get artist by exact name or normalized name."""
        norm_name = normalize_artist_name(name)
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("SELECT * FROM artists WHERE name = ? OR name_normalized = ?", (name, norm_name))
            row = cursor.fetchone()
            return Artist.from_row(row) if row else None

    def get_artist_by_normalized_name(self, name_normalized: str) -> Optional[Artist]:
        """Get artist by normalized name."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("SELECT * FROM artists WHERE name_normalized = ?", (name_normalized,))
            row = cursor.fetchone()
            return Artist.from_row(row) if row else None

    def update_artist(self, artist_or_id: Any, **kwargs) -> bool:
        """
        Update artist details. Accepts either an Artist instance or an artist_id with keyword arguments.
        """
        with self._lock:
            with self._conn:
                cursor = self._conn.cursor()
                if isinstance(artist_or_id, Artist):
                    artist = artist_or_id
                    if not artist.id:
                        return False
                    norm = artist.name_normalized or normalize_string(artist.name)
                    cursor.execute("""
                        UPDATE artists SET
                            name = ?,
                            name_normalized = ?,
                            role = ?,
                            photo_url = ?,
                            local_photo_path = ?,
                            bio = ?,
                            updated_at = ?
                        WHERE id = ?
                    """, (
                        artist.name,
                        norm,
                        artist.role,
                        artist.photo_url,
                        artist.local_photo_path,
                        artist.bio,
                        datetime.now().isoformat(),
                        artist.id,
                    ))
                    return cursor.rowcount > 0
                else:
                    artist_id = int(artist_or_id)
                    allowed = ["name", "name_normalized", "role", "photo_url", "local_photo_path", "bio"]
                    sets = []
                    vals = []
                    for k, v in kwargs.items():
                        if k in allowed:
                            sets.append(f"{k} = ?")
                            vals.append(v)
                    if "name" in kwargs and "name_normalized" not in kwargs:
                        sets.append("name_normalized = ?")
                        vals.append(normalize_string(kwargs["name"]))
                    if not sets:
                        return False
                    sets.append("updated_at = ?")
                    vals.append(datetime.now().isoformat())
                    vals.append(artist_id)
                    sql = f"UPDATE artists SET {', '.join(sets)} WHERE id = ?"
                    cursor.execute(sql, tuple(vals))
                    return cursor.rowcount > 0

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
        """Delete an artist by ID (does not delete associated songs or movies)."""
        with self._lock:
            with self._conn:
                cursor = self._conn.cursor()
                cursor.execute("DELETE FROM movie_actors WHERE actor_id = ?", (artist_id,))
                cursor.execute("DELETE FROM movie_composers WHERE composer_id = ?", (artist_id,))
                cursor.execute("DELETE FROM song_artists WHERE artist_id = ?", (artist_id,))
                cursor.execute("DELETE FROM artists WHERE id = ?", (artist_id,))
                return cursor.rowcount > 0

    def get_artist_roles(self, artist_id: int) -> List[str]:
        """Determine all distinct roles for an artist across relationships."""
        with self._lock:
            cursor = self._conn.cursor()
            roles_set = set()

            # Check direct role in artists table
            cursor.execute("SELECT role FROM artists WHERE id = ?", (artist_id,))
            row = cursor.fetchone()
            if row and row['role']:
                base_r = row['role'].strip().lower()
                if base_r in ("music_director", "composer"):
                    roles_set.add("music_director")
                elif base_r in ("singer", "vocalist"):
                    roles_set.add("singer")
                elif base_r == "actor":
                    roles_set.add("actor")
                elif base_r != "artist":
                    roles_set.add(base_r)

            # Check song_artists
            cursor.execute("SELECT DISTINCT role FROM song_artists WHERE artist_id = ?", (artist_id,))
            for r in cursor.fetchall():
                sa_role = (r['role'] or "").strip().lower()
                if sa_role in ("singer", "artist", "vocalist", ""):
                    roles_set.add("singer")
                elif sa_role in ("composer", "music_director"):
                    roles_set.add("music_director")
                else:
                    roles_set.add(sa_role)

            # Check movie_composers
            cursor.execute("SELECT 1 FROM movie_composers WHERE composer_id = ? LIMIT 1", (artist_id,))
            if cursor.fetchone():
                roles_set.add("music_director")

            # Check movie_actors
            cursor.execute("SELECT 1 FROM movie_actors WHERE actor_id = ? LIMIT 1", (artist_id,))
            if cursor.fetchone():
                roles_set.add("actor")

            if not roles_set:
                roles_set.add("artist")

            order_pref = {"music_director": 1, "singer": 2, "actor": 3, "artist": 4}
            return sorted(list(roles_set), key=lambda x: (order_pref.get(x, 10), x))

    def search_and_filter_artists(
        self,
        query: str = "",
        role: Optional[str] = None,
        sort_by: str = "name",
        ascending: bool = True,
        limit: Optional[int] = None,
        offset: int = 0,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Search, filter, and paginate artists with aggregated soundtrack and download statistics.
        Avoids N+1 queries by aggregating counts in SQL.
        Supports both limit/offset and page/page_size pagination.
        """
        if page is not None and page_size is not None:
            actual_limit = page_size
            actual_offset = max(0, (page - 1) * page_size)
        else:
            actual_limit = limit if limit is not None else 24
            actual_offset = offset

        with self._lock:
            cursor = self._conn.cursor()

            conditions = []
            params = []

            # 1. Text Search Filter (name or normalized name)
            if query and query.strip():
                clean_q = query.strip()
                norm_q = normalize_artist_name(clean_q)
                conditions.append("(a.name LIKE ? OR a.name_normalized LIKE ?)")
                params.extend([f"%{clean_q}%", f"%{norm_q}%"])

            # 2. Role Filter
            if role and role.lower() not in ("all", ""):
                r_filter = role.lower().strip()
                if r_filter == "singer":
                    conditions.append("""(
                        a.id IN (SELECT artist_id FROM song_artists WHERE LOWER(role) IN ('singer', 'vocalist', ''))
                        OR LOWER(a.role) IN ('singer', 'vocalist')
                    )""")
                elif r_filter in ("music_director", "composer"):
                    conditions.append("""(
                        a.id IN (SELECT composer_id FROM movie_composers)
                        OR a.id IN (SELECT artist_id FROM song_artists WHERE LOWER(role) IN ('composer', 'music_director'))
                        OR LOWER(a.role) IN ('music_director', 'composer')
                    )""")
                elif r_filter == "actor":
                    conditions.append("""(
                        a.id IN (SELECT actor_id FROM movie_actors)
                        OR LOWER(a.role) = 'actor'
                    )""")

            where_str = f"WHERE {' AND '.join(conditions)}" if conditions else ""

            # 3. Total Matching Artists Count
            count_sql = f"SELECT COUNT(DISTINCT a.id) FROM artists a {where_str}"
            cursor.execute(count_sql, tuple(params))
            total_count = cursor.fetchone()[0]

            # 4. Sorting
            direction = "ASC" if ascending else "DESC"
            sort_map = {
                "name": f"a.name COLLATE NOCASE {direction}",
                "songs": f"total_songs {direction}, a.name ASC",
                "movies": f"total_movies {direction}, a.name ASC",
                "downloaded": f"downloaded_songs {direction}, a.name ASC",
                "recent": f"a.created_at {direction}",
            }
            order_by = sort_map.get(sort_by, f"a.name COLLATE NOCASE {direction}")

            # 5. Query Artists with SQL Subquery Aggregation
            query_sql = f"""
                SELECT
                    a.id,
                    a.name,
                    a.name_normalized,
                    a.role as base_role,
                    a.photo_url,
                    a.local_photo_path,
                    a.bio,
                    (
                        SELECT COUNT(DISTINCT s_sub.id)
                        FROM songs s_sub
                        WHERE s_sub.title NOT LIKE '%ZIP%' AND s_sub.title NOT LIKE '%.zip%' AND (
                            s_sub.id IN (
                                SELECT sa.song_id FROM song_artists sa WHERE sa.artist_id = a.id
                                UNION
                                SELECT sm.song_id FROM movie_composers mc
                                JOIN song_movies sm ON mc.movie_id = sm.movie_id
                                WHERE mc.composer_id = a.id
                            )
                            OR s_sub.artist LIKE '%' || a.name || '%'
                            OR (a.name_normalized != '' AND s_sub.artist_normalized LIKE '%' || a.name_normalized || '%')
                        )
                    ) as total_songs,
                    (
                        SELECT COUNT(DISTINCT s_sub.id)
                        FROM songs s_sub
                        WHERE (s_sub.state = 'OWNED' OR (s_sub.file_path IS NOT NULL AND s_sub.file_path != ''))
                        AND s_sub.title NOT LIKE '%ZIP%' AND s_sub.title NOT LIKE '%.zip%' AND (
                            s_sub.id IN (
                                SELECT sa.song_id FROM song_artists sa WHERE sa.artist_id = a.id
                                UNION
                                SELECT sm.song_id FROM movie_composers mc
                                JOIN song_movies sm ON mc.movie_id = sm.movie_id
                                WHERE mc.composer_id = a.id
                            )
                            OR s_sub.artist LIKE '%' || a.name || '%'
                            OR (a.name_normalized != '' AND s_sub.artist_normalized LIKE '%' || a.name_normalized || '%')
                        )
                    ) as downloaded_songs,
                    (
                        SELECT COUNT(DISTINCT m_sub_id)
                        FROM (
                            SELECT movie_id as m_sub_id FROM movie_actors WHERE actor_id = a.id
                            UNION
                            SELECT movie_id as m_sub_id FROM movie_composers WHERE composer_id = a.id
                        )
                    ) as total_movies
                FROM artists a
                {where_str}
                ORDER BY {order_by}
                LIMIT ? OFFSET ?
            """
            cursor.execute(query_sql, tuple(params + [actual_limit, actual_offset]))

            results = []
            for row in cursor.fetchall():
                a_id = row['id']
                tot_s = row['total_songs'] or 0
                dl_s = row['downloaded_songs'] or 0
                miss_s = max(0, tot_s - dl_s)
                tot_m = row['total_movies'] or 0
                roles = self.get_artist_roles(a_id)

                results.append({
                    "id": a_id,
                    "name": row['name'],
                    "name_normalized": row['name_normalized'],
                    "role": row['base_role'],
                    "roles": roles,
                    "roles_display": " • ".join(
                        r.replace("_", " ").title() for r in roles
                    ) if roles else "Artist",
                    "photo_url": row['photo_url'],
                    "local_photo_path": row['local_photo_path'],
                    "bio": row['bio'],
                    "total_songs": tot_s,
                    "total_tracks": tot_s,
                    "downloaded_songs": dl_s,
                    "downloaded_tracks": dl_s,
                    "missing_songs": miss_s,
                    "missing_tracks": miss_s,
                    "total_movies": tot_m,
                    "total_soundtracks": tot_m,
                    "is_complete": (tot_s > 0 and dl_s >= tot_s),
                })

            return results, total_count

    def get_artist_statistics(self, artist_id: int) -> Dict[str, Any]:
        """Get verified statistics for an artist."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("""
                SELECT
                    (
                        SELECT COUNT(DISTINCT s_sub.id)
                        FROM songs s_sub
                        WHERE s_sub.title NOT LIKE '%ZIP%' AND s_sub.title NOT LIKE '%.zip%' AND (
                            s_sub.id IN (
                                SELECT sa.song_id FROM song_artists sa WHERE sa.artist_id = ?
                                UNION
                                SELECT sm.song_id FROM movie_composers mc
                                JOIN song_movies sm ON mc.movie_id = sm.movie_id
                                WHERE mc.composer_id = ?
                            )
                            OR s_sub.artist LIKE '%' || (SELECT name FROM artists WHERE id = ?) || '%'
                            OR (s_sub.artist_normalized != '' AND s_sub.artist_normalized LIKE '%' || (SELECT name_normalized FROM artists WHERE id = ?) || '%')
                        )
                    ) as total_songs,
                    (
                        SELECT COUNT(DISTINCT s_sub.id)
                        FROM songs s_sub
                        WHERE (s_sub.state = 'OWNED' OR (s_sub.file_path IS NOT NULL AND s_sub.file_path != ''))
                        AND s_sub.title NOT LIKE '%ZIP%' AND s_sub.title NOT LIKE '%.zip%' AND (
                            s_sub.id IN (
                                SELECT sa.song_id FROM song_artists sa WHERE sa.artist_id = ?
                                UNION
                                SELECT sm.song_id FROM movie_composers mc
                                JOIN song_movies sm ON mc.movie_id = sm.movie_id
                                WHERE mc.composer_id = ?
                            )
                            OR s_sub.artist LIKE '%' || (SELECT name FROM artists WHERE id = ?) || '%'
                            OR (s_sub.artist_normalized != '' AND s_sub.artist_normalized LIKE '%' || (SELECT name_normalized FROM artists WHERE id = ?) || '%')
                        )
                    ) as downloaded_songs,
                    (
                        SELECT COUNT(DISTINCT m_sub_id)
                        FROM (
                            SELECT movie_id as m_sub_id FROM movie_actors WHERE actor_id = ?
                            UNION
                            SELECT movie_id as m_sub_id FROM movie_composers WHERE composer_id = ?
                        )
                    ) as total_movies
                FROM artists a
                WHERE a.id = ?
            """, (artist_id, artist_id, artist_id, artist_id, artist_id, artist_id, artist_id, artist_id, artist_id, artist_id, artist_id))
            row = cursor.fetchone()
            tot_s = (row['total_songs'] if row else 0) or 0
            dl_s = (row['downloaded_songs'] if row else 0) or 0
            miss_s = max(0, tot_s - dl_s)
            tot_m = (row['total_movies'] if row else 0) or 0
            roles = self.get_artist_roles(artist_id)
            return {
                "total": tot_s,
                "total_songs": tot_s,
                "total_tracks": tot_s,
                "downloaded": dl_s,
                "downloaded_songs": dl_s,
                "downloaded_tracks": dl_s,
                "missing": miss_s,
                "missing_tracks": miss_s,
                "movies_count": tot_m,
                "total_movies": tot_m,
                "roles": roles,
            }

    def get_artist_songs_detailed(self, artist_id: int, role: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get detailed song list for an artist with download status."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("""
                SELECT
                    s.id as song_id,
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
                        SELECT m.title
                        FROM song_movies sm
                        JOIN movies m ON sm.movie_id = m.id
                        WHERE sm.song_id = s.id
                        LIMIT 1
                    ) as movie_title,
                    (
                        SELECT m.id
                        FROM song_movies sm
                        JOIN movies m ON sm.movie_id = m.id
                        WHERE sm.song_id = s.id
                        LIMIT 1
                    ) as movie_id,
                    (
                        SELECT src.source_name
                        FROM song_sources src
                        WHERE src.song_id = s.id
                        ORDER BY src.quality_kbps DESC, src.reliability_score DESC
                        LIMIT 1
                    ) as primary_source
                FROM songs s
                WHERE s.title NOT LIKE '%ZIP%' AND s.title NOT LIKE '%.zip%' AND (
                    s.id IN (
                        SELECT song_id FROM song_artists WHERE artist_id = ?
                        UNION
                        SELECT sm.song_id FROM movie_composers mc
                        JOIN song_movies sm ON mc.movie_id = sm.movie_id
                        WHERE mc.composer_id = ?
                    )
                    OR s.artist LIKE '%' || (SELECT name FROM artists WHERE id = ?) || '%'
                    OR (s.artist_normalized != '' AND s.artist_normalized LIKE '%' || (SELECT name_normalized FROM artists WHERE id = ?) || '%')
                )
                ORDER BY s.title ASC
            """, (artist_id, artist_id, artist_id, artist_id))
            results = []
            for r in cursor.fetchall():
                is_dl = (r['state'] == 'OWNED' or bool(r['file_path']))
                movie_name = r['movie_title'] or r['album'] or "Soundtrack"
                results.append({
                    "id": r['song_id'],
                    "song_id": r['song_id'],
                    "title": clean_song_title(r['title']),
                    "artist": r['artist'] or "Unknown Artist",
                    "album": movie_name,
                    "movie_title": movie_name,
                    "movie_id": r['movie_id'],
                    "year": r['year'],
                    "duration_seconds": r['duration_seconds'],
                    "state": "OWNED" if is_dl else r['state'],
                    "is_downloaded": is_dl,
                    "download_status_display": "✓ Downloaded" if is_dl else "Not Downloaded",
                    "quality_kbps": r['quality_kbps'],
                    "quality": r['quality_kbps'],
                    "quality_display": f"{r['quality_kbps']} kbps" if r['quality_kbps'] else "320 kbps",
                    "file_path": r['file_path'],
                    "source": r['primary_source'] or "Regional",
                })
            return results

    def get_artist_movies_detailed(self, artist_id: int) -> List[Dict[str, Any]]:
        """Get detailed list of movies associated with an artist (actor or composer)."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("""
                SELECT
                    m.id as movie_id,
                    m.title,
                    m.year,
                    m.director,
                    m.poster_url,
                    m.banner_url,
                    m.track_count as stored_track_count,
                    COUNT(DISTINCT sm.song_id) as total_songs,
                    COUNT(DISTINCT CASE WHEN s.state = 'OWNED' THEN sm.song_id END) as downloaded_songs,
                    ma.character_name,
                    CASE
                        WHEN mc.movie_id IS NOT NULL AND ma.movie_id IS NOT NULL THEN 'Composer & Actor'
                        WHEN mc.movie_id IS NOT NULL THEN 'Music Director'
                        ELSE 'Actor'
                    END as credit_role
                FROM movies m
                LEFT JOIN movie_actors ma ON m.id = ma.movie_id AND ma.actor_id = ?
                LEFT JOIN movie_composers mc ON m.id = mc.movie_id AND mc.composer_id = ?
                LEFT JOIN song_movies sm ON m.id = sm.movie_id
                LEFT JOIN songs s ON sm.song_id = s.id
                WHERE ma.actor_id = ? OR mc.composer_id = ?
                GROUP BY m.id
                ORDER BY COALESCE(m.year, 0) DESC, m.title ASC
            """, (artist_id, artist_id, artist_id, artist_id))
            results = []
            for r in cursor.fetchall():
                tot = max(r['total_songs'] or 0, r['stored_track_count'] or 0)
                dl = r['downloaded_songs'] or 0
                miss = max(0, tot - dl)
                results.append({
                    "movie_id": r['movie_id'],
                    "title": r['title'],
                    "year": r['year'],
                    "director": r['director'],
                    "poster_url": r['poster_url'],
                    "banner_url": r['banner_url'],
                    "character_name": r['character_name'],
                    "credit_role": r['credit_role'],
                    "total_songs": tot,
                    "downloaded_songs": dl,
                    "missing_songs": miss,
                    "is_complete": (tot > 0 and dl >= tot),
                })
            return results

    # ------------------------------------------------------------------
    # V5.1 Relational Join Tables: Movie Actors & Composers
    # ------------------------------------------------------------------

    def add_movie_actor(self, movie_id: Any = None, actor_id: Optional[int] = None, character_name: Optional[str] = None, **kwargs) -> bool:
        """Link an actor to a movie. Accepts MovieActor object, positional, or keyword parameters."""
        if hasattr(movie_id, 'movie_id') and hasattr(movie_id, 'actor_id'):
            m_id = movie_id.movie_id
            a_id = movie_id.actor_id
            c_name = getattr(movie_id, 'character_name', None)
        else:
            m_id = int(movie_id if movie_id is not None else kwargs.get('movie_id', 0))
            a_id = int(actor_id if actor_id is not None else kwargs.get('actor_id', 0))
            c_name = character_name if character_name is not None else kwargs.get('character_name')

        with self._lock:
            with self._conn:
                cursor = self._conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO movie_actors (movie_id, actor_id, character_name)
                    VALUES (?, ?, ?)
                """, (m_id, a_id, c_name))
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

    def add_movie_composer(self, movie_id: Any = None, composer_id: Optional[int] = None, **kwargs) -> bool:
        """Link a music director/composer to a movie. Accepts MovieComposer object, positional, or keyword parameters."""
        if hasattr(movie_id, 'movie_id') and hasattr(movie_id, 'composer_id'):
            m_id = movie_id.movie_id
            c_id = movie_id.composer_id
        else:
            m_id = int(movie_id if movie_id is not None else kwargs.get('movie_id', 0))
            c_id = int(composer_id if composer_id is not None else kwargs.get('composer_id', 0))

        with self._lock:
            with self._conn:
                cursor = self._conn.cursor()
                cursor.execute("""
                    INSERT OR IGNORE INTO movie_composers (movie_id, composer_id)
                    VALUES (?, ?)
                """, (m_id, c_id))
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

    def add_song_artist(self, song_id: Any = None, artist_id: Optional[int] = None, role: str = "singer", **kwargs) -> bool:
        """Link a canonical song to an artist with a role. Accepts SongArtist object, positional, or keyword parameters."""
        if hasattr(song_id, 'song_id') and hasattr(song_id, 'artist_id'):
            s_id = song_id.song_id
            a_id = song_id.artist_id
            r = getattr(song_id, 'role', role) or role
        else:
            s_id = int(song_id if song_id is not None else kwargs.get('song_id', 0))
            a_id = int(artist_id if artist_id is not None else kwargs.get('artist_id', 0))
            r = role if role != "singer" else kwargs.get('role', "singer")

        with self._lock:
            with self._conn:
                cursor = self._conn.cursor()
                cursor.execute("""
                    INSERT OR IGNORE INTO song_artists (song_id, artist_id, role)
                    VALUES (?, ?, ?)
                """, (s_id, a_id, r))
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

    def add_song_movie(self, song_id: Any = None, movie_id: Optional[int] = None, track_number: Optional[int] = None, **kwargs) -> bool:
        """Link a canonical song to a movie. Accepts SongMovie object, positional, or keyword parameters."""
        if hasattr(song_id, 'song_id') and hasattr(song_id, 'movie_id'):
            s_id = song_id.song_id
            m_id = song_id.movie_id
            t_num = getattr(song_id, 'track_number', None) or getattr(song_id, 'track_no', None)
        else:
            s_id = int(song_id if song_id is not None else kwargs.get('song_id', 0))
            m_id = int(movie_id if movie_id is not None else kwargs.get('movie_id', 0))
            t_num = track_number if track_number is not None else kwargs.get('track_number', kwargs.get('track_no'))

        with self._lock:
            with self._conn:
                cursor = self._conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO song_movies (song_id, movie_id, track_number)
                    VALUES (?, ?, ?)
                """, (s_id, m_id, t_num))
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

    def update_playlist(self, playlist_id: int, name: Optional[str] = None, description: Optional[str] = None) -> bool:
        """Update playlist name and/or description."""
        updates = []
        params = []
        if name is not None and name.strip():
            updates.append("name = ?")
            params.append(name.strip())
        if description is not None:
            updates.append("description = ?")
            params.append(description.strip())
        if not updates:
            return False
        updates.append("updated_at = ?")
        params.append(datetime.now().isoformat())
        params.append(playlist_id)
        with self._lock:
            with self._conn:
                cursor = self._conn.cursor()
                cursor.execute(f"UPDATE playlists SET {', '.join(updates)} WHERE id = ?", params)
                return cursor.rowcount > 0

    def reorder_playlist_items(self, playlist_id: int, ordered_song_ids: List[int]) -> bool:
        """Update positions of songs in a playlist based on list order."""
        with self._lock:
            with self._conn:
                cursor = self._conn.cursor()
                for pos, s_id in enumerate(ordered_song_ids, start=1):
                    cursor.execute(
                        "UPDATE playlist_items SET position = ? WHERE playlist_id = ? AND song_id = ?",
                        (pos, playlist_id, s_id),
                    )
                return True

    def move_playlist_item(self, playlist_id: int, song_id: int, direction: str) -> bool:
        """Swap position of a song with adjacent item ('up' or 'down')."""
        with self._lock:
            with self._conn:
                cursor = self._conn.cursor()
                cursor.execute("SELECT position FROM playlist_items WHERE playlist_id = ? AND song_id = ?", (playlist_id, song_id))
                row = cursor.fetchone()
                if not row:
                    return False
                current_pos = row[0]
                if direction == "up":
                    cursor.execute(
                        "SELECT song_id, position FROM playlist_items WHERE playlist_id = ? AND position < ? ORDER BY position DESC LIMIT 1",
                        (playlist_id, current_pos),
                    )
                elif direction == "down":
                    cursor.execute(
                        "SELECT song_id, position FROM playlist_items WHERE playlist_id = ? AND position > ? ORDER BY position ASC LIMIT 1",
                        (playlist_id, current_pos),
                    )
                else:
                    return False
                adj = cursor.fetchone()
                if not adj:
                    return False
                adj_song_id, adj_pos = adj[0], adj[1]
                # Swap positions
                cursor.execute("UPDATE playlist_items SET position = ? WHERE playlist_id = ? AND song_id = ?", (adj_pos, playlist_id, song_id))
                cursor.execute("UPDATE playlist_items SET position = ? WHERE playlist_id = ? AND song_id = ?", (current_pos, playlist_id, adj_song_id))
                return True

    def search_and_filter_playlists(
        self,
        query: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Search playlists with calculated track and download metrics."""
        with self._lock:
            cursor = self._conn.cursor()
            where_clauses = []
            params = []
            if query and query.strip():
                q = f"%{query.strip().lower()}%"
                where_clauses.append("(LOWER(p.name) LIKE ? OR LOWER(COALESCE(p.description, '')) LIKE ?)")
                params.extend([q, q])

            where_str = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

            count_sql = f"SELECT COUNT(*) FROM playlists p {where_str}"
            cursor.execute(count_sql, params)
            total = cursor.fetchone()[0]

            sql = f"""
                SELECT
                    p.id,
                    p.name,
                    p.description,
                    p.cover_url,
                    p.is_smart,
                    p.created_at,
                    p.updated_at,
                    (SELECT COUNT(*) FROM playlist_items pi WHERE pi.playlist_id = p.id) AS total_songs,
                    (SELECT COUNT(*) FROM playlist_items pi
                     JOIN songs s ON pi.song_id = s.id
                     WHERE pi.playlist_id = p.id AND s.state = 'OWNED') AS downloaded_songs
                FROM playlists p
                {where_str}
                ORDER BY p.updated_at DESC, p.name ASC
                LIMIT ? OFFSET ?
            """
            cursor.execute(sql, params + [limit, offset])
            rows = cursor.fetchall()
            results = []
            for r in rows:
                tot = r[7]
                dl = r[8]
                results.append({
                    "id": r[0],
                    "name": r[1],
                    "description": r[2],
                    "cover_url": r[3],
                    "is_smart": bool(r[4]),
                    "created_at": r[5],
                    "updated_at": r[6],
                    "total_songs": tot,
                    "downloaded_songs": dl,
                    "missing_songs": max(0, tot - dl),
                })
            return results, total

    def get_playlist_statistics(self, playlist_id: int) -> Dict[str, int]:
        """Return authoritative playlist track and download metrics with disk verification."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("""
                SELECT s.state, s.file_path
                FROM playlist_items pi
                JOIN songs s ON pi.song_id = s.id
                WHERE pi.playlist_id = ?
            """, (playlist_id,))
            rows = cursor.fetchall()
            total = len(rows)
            downloaded = 0
            for state, f_path in rows:
                if state == SongState.OWNED.value and f_path and os.path.isfile(f_path):
                    downloaded += 1
            return {
                "total_songs": total,
                "downloaded_songs": downloaded,
                "missing_songs": max(0, total - downloaded),
            }

    def get_playlist_items_detailed(
        self,
        playlist_id: int,
        query: str = "",
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Fetch playlist items ordered by position with metadata, artist/movie links, and user rating/favorite status."""
        with self._lock:
            cursor = self._conn.cursor()
            where_clauses = ["pi.playlist_id = ?"]
            params = [playlist_id]

            if query and query.strip():
                q = f"%{query.strip().lower()}%"
                where_clauses.append("(LOWER(s.title) LIKE ? OR LOWER(COALESCE(s.artist, '')) LIKE ? OR LOWER(COALESCE(s.album, '')) LIKE ?)")
                params.extend([q, q, q])

            where_str = "WHERE " + " AND ".join(where_clauses)

            count_sql = f"""
                SELECT COUNT(*)
                FROM playlist_items pi
                JOIN songs s ON pi.song_id = s.id
                {where_str}
            """
            cursor.execute(count_sql, params)
            total = cursor.fetchone()[0]

            sql = f"""
                SELECT
                    pi.position,
                    pi.added_at,
                    s.id AS song_id,
                    s.title,
                    s.artist,
                    s.album,
                    s.year,
                    s.duration_seconds,
                    s.state,
                    s.file_path,
                    s.quality_kbps,
                    (SELECT a.id FROM artists a
                     JOIN song_artists sa ON a.id = sa.artist_id
                     WHERE sa.song_id = s.id LIMIT 1) AS artist_id,
                    (SELECT m.id FROM movies m
                     JOIN song_movies sm ON m.id = sm.movie_id
                     WHERE sm.song_id = s.id LIMIT 1) AS movie_id,
                    m.rating,
                    m.is_favorite
                FROM playlist_items pi
                JOIN songs s ON pi.song_id = s.id
                LEFT JOIN user_song_metadata m ON s.id = m.song_id
                {where_str}
                ORDER BY pi.position ASC
                LIMIT ? OFFSET ?
            """
            cursor.execute(sql, params + [limit, offset])
            rows = cursor.fetchall()
            items = []
            for r in rows:
                pos, added_at, s_id, title, artist, album, year, dur, state, f_path, q_kbps, a_id, m_id, rating, is_fav = r
                is_dl = (state == SongState.OWNED.value and f_path and os.path.isfile(f_path))
                items.append({
                    "position": pos,
                    "added_at": added_at,
                    "song_id": s_id,
                    "title": title,
                    "artist": artist or "Unknown Artist",
                    "album": album or "Unknown Album",
                    "year": year,
                    "duration_seconds": dur,
                    "is_downloaded": bool(is_dl),
                    "file_path": f_path if is_dl else None,
                    "quality_kbps": q_kbps,
                    "artist_id": a_id,
                    "movie_id": m_id,
                    "rating": rating,
                    "is_favorite": bool(is_fav),
                })
            return items, total

    def search_and_filter_favorites(
        self,
        query: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Search and filter favorite songs with user ratings and download states."""
        with self._lock:
            cursor = self._conn.cursor()
            where_clauses = ["m.is_favorite = 1"]
            params = []
            if query and query.strip():
                q = f"%{query.strip().lower()}%"
                where_clauses.append("(LOWER(s.title) LIKE ? OR LOWER(COALESCE(s.artist, '')) LIKE ? OR LOWER(COALESCE(s.album, '')) LIKE ?)")
                params.extend([q, q, q])

            where_str = "WHERE " + " AND ".join(where_clauses)
            count_sql = f"""
                SELECT COUNT(*)
                FROM songs s
                JOIN user_song_metadata m ON s.id = m.song_id
                {where_str}
            """
            cursor.execute(count_sql, params)
            total = cursor.fetchone()[0]

            sql = f"""
                SELECT
                    s.id, s.title, s.artist, s.album, s.year, s.duration_seconds,
                    s.state, s.file_path, s.quality_kbps,
                    m.rating, m.is_favorite, m.favorited_at,
                    (SELECT a.id FROM artists a JOIN song_artists sa ON a.id = sa.artist_id WHERE sa.song_id = s.id LIMIT 1) AS artist_id,
                    (SELECT mv.id FROM movies mv JOIN song_movies sm ON mv.id = sm.movie_id WHERE sm.song_id = s.id LIMIT 1) AS movie_id
                FROM songs s
                JOIN user_song_metadata m ON s.id = m.song_id
                {where_str}
                ORDER BY m.favorited_at DESC, s.title ASC
                LIMIT ? OFFSET ?
            """
            cursor.execute(sql, params + [limit, offset])
            items = []
            for r in cursor.fetchall():
                s_id, title, artist, album, year, dur, state, f_path, q_kbps, rating, is_fav, fav_at, a_id, m_id = r
                is_dl = (state == SongState.OWNED.value and f_path and os.path.isfile(f_path))
                items.append({
                    "song_id": s_id,
                    "title": title,
                    "artist": artist or "Unknown Artist",
                    "album": album or "Unknown Album",
                    "year": year,
                    "duration_seconds": dur,
                    "is_downloaded": bool(is_dl),
                    "file_path": f_path if is_dl else None,
                    "quality_kbps": q_kbps,
                    "rating": rating,
                    "is_favorite": bool(is_fav),
                    "favorited_at": fav_at,
                    "artist_id": a_id,
                    "movie_id": m_id,
                })
            return items, total

    def search_and_filter_rated_songs(
        self,
        min_rating: int = 1,
        query: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Search and filter rated songs ordered by rating descending."""
        with self._lock:
            cursor = self._conn.cursor()
            where_clauses = ["m.rating IS NOT NULL", "m.rating >= ?"]
            params = [min_rating]
            if query and query.strip():
                q = f"%{query.strip().lower()}%"
                where_clauses.append("(LOWER(s.title) LIKE ? OR LOWER(COALESCE(s.artist, '')) LIKE ? OR LOWER(COALESCE(s.album, '')) LIKE ?)")
                params.extend([q, q, q])

            where_str = "WHERE " + " AND ".join(where_clauses)
            count_sql = f"""
                SELECT COUNT(*)
                FROM songs s
                JOIN user_song_metadata m ON s.id = m.song_id
                {where_str}
            """
            cursor.execute(count_sql, params)
            total = cursor.fetchone()[0]

            sql = f"""
                SELECT
                    s.id, s.title, s.artist, s.album, s.year, s.duration_seconds,
                    s.state, s.file_path, s.quality_kbps,
                    m.rating, m.is_favorite, m.last_rated_at,
                    (SELECT a.id FROM artists a JOIN song_artists sa ON a.id = sa.artist_id WHERE sa.song_id = s.id LIMIT 1) AS artist_id,
                    (SELECT mv.id FROM movies mv JOIN song_movies sm ON mv.id = sm.movie_id WHERE sm.song_id = s.id LIMIT 1) AS movie_id
                FROM songs s
                JOIN user_song_metadata m ON s.id = m.song_id
                {where_str}
                ORDER BY m.rating DESC, m.last_rated_at DESC, s.title ASC
                LIMIT ? OFFSET ?
            """
            cursor.execute(sql, params + [limit, offset])
            items = []
            for r in cursor.fetchall():
                s_id, title, artist, album, year, dur, state, f_path, q_kbps, rating, is_fav, rated_at, a_id, m_id = r
                is_dl = (state == SongState.OWNED.value and f_path and os.path.isfile(f_path))
                items.append({
                    "song_id": s_id,
                    "title": title,
                    "artist": artist or "Unknown Artist",
                    "album": album or "Unknown Album",
                    "year": year,
                    "duration_seconds": dur,
                    "is_downloaded": bool(is_dl),
                    "file_path": f_path if is_dl else None,
                    "quality_kbps": q_kbps,
                    "rating": rating,
                    "is_favorite": bool(is_fav),
                    "last_rated_at": rated_at,
                    "artist_id": a_id,
                    "movie_id": m_id,
                })
            return items, total

    # ------------------------------------------------------------------
    # V5.1 Curated Charts & Snapshots
    # ------------------------------------------------------------------

    def create_chart(self, chart: Any) -> str:
        """Create a chart snapshot."""
        if isinstance(chart, dict):
            c_id = chart["id"]
            title = chart["title"]
            c_type = chart.get("chart_type", "top_100")
            p_name = chart.get("provider_name", "curated")
            snap = chart.get("snapshot_date")
            created = chart.get("created_at")
        else:
            c_id = chart.id
            title = chart.title
            c_type = chart.chart_type
            p_name = chart.provider_name
            snap = chart.snapshot_date
            created = chart.created_at

        snap_str = snap.isoformat() if isinstance(snap, datetime) else (str(snap) if snap else datetime.now().isoformat())
        created_str = created.isoformat() if isinstance(created, datetime) else (str(created) if created else datetime.now().isoformat())

        with self._lock:
            with self._conn:
                cursor = self._conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO charts (
                        id, title, chart_type, provider_name, snapshot_date, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    c_id,
                    title,
                    c_type,
                    p_name,
                    snap_str,
                    created_str,
                ))
                return c_id

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

    def update_chart(
        self,
        chart_id: str,
        title: Optional[str] = None,
        chart_type: Optional[str] = None,
        provider_name: Optional[str] = None,
        snapshot_date: Optional[Any] = None,
    ) -> bool:
        """Update an existing chart record."""
        updates = []
        params = []
        if title is not None:
            updates.append("title = ?")
            params.append(title)
        if chart_type is not None:
            updates.append("chart_type = ?")
            params.append(chart_type)
        if provider_name is not None:
            updates.append("provider_name = ?")
            params.append(provider_name)
        if snapshot_date is not None:
            snap_str = snapshot_date.isoformat() if isinstance(snapshot_date, datetime) else str(snapshot_date)
            updates.append("snapshot_date = ?")
            params.append(snap_str)

        if not updates:
            return False

        params.append(chart_id)
        with self._lock:
            with self._conn:
                cursor = self._conn.cursor()
                cursor.execute(f"UPDATE charts SET {', '.join(updates)} WHERE id = ?", params)
                return cursor.rowcount > 0

    def delete_chart(self, chart_id: str) -> bool:
        """Delete chart (cascades to chart_entries, preserves songs)."""
        with self._lock:
            with self._conn:
                cursor = self._conn.cursor()
                cursor.execute("DELETE FROM chart_entries WHERE chart_id = ?", (chart_id,))
                cursor.execute("DELETE FROM charts WHERE id = ?", (chart_id,))
                return cursor.rowcount > 0

    def add_chart_entry(self, entry: Any = None, **kwargs) -> int:
        """Add a ranked track entry to a chart."""
        if entry is not None and not kwargs:
            if isinstance(entry, ChartEntry):
                c_id = entry.chart_id
                rank = entry.rank
                prev_rank = entry.previous_rank
                s_id = entry.song_id
                r_title = entry.raw_title
                r_artist = entry.raw_artist
                r_movie = entry.raw_movie
            elif isinstance(entry, dict):
                c_id = entry["chart_id"]
                rank = entry["rank"]
                prev_rank = entry.get("previous_rank")
                s_id = entry.get("song_id")
                r_title = entry["raw_title"]
                r_artist = entry.get("raw_artist")
                r_movie = entry.get("raw_movie")
            else:
                c_id = getattr(entry, "chart_id", "")
                rank = getattr(entry, "rank", 0)
                prev_rank = getattr(entry, "previous_rank", None)
                s_id = getattr(entry, "song_id", None)
                r_title = getattr(entry, "raw_title", "")
                r_artist = getattr(entry, "raw_artist", None)
                r_movie = getattr(entry, "raw_movie", None)
        else:
            c_id = kwargs.get("chart_id", "")
            rank = kwargs.get("rank", 0)
            prev_rank = kwargs.get("previous_rank")
            s_id = kwargs.get("song_id")
            r_title = kwargs.get("raw_title", "")
            r_artist = kwargs.get("raw_artist")
            r_movie = kwargs.get("raw_movie")

        with self._lock:
            with self._conn:
                cursor = self._conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO chart_entries (
                        chart_id, rank, previous_rank, song_id, raw_title, raw_artist, raw_movie
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    c_id,
                    rank,
                    prev_rank,
                    s_id,
                    r_title,
                    r_artist,
                    r_movie,
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

    def update_chart_entry_song(self, chart_id: str, rank: int, song_id: int) -> bool:
        """Link a chart entry to a canonical song ID."""
        with self._lock:
            with self._conn:
                cursor = self._conn.cursor()
                cursor.execute("""
                    UPDATE chart_entries
                    SET song_id = ?
                    WHERE chart_id = ? AND rank = ?
                """, (song_id, chart_id, rank))
                return cursor.rowcount > 0

    def search_and_filter_charts(
        self,
        query: str = "",
        chart_type: Optional[str] = None,
        sort_by: str = "snapshot_date",
        ascending: bool = False,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Search and filter charts with total and downloaded song counts.
        Returns (charts_list, total_count).
        """
        with self._lock:
            cursor = self._conn.cursor()
            where_clauses = []
            params: List[Any] = []

            if query:
                q = f"%{query.strip()}%"
                where_clauses.append("(c.title LIKE ? OR c.provider_name LIKE ?)")
                params.extend([q, q])

            if chart_type and chart_type.lower() != "all":
                where_clauses.append("c.chart_type = ?")
                params.append(chart_type)

            where_str = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

            # Count total matching
            count_sql = f"SELECT COUNT(*) FROM charts c {where_str}"
            cursor.execute(count_sql, params)
            total_count = cursor.fetchone()[0]

            # Allowed sorts
            sort_dir = "ASC" if ascending else "DESC"
            sort_column = "c.snapshot_date"
            if sort_by == "title":
                sort_column = "c.title"
            elif sort_by == "created_at":
                sort_column = "c.created_at"
            elif sort_by == "type":
                sort_column = "c.chart_type"

            sql = f"""
                SELECT
                    c.id,
                    c.title,
                    c.chart_type,
                    c.provider_name,
                    c.snapshot_date,
                    c.created_at,
                    (SELECT COUNT(*) FROM chart_entries ce WHERE ce.chart_id = c.id) AS total_entries,
                    (
                        SELECT COUNT(*)
                        FROM chart_entries ce
                        JOIN songs s ON ce.song_id = s.id
                        WHERE ce.chart_id = c.id
                          AND s.state = 'OWNED'
                          AND s.file_path IS NOT NULL
                    ) AS owned_entries
                FROM charts c
                {where_str}
                ORDER BY {sort_column} {sort_dir}
                LIMIT ? OFFSET ?
            """
            query_params = list(params) + [limit, offset]
            cursor.execute(sql, query_params)
            rows = cursor.fetchall()

            charts = []
            for r in rows:
                c_dict = {
                    "id": r["id"],
                    "title": r["title"],
                    "chart_type": r["chart_type"],
                    "provider_name": r["provider_name"],
                    "snapshot_date": r["snapshot_date"],
                    "created_at": r["created_at"],
                    "total_entries": r["total_entries"],
                    "downloaded_entries": r["owned_entries"],
                    "missing_entries": max(0, r["total_entries"] - r["owned_entries"]),
                }
                charts.append(c_dict)

            return charts, total_count

    def get_chart_statistics(self, chart_id: str) -> Dict[str, int]:
        """
        Get authoritative statistics for a chart.
        Cross-verifies physical file presence on disk.
        """
        import os
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("""
                SELECT
                    ce.id,
                    ce.rank,
                    ce.song_id,
                    s.state,
                    s.file_path
                FROM chart_entries ce
                LEFT JOIN songs s ON ce.song_id = s.id
                WHERE ce.chart_id = ?
            """, (chart_id,))
            rows = cursor.fetchall()

            total_songs = len(rows)
            downloaded = 0
            for r in rows:
                if (
                    r["song_id"] is not None
                    and r["state"] == "OWNED"
                    and r["file_path"]
                    and os.path.isfile(r["file_path"])
                ):
                    downloaded += 1

            return {
                "total_songs": total_songs,
                "downloaded_songs": downloaded,
                "missing_songs": max(0, total_songs - downloaded),
            }

    def get_chart_entries_detailed(
        self,
        chart_id: str,
        query: str = "",
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Get detailed ranked entries for a chart, joined with songs, artists, and movies.
        Computes trend direction (up, down, same, new) and verifies physical download state.
        Returns (entries_list, total_matching).
        """
        import os
        with self._lock:
            cursor = self._conn.cursor()

            where_clauses = ["ce.chart_id = ?"]
            params: List[Any] = [chart_id]

            if query:
                q = f"%{query.strip()}%"
                where_clauses.append("""(
                    ce.raw_title LIKE ?
                    OR ce.raw_artist LIKE ?
                    OR ce.raw_movie LIKE ?
                    OR s.title LIKE ?
                    OR s.artist LIKE ?
                )""")
                params.extend([q, q, q, q, q])

            where_str = f"WHERE {' AND '.join(where_clauses)}"

            # Count total
            count_sql = f"""
                SELECT COUNT(*)
                FROM chart_entries ce
                LEFT JOIN songs s ON ce.song_id = s.id
                {where_str}
            """
            cursor.execute(count_sql, params)
            total_matching = cursor.fetchone()[0]

            sql = f"""
                SELECT
                    ce.id AS entry_id,
                    ce.chart_id,
                    ce.rank,
                    ce.previous_rank,
                    ce.song_id,
                    ce.raw_title,
                    ce.raw_artist,
                    ce.raw_movie,
                    s.title AS song_title,
                    s.artist AS song_artist,
                    s.album AS song_album,
                    s.duration_seconds,
                    s.quality_kbps,
                    s.file_path,
                    s.state AS song_state
                FROM chart_entries ce
                LEFT JOIN songs s ON ce.song_id = s.id
                {where_str}
                ORDER BY ce.rank ASC
                LIMIT ? OFFSET ?
            """
            query_params = list(params) + [limit, offset]
            cursor.execute(sql, query_params)
            rows = cursor.fetchall()

            entries = []
            for r in rows:
                rank = r["rank"]
                prev_rank = r["previous_rank"]

                # Determine trend
                if prev_rank is None or prev_rank == 0:
                    trend = "new"
                    trend_label = "NEW"
                    trend_diff = 0
                elif prev_rank > rank:
                    diff = prev_rank - rank
                    trend = "up"
                    trend_label = f"▲ {diff}"
                    trend_diff = diff
                elif prev_rank < rank:
                    diff = rank - prev_rank
                    trend = "down"
                    trend_label = f"▼ {diff}"
                    trend_diff = -diff
                else:
                    trend = "same"
                    trend_label = "＝"
                    trend_diff = 0

                # Authoritative download check
                file_path = r["file_path"]
                song_state = r["song_state"] or "NEW"
                is_downloaded = bool(
                    r["song_id"] is not None
                    and song_state == "OWNED"
                    and file_path
                    and os.path.isfile(file_path)
                )

                # Try resolving artist ID for clickable navigation
                artist_name = r["song_artist"] or r["raw_artist"]
                artist_id = None
                if artist_name:
                    norm_artist = normalize_string(artist_name.split(",")[0])
                    if norm_artist:
                        cur_art = self._conn.cursor()
                        cur_art.execute(
                            "SELECT id FROM artists WHERE name_normalized = ? LIMIT 1",
                            (norm_artist,)
                        )
                        art_row = cur_art.fetchone()
                        if art_row:
                            artist_id = art_row[0]

                # Try resolving movie ID for clickable navigation
                movie_name = r["song_album"] or r["raw_movie"]
                movie_id = None
                if movie_name:
                    norm_movie = normalize_string(movie_name)
                    if norm_movie:
                        cur_mov = self._conn.cursor()
                        cur_mov.execute(
                            "SELECT id FROM movies WHERE title_normalized = ? LIMIT 1",
                            (norm_movie,)
                        )
                        mov_row = cur_mov.fetchone()
                        if mov_row:
                            movie_id = mov_row[0]

                entries.append({
                    "entry_id": r["entry_id"],
                    "chart_id": r["chart_id"],
                    "rank": rank,
                    "previous_rank": prev_rank,
                    "trend": trend,
                    "trend_label": trend_label,
                    "trend_diff": trend_diff,
                    "song_id": r["song_id"],
                    "title": r["song_title"] or r["raw_title"],
                    "artist": r["song_artist"] or r["raw_artist"] or "Unknown Artist",
                    "movie": r["song_album"] or r["raw_movie"] or "Single",
                    "duration_seconds": r["duration_seconds"],
                    "quality_kbps": r["quality_kbps"],
                    "file_path": file_path,
                    "song_state": song_state,
                    "is_downloaded": is_downloaded,
                    "artist_id": artist_id,
                    "movie_id": movie_id,
                })

            return entries, total_matching
