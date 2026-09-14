import logging
import os
import re
from pathlib import Path
from typing import Optional, List, Callable, Dict, Any, Tuple

from dataclasses import dataclass, field
from library.canonical import CanonicalIdentity
from library.models import LibrarySong, SongState

logger = logging.getLogger(__name__)

# Attempt Mutagen import for rich ID3 parsing
try:
    import mutagen
    from mutagen.mp3 import MP3
    from mutagen.easyid3 import EasyID3
    _MUTAGEN_AVAILABLE = True
except ImportError:
    _MUTAGEN_AVAILABLE = False


@dataclass
class ImportResult:
    """Statistics result model for import operations."""
    scanned: int = 0
    imported: int = 0     # New canonical songs added
    matched: int = 0      # Existing songs updated to OWNED
    unmatched: int = 0    # Metadata incomplete
    failed: int = 0       # Read/file errors
    conflicts: int = 0    # Conflicting metadata records

    def to_dict(self) -> Dict[str, int]:
        return {
            "scanned": self.scanned,
            "imported": self.imported,
            "matched": self.matched,
            "unmatched": self.unmatched,
            "failed": self.failed,
            "conflicts": self.conflicts,
        }


class LibraryImporter:
    """
    Import existing local MP3 files into the canonical library.

    Extracts ID3 metadata (or parses filenames), computes CanonicalIdentity,
    and registers files in SQLite with state=OWNED to participate in
    deduplication and prevent unnecessary online re-downloads.
    """

    def __init__(self, db):
        """
        Initialize library importer.

        Args:
            db: SQLiteDatabase instance
        """
        self.db = db

    def scan_directory(
        self,
        directory: Path,
        progress_cb: Optional[Callable[[int, int], None]] = None
    ) -> List[Path]:
        """Scan a directory recursively for MP3 files."""
        logger.info(f"Scanning directory for MP3 files: {directory}")
        if not directory.exists() or not directory.is_dir():
            return []
        
        mp3_files = list(directory.rglob("*.mp3"))
        if progress_cb:
            progress_cb(len(mp3_files), len(mp3_files))

        logger.info(f"Found {len(mp3_files)} MP3 files in {directory}")
        return mp3_files

    def extract_metadata(self, file_path: Path) -> Dict[str, Any]:
        """
        Extract metadata from an MP3 file using Mutagen ID3 or fallback to filename.

        Args:
            file_path: Path to MP3 file

        Returns:
            Dictionary containing title, artist, album, year, duration_seconds, quality_kbps, file_size_bytes
        """
        title = file_path.stem
        artist = ""
        album = ""
        year = None
        duration_seconds = None
        quality_kbps: Optional[int] = None  # Store None for unknown bitrate — DO NOT assume 320 kbps

        file_size_bytes = file_path.stat().st_size if file_path.exists() else 0

        # Try Mutagen extraction if available
        if _MUTAGEN_AVAILABLE and file_path.exists():
            try:
                audio = MP3(file_path, ID3=EasyID3)
                if audio.info:
                    if hasattr(audio.info, "bitrate") and audio.info.bitrate:
                        quality_kbps = int(audio.info.bitrate / 1000)
                    if hasattr(audio.info, "length") and audio.info.length:
                        duration_seconds = int(audio.info.length)

                title_tags = audio.get("title")
                if title_tags:
                    title = title_tags[0]
                artist_tags = audio.get("artist")
                if artist_tags:
                    artist = artist_tags[0]
                album_tags = audio.get("album")
                if album_tags:
                    album = album_tags[0]
                date_tags = audio.get("date") or audio.get("year")
                if date_tags:
                    y_match = re.search(r"\b(19\d{2}|20\d{2})\b", str(date_tags[0]))
                    if y_match:
                        year = int(y_match.group(1))
            except Exception as e:
                logger.debug(f"Mutagen ID3 extraction error for {file_path}: {e}")

        # Fallback filename cleanup if title contains quality or track numbers
        if title == file_path.stem:
            # Check filename for bitrate hint if mutagen failed to detect
            q_match = re.search(r"\b(320|128)\s*kbps\b", title, flags=re.I)
            if q_match and quality_kbps is None:
                quality_kbps = int(q_match.group(1))

            clean = re.sub(r"^\d+[\s\-\.]+", "", title).strip()
            clean = re.sub(r"\s*(320|128)kbps.*", "", clean, flags=re.I).strip()
            if clean:
                title = clean

        # Extract year from filename if missing
        if not year:
            y_match = re.search(r"\b(19\d{2}|20\d{2})\b", file_path.name)
            if y_match:
                year = int(y_match.group(1))

        return {
            "title": title,
            "artist": artist,
            "album": album,
            "year": year,
            "duration_seconds": duration_seconds,
            "quality_kbps": quality_kbps,
            "file_size_bytes": file_size_bytes,
        }

    def import_file(self, file_path: Path, location_id: Optional[int] = None) -> Tuple[Optional[int], bool]:
        """
        Import a single local MP3 file into the canonical library with state=OWNED.

        Args:
            file_path: Absolute path to MP3 file
            location_id: Optional LibraryLocation ID

        Returns:
            Tuple of (song_id or None, is_new_import: bool)
        """
        try:
            meta = self.extract_metadata(file_path)
            identity = CanonicalIdentity.from_metadata(
                title=meta["title"],
                artist=meta["artist"],
                album=meta["album"],
                year=meta["year"],
            )

            # Check if canonical song already exists in SQLite
            existing = self.db.get_song_by_canonical_hash(identity.hash)
            is_new = existing is None

            # Create or update canonical song in DB
            lib_song = LibrarySong(
                canonical_hash=identity.hash,
                title_normalized=identity.title_normalized,
                artist_normalized=identity.artist_normalized,
                album_normalized=identity.album_normalized,
                year=identity.year,
                duration_seconds=meta["duration_seconds"],
                title=identity.title_original,
                artist=identity.artist_original or None,
                album=identity.album_original or None,
                state=SongState.OWNED,  # Mark as local OWNED file!
                quality_kbps=meta["quality_kbps"],
                file_size_bytes=meta["file_size_bytes"],
                library_location_id=location_id,
                file_path=str(file_path),
            )

            song_id = self.db.add_song(lib_song)
            self.db.update_song_file(
                song_id=song_id,
                file_path=str(file_path),
                file_size_bytes=meta["file_size_bytes"],
                quality_kbps=meta["quality_kbps"],
                library_location_id=location_id or 1,
            )

            logger.info(f"Imported local MP3 '{identity}' (song_id={song_id}, is_new={is_new}) as OWNED")
            return song_id, is_new

        except Exception as e:
            logger.error(f"Failed to import local MP3 {file_path}: {e}")
            return None, False

    def import_directory(
        self,
        directory: Path,
        location_id: Optional[int] = None,
        progress_cb: Optional[Callable[[int, int], None]] = None
    ) -> Dict[str, int]:
        """
        Import all MP3 files from a local directory into the canonical library.

        Args:
            directory: Directory to scan and import
            location_id: Optional LibraryLocation ID
            progress_cb: Optional progress callback (current, total)

        Returns:
            Statistics dictionary conforming to ImportResult model schema.
        """
        res = ImportResult()
        mp3_files = self.scan_directory(directory)
        res.scanned = len(mp3_files)

        for i, file_path in enumerate(mp3_files, start=1):
            if progress_cb:
                progress_cb(i, res.scanned)

            song_id, is_new = self.import_file(file_path, location_id=location_id)
            if song_id is not None:
                if is_new:
                    res.imported += 1
                else:
                    res.matched += 1
            else:
                res.failed += 1

        logger.info(f"Import directory complete: {res.to_dict()}")
        return res.to_dict()

