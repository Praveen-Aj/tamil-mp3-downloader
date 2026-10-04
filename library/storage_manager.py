"""
Deterministic Storage Manager and Filesystem Reconciler.

Enforces the canonical directory structure under Songs New:
Songs New/
├── Movies/
│   ├── <Movie Name> (<Year>)/
│   │   ├── 01 - <Track>.mp3
│   │   ├── 02 - <Track>.mp3
│   │   └── ...
├── Singles/
│   └── <Artist> - <Track>.mp3
└── Imports/
    └── ...

Rules:
1. Movie soundtrack tracks are stored under Movies/<Movie Name> (<Year>)/
   with 2-digit track numbering where known.
2. Standalone songs without a canonical movie/album are stored under Singles/
3. Playlists are purely logical and NEVER duplicate files.
4. Spotify imports reuse existing canonical files where matched.
5. All downloads write complete ID3 metadata (title, artist, album/movie, year, track position, artwork).
"""

import logging
import os
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def sanitize_filename(name: str) -> str:
    """Strip characters invalid on Windows and POSIX filesystems."""
    if not name:
        return "Unknown"
    # Remove filesystem forbidden chars: < > : " / \ | ? * and control chars
    clean = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", str(name)).strip()
    # Normalize multiple whitespace
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean or "Unknown"


def get_canonical_download_path(
    base_dir: Path,
    song_title: str,
    artist: Optional[str] = None,
    movie_title: Optional[str] = None,
    movie_year: Optional[int] = None,
    track_number: Optional[int] = None,
    is_import: bool = False,
) -> Path:
    """
    Derive the deterministic destination path according to canonical rules.
    """
    base_dir = Path(base_dir)
    safe_title = sanitize_filename(song_title)

    # Strip .mp3 from safe_title if already present to avoid double extension
    if safe_title.lower().endswith(".mp3"):
        safe_title = safe_title[:-4].strip()

    if movie_title and movie_title.strip():
        # Movie Soundtrack Rule: Movies/<Movie Name> (<Year>)/<TrackNum> - <Title>.mp3
        safe_movie = sanitize_filename(movie_title)
        year_suffix = f" ({movie_year})" if movie_year and str(movie_year).isdigit() else ""
        folder_name = f"{safe_movie}{year_suffix}"
        target_dir = base_dir / "Movies" / folder_name

        if track_number and int(track_number) > 0:
            filename = f"{int(track_number):02d} - {safe_title}.mp3"
        else:
            filename = f"{safe_title}.mp3"
        return target_dir / filename

    # Standalone Song Rule: Singles/<Artist> - <Title>.mp3
    safe_artist = sanitize_filename(artist or "Unknown Artist")
    target_dir = base_dir / "Singles"
    filename = f"{safe_artist} - {safe_title}.mp3"
    return target_dir / filename


def tag_mp3_metadata(
    file_path: Path,
    title: str,
    artist: Optional[str] = None,
    album_or_movie: Optional[str] = None,
    year: Optional[int] = None,
    track_number: Optional[int] = None,
    cover_art_url: Optional[str] = None,
    cover_art_bytes: Optional[bytes] = None,
) -> bool:
    """
    Write complete ID3 tags into downloaded MP3 file using Mutagen.
    Includes title, artist, album/movie, year, track number, and embedded artwork.
    """
    try:
        from mutagen.mp3 import MP3
        from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC, TRCK, APIC, ID3NoHeaderError
    except ImportError:
        logger.warning("mutagen not installed, skipping ID3 tagging")
        return False

    p = Path(file_path)
    if not p.is_file() or p.suffix.lower() != ".mp3":
        return False

    try:
        try:
            audio = ID3(str(p))
        except ID3NoHeaderError:
            audio = ID3()

        # Title
        audio.delall("TIT2")
        audio.add(TIT2(encoding=3, text=title.strip()))

        # Artist
        if artist:
            audio.delall("TPE1")
            audio.add(TPE1(encoding=3, text=[artist.strip()]))

        # Album / Movie
        if album_or_movie:
            audio.delall("TALB")
            audio.add(TALB(encoding=3, text=album_or_movie.strip()))

        # Year
        if year and str(year).isdigit():
            audio.delall("TDRC")
            audio.add(TDRC(encoding=3, text=str(year)))

        # Track Number
        if track_number and int(track_number) > 0:
            audio.delall("TRCK")
            audio.add(TRCK(encoding=3, text=str(track_number)))

        # Cover Art
        art_payload = cover_art_bytes
        if not art_payload and cover_art_url:
            try:
                import urllib.request
                req = urllib.request.Request(
                    cover_art_url,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    if resp.status == 200:
                        art_payload = resp.read()
            except Exception as e:
                logger.debug(f"Cover art fetch failed for {cover_art_url}: {e}")

        if art_payload:
            audio.delall("APIC")
            audio.add(APIC(
                encoding=3,
                mime="image/jpeg",
                type=3,  # Cover Front
                desc="Cover",
                data=art_payload,
            ))

        audio.save(str(p), v2_version=3)
        return True
    except Exception as exc:
        logger.warning(f"Failed to tag {p.name}: {exc}")
        return False


def migrate_storage_to_canonical(
    db_conn,
    base_dir: Path,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Safely migrate existing owned files in base_dir to the canonical directory structure:
    Movies/<Movie Name> (<Year>)/<Track> - <Title>.mp3
    Singles/<Artist> - <Title>.mp3

    Preserves user files, updates SQLite records, and leaves ambiguous files in place.
    """
    base_dir = Path(base_dir)
    cursor = db_conn.cursor()

    # Query all owned songs with their movie and track details
    cursor.execute("""
        SELECT
            s.id,
            s.title,
            s.artist,
            s.album,
            s.year,
            s.file_path,
            s.file_size_bytes,
            m.title as movie_title,
            m.year as movie_year,
            sm.track_number
        FROM songs s
        LEFT JOIN song_movies sm ON s.id = sm.song_id
        LEFT JOIN movies m ON sm.movie_id = m.id
        WHERE s.state = 'OWNED' AND s.file_path IS NOT NULL AND s.file_path != ''
    """)
    owned_songs = cursor.fetchall()

    migrated = []
    skipped = []
    errors = []

    for row in owned_songs:
        sid, title, artist, album, year, fp, sz, m_title, m_year, trk_num = row
        current_path = Path(fp)

        # Verify current file exists
        if not current_path.is_file() or not current_path.exists():
            skipped.append({"id": sid, "title": title, "reason": f"File does not exist: {fp}"})
            continue

        # Effective movie metadata
        effective_movie = m_title or (album if album and album.lower() != "singles" else None)
        effective_year = m_year or year

        # Compute deterministic destination path
        canonical_dest = get_canonical_download_path(
            base_dir=base_dir,
            song_title=title,
            artist=artist,
            movie_title=effective_movie,
            movie_year=effective_year,
            track_number=trk_num,
        )

        # Check if already in canonical location
        try:
            if current_path.resolve() == canonical_dest.resolve():
                skipped.append({"id": sid, "title": title, "reason": "Already at canonical location"})
                continue
        except Exception:
            pass

        if dry_run:
            migrated.append({
                "id": sid,
                "title": title,
                "from": str(current_path),
                "to": str(canonical_dest),
                "dry_run": True,
            })
            continue

        try:
            # Create destination folder
            canonical_dest.parent.mkdir(parents=True, exist_ok=True)

            # Safely move file
            shutil.move(str(current_path), str(canonical_dest))

            # Verify destination file
            if not canonical_dest.exists() or canonical_dest.stat().st_size == 0:
                raise RuntimeError(f"Destination file verification failed: {canonical_dest}")

            # Ensure ID3 tags are complete
            tag_mp3_metadata(
                file_path=canonical_dest,
                title=title,
                artist=artist,
                album_or_movie=effective_movie,
                year=effective_year,
                track_number=trk_num,
            )

            # Update database
            new_size = canonical_dest.stat().st_size
            cursor.execute(
                "UPDATE songs SET file_path = ?, file_size_bytes = ? WHERE id = ?",
                (str(canonical_dest), new_size, sid)
            )

            # Update downloads history records referencing old path
            cursor.execute(
                "UPDATE downloads SET output_path = ?, file_size_bytes = ? WHERE song_id = ?",
                (str(canonical_dest), new_size, sid)
            )

            migrated.append({
                "id": sid,
                "title": title,
                "from": str(current_path),
                "to": str(canonical_dest),
                "size": new_size,
            })
            logger.info(f"Successfully migrated song {sid} ('{title}') -> {canonical_dest}")
        except Exception as e:
            logger.error(f"Error migrating song {sid} ('{title}'): {e}")
            errors.append({"id": sid, "title": title, "error": str(e)})

    if not dry_run and migrated:
        db_conn.commit()

    return {
        "migrated_count": len(migrated),
        "skipped_count": len(skipped),
        "error_count": len(errors),
        "migrated": migrated,
        "skipped": skipped,
        "errors": errors,
    }
