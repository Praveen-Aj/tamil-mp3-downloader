"""
Song Discovery Integration for the library system.

Provides a pipeline to canonicalize discovered songs from scrapers,
register them in the library, aggregate source variants, and track
discovery context — enabling cross-category/source deduplication.
"""

import logging
from typing import Optional, List

from library.canonical import CanonicalIdentity, compute_canonical_hash
from library.database import SQLiteDatabase
from library.models import LibrarySong, SongSource, DiscoveryContext, SongState
from models.song import Song, Album

logger = logging.getLogger(__name__)


def song_to_canonical(song: Song, source_name: str) -> CanonicalIdentity:
    """
    Convert a scraper Song to a CanonicalIdentity.

    Args:
        song: Song from scraper
        source_name: Name of source (e.g. 'isaimini')

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
    if "320" in q:
        return 320
    if "256" in q:
        return 256
    if "192" in q:
        return 192
    if "160" in q:
        return 160
    if "128" in q:
        return 128
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
        File type string (mp3, zip, etc.)
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
    2. Check if it already exists in the library
    3. If new, add as LibrarySong
    4. Add/update the source variant
    5. Record discovery context
    """

    def __init__(self, db: SQLiteDatabase):
        """
        Initialize discovery pipeline.

        Args:
            db: Connected SQLiteDatabase instance
        """
        self.db = db

    def register_song(
        self,
        song: Song,
        source_name: str,
        album: Optional[Album] = None,
        category: Optional[str] = None,
    ) -> int:
        """
        Register a discovered song in the library.

        Args:
            song: Discovered Song from scraper
            source_name: Source name (e.g. 'isaimini', 'masstamilan')
            album: Album context (optional)
            category: Category (e.g. 'latest', 'old') where discovered

        Returns:
            Library song ID
        """
        identity = song_to_canonical(song, source_name)

        # Check if already known
        existing = self.db.get_song_by_canonical_hash(identity.hash)

        if existing:
            song_id = existing.id
            logger.debug(f"Song already in library: {identity} (id={song_id})")
        else:
            # Create new library entry
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
            logger.debug(f"Added new song to library: {identity} (id={song_id})")

        # Add source variant (ignore duplicate URL errors)
        self._add_or_update_source(song_id, song, source_name)

        # Record discovery context
        self._record_discovery_context(song_id, source_name, album, category)

        return song_id

    def register_batch(
        self,
        songs: List[Song],
        source_name: str,
        album: Optional[Album] = None,
        category: Optional[str] = None,
    ) -> dict:
        """
        Register a batch of discovered songs.

        Args:
            songs: List of discovered Songs
            source_name: Source name
            album: Album context (optional)
            category: Category (optional)

        Returns:
            Statistics dict: {new, existing, total}
        """
        new_count = 0
        existing_count = 0

        for song in songs:
            try:
                identity = song_to_canonical(song, source_name)
                existing = self.db.get_song_by_canonical_hash(identity.hash)
                self.register_song(song, source_name, album, category)
                if existing:
                    existing_count += 1
                else:
                    new_count += 1
            except Exception as e:
                logger.warning(f"Failed to register song '{song.name}': {e}")

        stats = {
            "new": new_count,
            "existing": existing_count,
            "total": len(songs),
        }
        logger.info(
            f"Batch registered {len(songs)} songs from {source_name}: "
            f"{new_count} new, {existing_count} existing"
        )
        return stats

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _add_or_update_source(
        self, song_id: int, song: Song, source_name: str
    ) -> None:
        """
        Add or update a source variant for a song.

        Ignores duplicate (song_id, source_url) pairs silently.

        Args:
            song_id: Library song ID
            song: Original song from scraper
            source_name: Source name
        """
        source = SongSource(
            song_id=song_id,
            source_name=source_name,
            source_url=song.url,
            quality_kbps=extract_quality_kbps(song),
            file_size_bytes=extract_file_size_bytes(song),
            file_type=extract_file_type(song),
            is_available=True,
        )
        try:
            self.db.add_source(source)
        except Exception:
            # Likely a UNIQUE constraint violation (duplicate URL) — skip silently
            pass

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
