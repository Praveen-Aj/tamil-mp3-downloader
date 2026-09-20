"""
Download Registry for concurrent download management.

Provides atomic slot acquisition to prevent concurrent downloads of
the same song, using database-level state transitions protected by
a threading lock.
"""

import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, List, TYPE_CHECKING

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
        Attempt to acquire a download slot for a song.

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
            # Enforce physical filesystem invariant: file must exist and be > 0 bytes
            if not file_path:
                err = "Physical file validation failed: file_path is empty"
                logger.error(f"Cannot complete download for song {song_id}: {err}")
                self.fail(song_id, download_id, err, None)
                return

            p = Path(file_path)
            if not p.is_file() or not p.exists() or p.stat().st_size <= 0:
                err = f"Physical file validation failed for '{file_path}': file is missing, empty, or not a regular file"
                logger.error(f"Cannot complete download for song {song_id}: {err}")
                self.fail(song_id, download_id, err, None)
                return

            actual_size = p.stat().st_size
            effective_size = file_size_bytes if (file_size_bytes and file_size_bytes > 0) else actual_size

            # Update download record
            self.db.update_download_completed(
                download_id=download_id,
                output_path=file_path,
                file_size_bytes=effective_size,
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
                file_size_bytes=effective_size,
                quality_kbps=quality_kbps,
                library_location_id=library_location_id,
            )

            logger.info(f"complete: song {song_id} download verified on disk ({effective_size} bytes) → OWNED")

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

    def acquire_download(self, song_id: int, song_source_id: int) -> Optional[int]:
        """Alias for acquire."""
        return self.acquire(song_id, song_source_id)

    def get_active_downloads(self) -> List[Download]:
        """
        Get all active downloads currently downloading or queued.
        """
        with self._lock:
            all_dls = self.db.get_all_downloads()
            active_states = {
                DownloadState.DOWNLOADING, DownloadState.QUEUED,
                "DOWNLOADING", "QUEUED", "downloading", "queued"
            }
            return [
                d for d in all_dls
                if d.state in active_states or (hasattr(d.state, "value") and d.state.value in active_states)
            ]


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
            source = self.db.get_source_by_id(source_id)
            if source is not None:
                new_score = min(1.0, source.reliability_score + increment)
                self.db.update_source_reliability(source_id, new_score)

    def _penalize_source(self, source_id: int, decrement: float = 0.1) -> None:
        """
        Decrease source reliability score after failed download.

        Args:
            source_id: Source ID
            decrement: Amount to decrease score (default 0.1)
        """
        source = self.db.get_source_by_id(source_id)
        if source is not None:
            new_score = max(0.0, source.reliability_score - decrement)
            self.db.update_source_reliability(source_id, new_score)

    # Alias for backwards compatibility
    acquire_download = acquire

