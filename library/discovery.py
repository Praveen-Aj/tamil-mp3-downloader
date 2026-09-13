"""
Song Discovery Integration for the library system.

Provides a pipeline to canonicalize discovered songs from scrapers,
register them in the library, aggregate source variants, and track
discovery context — enabling cross-category/source deduplication.

Thread-safety: DiscoveryPipeline uses an RLock to make the
check-then-upsert sequence atomic across concurrent scraper workers.
"""

import logging
import threading
from typing import Optional, List

from library.canonical import CanonicalIdentity
from library.database import SQLiteDatabase
from library.models import LibrarySong, SongSource, DiscoveryContext, SongState
from models.song import Song, Album

logger = logging.getLogger(__name__)


def song_to_canonical(song: Song, source_name: str = "") -> CanonicalIdentity:
    """
    Convert a scraper Song to a CanonicalIdentity.

    Args:
        song: Song from scraper
        source_name: Name of source (unused — kept for API compatibility)

    Returns:
        CanonicalIdentity for the song
    """
    title = song.name or "Unknown"
    artist = song.artist or ""
    album = song.album_title or song.album_name or ""
    year = song.year
    return CanonicalIdentity.from_metadata(title, artist, album, year)


def extract_quality_kbps(song: Song) -> Optional[int]:
    """
    Extract quality in kbps from a Song's quality string.

    Args:
        song: Song object

    Returns:
        Quality in kbps, or None if unknown
    """
    q = (song.quality or "").lower()
    for kbps in (320, 256, 192, 160, 128):
        if str(kbps) in q:
            return kbps
    return None


def extract_file_size_bytes(song: Song) -> Optional[int]:
    """
    Extract file size in bytes from a Song.

    Args:
        song: Song object

    Returns:
        File size in bytes, or None if unknown
    """
    if song.size_mb is not None:
        return int(song.size_mb * 1024 * 1024)
    return None


def extract_file_type(song: Song) -> str:
    """
    Determine file type from song URL.

    Args:
        song: Song object

    Returns:
        File type string (mp3, zip, m4a, flac)
    """
    url_lower = (song.url or "").lower()
    if ".zip" in url_lower:
        return "zip"
    if ".m4a" in url_lower:
        return "m4a"
    if ".flac" in url_lower:
        return "flac"
    return "mp3"


class DiscoveryPipeline:
    """
    Pipeline that registers discovered songs into the library.

    On each call to register_song():
    1. Canonicalize the song
    2. Upsert into the library (INSERT OR IGNORE + SELECT fallback)
    3. Add/update the source variant (idempotent)
    4. Record discovery context

    Thread-safety:
        An RLock serializes the full register_song() critical section so
        concurrent workers discovering the same canonical song from different
        categories/sources produce exactly one library entry.
    """

    def __init__(self, db: SQLiteDatabase):
        """
        Initialize discovery pipeline.

        Args:
            db: Connected SQLiteDatabase instance
        """
        self.db = db
        self._lock = threading.RLock()

    def register_song(
        self,
        song: Song,
        source_name: str,
        album: Optional[Album] = None,
        category: Optional[str] = None,
    ) -> int:
        """
        Register a discovered song in the library (idempotent & thread-safe).

        The full check-upsert-add_source sequence is wrapped in an RLock so
        concurrent calls for the same canonical song are serialized safely.

        Args:
            song: Discovered Song from scraper
            source_name: Source name (e.g. 'isaimini', 'masstamilan')
            album: Album context (optional)
            category: Category (e.g. 'latest', 'old') where discovered

        Returns:
            Library song ID (stable across repeated calls for same song)
        """
        identity = song_to_canonical(song, source_name)

        with self._lock:
            # Upsert: add_song uses INSERT OR IGNORE + SELECT fallback —
            # always returns the canonical song's ID, even under concurrency.
            lib_song = LibrarySong(
                canonical_hash=identity.hash,
                title_normalized=identity.title_normalized,
                artist_normalized=identity.artist_normalized,
                album_normalized=identity.album_normalized,
                year=identity.year,
                title=identity.title_original,
                artist=identity.artist_original or None,
                album=identity.album_original or None,
                state=SongState.NEW,
            )
            song_id = self.db.add_song(lib_song)

            # Add source variant (idempotent — INSERT OR IGNORE on (song_id, url))
            self._add_source(song_id, song, source_name)

        # Discovery context recorded outside the critical section (not unique-constrained)
        self._record_discovery_context(song_id, source_name, album, category)

        logger.debug(f"Registered song '{identity}' (id={song_id}) from {source_name}")
        return song_id

    def register_batch(
        self,
        songs: List[Song],
        source_name: str,
        album: Optional[Album] = None,
        category: Optional[str] = None,
    ) -> dict:
        """
        Register a batch of discovered songs and return deduplication stats.

        Args:
            songs: List of discovered Songs
            source_name: Source name
            album: Album context (optional)
            category: Category (optional)

        Returns:
            Statistics dict: {new, existing, total, errors}
        """
        new_count = 0
        existing_count = 0
        error_count = 0

        for song in songs:
            try:
                identity = song_to_canonical(song, source_name)
                # Check before registering to differentiate new vs existing in stats
                pre_existing = self.db.get_song_by_canonical_hash(identity.hash)
                self.register_song(song, source_name, album, category)
                if pre_existing is not None:
                    existing_count += 1
                else:
                    new_count += 1
            except Exception as e:
                error_count += 1
                logger.warning(f"Failed to register song '{song.name}': {e}")

        stats = {
            "new": new_count,
            "existing": existing_count,
            "total": len(songs),
            "errors": error_count,
        }
        logger.info(
            f"Batch registered {len(songs)} songs from {source_name}: "
            f"{new_count} new, {existing_count} existing, {error_count} errors"
        )
        return stats

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _add_source(self, song_id: int, song: Song, source_name: str) -> int:
        """
        Add a source variant for a song (idempotent).

        Uses INSERT OR IGNORE on (song_id, source_url).  Returns the source ID.

        Args:
            song_id: Library song ID
            song: Original song from scraper
            source_name: Source name

        Returns:
            Source ID (inserted or pre-existing)
        """
        source = SongSource(
            song_id=song_id,
            source_name=source_name,
            source_url=song.url,
            download_reference=getattr(song, "download_reference", None),
            quality_kbps=extract_quality_kbps(song),
            file_size_bytes=extract_file_size_bytes(song),
            file_type=extract_file_type(song),
            is_available=True,
        )
        return self.db.add_source(source)

    def _record_discovery_context(
        self,
        song_id: int,
        source_name: str,
        album: Optional[Album],
        category: Optional[str],
    ) -> None:
        """
        Record the discovery context for a song.

        Args:
            song_id: Library song ID
            source_name: Source name
            album: Album where discovered (optional)
            category: Category (optional)
        """
        ctx = DiscoveryContext(
            song_id=song_id,
            source_name=source_name,
            category=category,
            album_name=album.name if album else None,
            album_url=album.url if album else None,
        )
        try:
            self.db.add_discovery_context(ctx)
        except Exception as e:
            logger.debug(f"Failed to add discovery context: {e}")
