"""
Download Registry for concurrent download management.

Provides atomic slot acquisition to prevent concurrent downloads of
the same song, using database-level state transitions protected by
a threading lock.
"""

import logging
import threading
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from library.models import Download, DownloadState, SongState

if TYPE_CHECKING:
    from library.database import SQLiteDatabase

logger = logging.getLogger(__name__)


class DownloadRegistry:
    """
    Central registry to prevent concurrent duplicate downloads.

    Uses a threading RLock + database-level state transitions for
    thread-safe slot acquisition. Works across ThreadPoolExecutor
    workers without requiring external synchronization by callers.

    Usage::

        registry = DownloadRegistry(db)

        if registry.acquire(song_id, source_id):
            try:
                # do download ...
                registry.complete(song_id, download_id, file_path, ...)
            except Exception as e:
                registry.fail(song_id, download_id, str(e))
        else:
            # Already downloading — skip
    """

    def __init__(self, db: "SQLiteDatabase"):
        """
        Initialize registry.

        Args:
            db: Connected SQLiteDatabase instance
        """
        self.db = db
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Slot acquisition / release
    # ------------------------------------------------------------------

    def acquire(self, song_id: int, song_source_id: int) -> Optional[int]:
        """
        Atomically acquire a download slot for a song.

        Transitions song state to DOWNLOADING and creates a Download record.
        Returns the download ID if acquired, or None if the song is already
        being downloaded or queued.

        Args:
            song_id: Library song ID
            song_source_id: Source variant ID to download from

        Returns:
            Download record ID if acquired, None if already in progress
        """
        with self._lock:
            song = self.db.get_song(song_id)
            if song is None:
                logger.error(f"acquire: song {song_id} not found in library")
                return None

            if song.state in (SongState.DOWNLOADING, SongState.QUEUED):
                logger.debug(
                    f"acquire: song {song_id} already in state {song.state.value} — skipping"
                )
                return None

            # Transition to DOWNLOADING
            self.db.update_song_state(song_id, SongState.DOWNLOADING)

            now = datetime.now().isoformat()
            # Create download record
            download = Download(
                song_id=song_id,
                song_source_id=song_source_id,
                queued_at=now,
                started_at=now,
                state=DownloadState.DOWNLOADING,
            )
            download_id = self.db.add_download(download)

            logger.debug(f"acquire: slot acquired for song {song_id} (download {download_id})")
            return download_id

    def complete(
        self,
        song_id: int,
        download_id: int,
        file_path: str,
        file_size_bytes: int,
        quality_kbps: Optional[int],
        library_location_id: int,
        download_speed_bps: Optional[float] = None,
        was_upgrade: bool = False,
        previous_file_path: Optional[str] = None,
        previous_quality_kbps: Optional[int] = None,
    ) -> None:
        """
        Mark a download as successfully completed.

        Updates both the download record and the song's file info / state.

        Args:
            song_id: Library song ID
            download_id: Download record ID
            file_path: Path where file was saved
            file_size_bytes: Size of downloaded file
            quality_kbps: Quality of downloaded file
            library_location_id: Library location ID
            download_speed_bps: Average download speed (optional)
            was_upgrade: Whether this was a quality upgrade
            previous_file_path: Old file path if upgrade
            previous_quality_kbps: Old quality if upgrade
        """
        with self._lock:
            # Update download record
            self.db.update_download_completed(
                download_id=download_id,
                output_path=file_path,
                file_size_bytes=file_size_bytes,
                download_speed_bps=download_speed_bps,
                was_upgrade=was_upgrade,
                previous_file_path=previous_file_path,
                previous_quality_kbps=previous_quality_kbps,
                library_location_id=library_location_id,
            )

            # Update song file info and mark OWNED
            self.db.update_song_file(
                song_id=song_id,
                file_path=file_path,
                file_size_bytes=file_size_bytes,
                quality_kbps=quality_kbps or 0,
                library_location_id=library_location_id,
            )

            logger.info(f"complete: song {song_id} download finished → OWNED")

    def fail(
        self,
        song_id: int,
        download_id: int,
        error_message: str,
        source_id: Optional[int] = None,
    ) -> None:
        """
        Mark a download as failed.

        Transitions song back to FAILED state and records error.
        Optionally decrements source reliability score.

        Args:
            song_id: Library song ID
            download_id: Download record ID
            error_message: Error description
            source_id: Source ID to penalize reliability (optional)
        """
        with self._lock:
            self.db.update_download_state(
                download_id, DownloadState.FAILED, error_message=error_message
            )
            self.db.update_song_state(song_id, SongState.FAILED)

            if source_id is not None:
                self._penalize_source(source_id)

            logger.warning(
                f"fail: song {song_id} download failed — {error_message}"
            )

    def is_downloading(self, song_id: int) -> bool:
        """
        Check if a song is currently being downloaded.

        Args:
            song_id: Library song ID

        Returns:
            True if downloading or queued
        """
        with self._lock:
            song = self.db.get_song(song_id)
            if song is None:
                return False
            return song.state in (SongState.DOWNLOADING, SongState.QUEUED)

    # ------------------------------------------------------------------
    # Source reliability tracking
    # ------------------------------------------------------------------

    def reward_source(self, source_id: int, increment: float = 0.05) -> None:
        """
        Increase source reliability score after successful download.

        Args:
            source_id: Source ID
            increment: Amount to increase score (default 0.05)
        """
        with self._lock:
            sources = self._get_source(source_id)
            if sources is not None:
                new_score = min(1.0, sources + increment)
                self.db.update_source_reliability(source_id, new_score)

    def _penalize_source(self, source_id: int, decrement: float = 0.1) -> None:
        """
        Decrease source reliability score after failed download.

        Args:
            source_id: Source ID
            decrement: Amount to decrease score (default 0.1)
        """
        sources = self._get_source(source_id)
        if sources is not None:
            new_score = max(0.0, sources - decrement)
            self.db.update_source_reliability(source_id, new_score)

    def _get_source(self, source_id: int) -> Optional[float]:
        """
        Get current reliability score for a source.

        Args:
            source_id: Source ID

        Returns:
            Current reliability score, or None if source not found
        """
        try:
            cursor = self.db._conn.cursor()
            cursor.execute(
                "SELECT reliability_score FROM song_sources WHERE id = ?",
                (source_id,)
            )
            row = cursor.fetchone()
            return row[0] if row else None
        except Exception as e:
            logger.debug(f"Failed to get source reliability: {e}")
            return None
