"""
Deterministic Batch Download Manager for V6.
Coordinates multi-track download batches (Spotify Import, Movies, Artists, Playlists, Songs)
with thread-safe execution, progress tracking, and batch vs single track cancellation.
"""

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from library.models import DownloadState, SongState

logger = logging.getLogger(__name__)


@dataclass
class BatchDownloadJob:
    """Represents a logical multi-track download batch."""
    batch_id: str
    title: str
    source_type: str  # spotify, movie, artist, playlist, songs
    child_download_ids: List[int] = field(default_factory=list)
    total_tracks: int = 0
    completed_ids: Set[int] = field(default_factory=set)
    failed_ids: Set[int] = field(default_factory=set)
    cancelled_ids: Set[int] = field(default_factory=set)
    active_download_id: Optional[int] = None
    current_track: Optional[str] = None
    status: str = "in_progress"  # in_progress, completed, cancelled, failed
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    cancel_event: threading.Event = field(default_factory=threading.Event)

    @property
    def is_cancelled(self) -> bool:
        return self.cancel_event.is_set() or self.status == "cancelled"

    @property
    def completed(self) -> int:
        return len(self.completed_ids)

    @property
    def failed(self) -> int:
        return len(self.failed_ids)

    @property
    def cancelled(self) -> int:
        return len(self.cancelled_ids)

    @property
    def active(self) -> int:
        return 1 if self.active_download_id is not None and not self.is_cancelled else 0

    @property
    def queued(self) -> int:
        if self.is_cancelled:
            return 0
        rem = self.total_tracks - (self.completed + self.failed + self.cancelled + self.active)
        return max(0, rem)

    @property
    def overall_percentage(self) -> float:
        if self.total_tracks <= 0:
            return 100.0 if self.status == "completed" else 0.0
        pct = (self.completed / float(self.total_tracks)) * 100.0
        return round(min(100.0, max(0.0, pct)), 1)

    def to_dict(self, service=None, include_tracks: bool = True) -> Dict[str, Any]:
        """Serialize batch for API and WebSocket consumers."""
        data: Dict[str, Any] = {
            "batch_id": self.batch_id,
            "title": self.title,
            "source_name": self.title,
            "context_name": self.title,
            "source_type": self.source_type,
            "total_tracks": self.total_tracks,
            "completed": self.completed,
            "active": self.active,
            "queued": self.queued,
            "failed": self.failed,
            "cancelled": self.cancelled,
            "overall_percentage": self.overall_percentage,
            "current_track": self.current_track,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

        if include_tracks and service:
            track_items = []
            for dl_id in self.child_download_ids:
                dl = service.db.get_download(dl_id) if hasattr(service, "db") else None
                if dl:
                    song = service.db.get_song(dl.song_id) if dl.song_id else None
                    st_str = dl.state.value if hasattr(dl.state, "value") else str(dl.state)
                    track_items.append({
                        "download_id": dl.id,
                        "song_id": dl.song_id,
                        "title": song.title if song else f"Track #{dl.id}",
                        "artist": song.artist if song else None,
                        "status": st_str.lower(),
                        "is_active": dl.id == self.active_download_id,
                    })
            data["tracks"] = track_items

        return data


class BatchDownloadManager:
    """Central singleton/service coordinator for batch download operations."""

    def __init__(self, service):
        self.service = service
        self._batches: Dict[str, BatchDownloadJob] = {}
        self._download_to_batch: Dict[int, str] = {}
        self._lock = threading.RLock()
        self._ensure_table()

    def _ensure_table(self) -> None:
        """Ensure download_batches table exists in database."""
        try:
            with self.service.db._lock, self.service.db._conn:
                cur = self.service.db._conn.cursor()
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS download_batches (
                        id TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        source_type TEXT NOT NULL,
                        total_tracks INTEGER DEFAULT 0,
                        status TEXT NOT NULL,
                        created_at TIMESTAMP,
                        updated_at TIMESTAMP
                    )
                """)
                # Try adding batch_id to downloads table if missing
                try:
                    cur.execute("ALTER TABLE downloads ADD COLUMN batch_id TEXT")
                except Exception:
                    pass
                cur.execute("CREATE INDEX IF NOT EXISTS idx_downloads_batch_id ON downloads(batch_id)")
        except Exception as e:
            logger.debug(f"Table verification in BatchDownloadManager: {e}")

    def create_batch(
        self,
        batch_id: str,
        title: str,
        source_type: str,
        child_download_ids: List[int],
        total_tracks: Optional[int] = None,
    ) -> BatchDownloadJob:
        """Create and register a new batch download job."""
        with self._lock:
            total = total_tracks if total_tracks is not None else len(child_download_ids)
            batch = BatchDownloadJob(
                batch_id=batch_id,
                title=title,
                source_type=source_type,
                child_download_ids=list(child_download_ids),
                total_tracks=total,
                status="in_progress",
            )
            self._batches[batch_id] = batch

            for dl_id in child_download_ids:
                self._download_to_batch[dl_id] = batch_id
                # Associate batch_id in database download record
                try:
                    with self.service.db._lock, self.service.db._conn:
                        cur = self.service.db._conn.cursor()
                        cur.execute("UPDATE downloads SET batch_id = ? WHERE id = ?", (batch_id, dl_id))
                except Exception:
                    pass

            # Persist batch record in DB
            try:
                with self.service.db._lock, self.service.db._conn:
                    cur = self.service.db._conn.cursor()
                    cur.execute("""
                        INSERT OR REPLACE INTO download_batches (id, title, source_type, total_tracks, status, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (batch_id, title, source_type, total, "in_progress", datetime.now().isoformat(), datetime.now().isoformat()))
            except Exception:
                pass

            self._broadcast_batch_event(batch)
            logger.info(f"Registered batch {batch_id} ('{title}') with {total} tracks.")
            return batch

    def get_batch(self, batch_id: str) -> Optional[BatchDownloadJob]:
        with self._lock:
            return self._batches.get(batch_id)

    def get_batch_for_download(self, download_id: int) -> Optional[BatchDownloadJob]:
        with self._lock:
            b_id = self._download_to_batch.get(download_id)
            if b_id:
                return self._batches.get(b_id)
            return None

    def get_all_batches(self) -> List[BatchDownloadJob]:
        with self._lock:
            return sorted(self._batches.values(), key=lambda b: b.created_at, reverse=True)

    def get_active_batches(self) -> List[BatchDownloadJob]:
        with self._lock:
            return [
                b for b in self._batches.values()
                if b.status == "in_progress" and not b.is_cancelled
            ]

    def on_track_started(self, batch_id: str, download_id: int, track_title: str) -> None:
        """Mark track as actively downloading within its batch."""
        with self._lock:
            batch = self._batches.get(batch_id)
            if not batch or batch.is_cancelled:
                return
            batch.active_download_id = download_id
            batch.current_track = track_title
            batch.updated_at = datetime.now()
            self._broadcast_batch_event(batch)

    def on_track_completed(self, batch_id: str, download_id: int) -> None:
        """Mark track completed within its batch."""
        with self._lock:
            batch = self._batches.get(batch_id)
            if not batch:
                return
            batch.completed_ids.add(download_id)
            if batch.active_download_id == download_id:
                batch.active_download_id = None
            batch.updated_at = datetime.now()

            # Check if all tracks finished
            if (batch.completed + batch.failed + batch.cancelled) >= batch.total_tracks:
                batch.status = "completed"
                self._update_db_status(batch_id, "completed")

            self._broadcast_batch_event(batch)

    def on_track_failed(self, batch_id: str, download_id: int) -> None:
        """Mark track failed within its batch."""
        with self._lock:
            batch = self._batches.get(batch_id)
            if not batch:
                return
            batch.failed_ids.add(download_id)
            if batch.active_download_id == download_id:
                batch.active_download_id = None
            batch.updated_at = datetime.now()

            if (batch.completed + batch.failed + batch.cancelled) >= batch.total_tracks:
                batch.status = "completed" if batch.completed > 0 else "failed"
                self._update_db_status(batch_id, batch.status)

            self._broadcast_batch_event(batch)

    def cancel_batch(self, batch_id: str) -> bool:
        """
        Cancel an entire batch:
        - Signals batch cancel event so loop halts immediately
        - Cancels the active child job
        - Marks all queued child jobs as CANCELLED
        - Leaves already completed child jobs untouched
        - Batch final state becomes CANCELLED
        """
        with self._lock:
            batch = self._batches.get(batch_id)
            if not batch:
                logger.warning(f"cancel_batch: Batch {batch_id} not found in memory")
                return False

            if batch.status in ("completed", "cancelled") and batch.is_cancelled:
                return True

            logger.info(f"Cancelling entire batch {batch_id} ('{batch.title}')")
            batch.cancel_event.set()
            batch.status = "cancelled"
            batch.updated_at = datetime.now()

            # 1. Cancel active child job if one is running
            active_id = batch.active_download_id
            if active_id:
                batch.cancelled_ids.add(active_id)
                batch.active_download_id = None
                self._cancel_download_record(active_id)

            # 2. Cancel all queued/planned child jobs
            for dl_id in batch.child_download_ids:
                if dl_id not in batch.completed_ids and dl_id not in batch.failed_ids:
                    batch.cancelled_ids.add(dl_id)
                    self._cancel_download_record(dl_id)

            self._update_db_status(batch_id, "cancelled")
            self._broadcast_batch_event(batch)
            return True

    def cancel_track(self, download_id: int) -> bool:
        """
        Cancel ONLY the specified single track.
        If part of a batch, marks track cancelled without halting the remaining batch.
        """
        with self._lock:
            batch = self.get_batch_for_download(download_id)
            if batch:
                batch.cancelled_ids.add(download_id)
                if batch.active_download_id == download_id:
                    batch.active_download_id = None
                batch.updated_at = datetime.now()
                if (batch.completed + batch.failed + batch.cancelled) >= batch.total_tracks:
                    batch.status = "completed" if batch.completed > 0 else "cancelled"
                    self._update_db_status(batch.batch_id, batch.status)
                self._broadcast_batch_event(batch)

            # Update DB download state
            self._cancel_download_record(download_id)
            return True

    def _cancel_download_record(self, download_id: int) -> None:
        """Update DB download and song state to CANCELLED."""
        try:
            dl = self.service.db.get_download(download_id)
            if dl:
                self.service.db.update_download_state(
                    download_id,
                    DownloadState.CANCELLED,
                    error_message="Cancelled by user"
                )
                if dl.song_id:
                    # Reset song state to NEW so it can be downloaded later
                    self.service.db.update_song_state(dl.song_id, SongState.NEW)
        except Exception as e:
            logger.error(f"Error cancelling download record {download_id}: {e}")

    def _update_db_status(self, batch_id: str, status: str) -> None:
        try:
            with self.service.db._lock, self.service.db._conn:
                cur = self.service.db._conn.cursor()
                cur.execute(
                    "UPDATE download_batches SET status = ?, updated_at = ? WHERE id = ?",
                    (status, datetime.now().isoformat(), batch_id)
                )
        except Exception:
            pass

    def _broadcast_batch_event(self, batch: BatchDownloadJob) -> None:
        """Emit live WebSocket progress event for the batch."""
        try:
            from library.service import DownloadProgressEvent
            self.service.emit_progress(DownloadProgressEvent(
                download_id=batch.active_download_id or 0,
                song_id=0,
                title=batch.title,
                status=batch.status.upper(),
                percent=batch.overall_percentage / 100.0,
                speed_str=f"{batch.completed}/{batch.total_tracks} completed · {batch.active} active · {batch.queued} queued",
                batch_id=batch.batch_id,
                batch_data=batch.to_dict(service=self.service, include_tracks=False),
            ))
        except Exception as exc:
            logger.debug(f"Failed broadcasting batch event: {exc}")
