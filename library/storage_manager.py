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


def get_primary_artist(artist: Optional[str]) -> str:
    """
    Extract clean primary artist from potentially comma/feat/and separated string.
    Avoids filenames with long comma-separated artist lists.
    """
    if not artist:
        return "Unknown Artist"
    clean = artist.replace("\xa0", " ").strip()
    # Split on commas, slash, semicolon, feat, ft, and, &
    parts = re.split(r"\s*(?:,|/|;|\bfeat\.?|\bft\.?|\band\b|&)\s*", clean, flags=re.IGNORECASE)
    primary = parts[0].strip() if parts else clean
    return sanitize_filename(primary or "Unknown Artist")


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
    - Movie songs: Movies/<Movie Name> (<Year>)/<TrackNum> - <Title>.mp3
    - Standalone singles: Singles/<Primary Artist> - <Title>.mp3
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

        # Clean redundant '(From ...)' matching movie name from the track title
        cleaned_track_title = re.sub(
            r'\s*\((?:From|from)\s+["\']?' + re.escape(safe_movie) + r'["\']?\)',
            '',
            safe_title,
            flags=re.IGNORECASE
        ).strip()
        final_track_title = cleaned_track_title if cleaned_track_title else safe_title

        if track_number and int(track_number) > 0:
            filename = f"{int(track_number):02d} - {final_track_title}.mp3"
        else:
            filename = f"{final_track_title}.mp3"
        return target_dir / filename

    # Standalone Song Rule: Singles/<Artist> - <Title>.mp3
    safe_artist = get_primary_artist(artist)
    target_dir = base_dir / "Singles"
    filename = f"{safe_artist} - {safe_title}.mp3"
    return target_dir / filename


def _get_db_cursor(db):
    if db is None:
        return None
    if hasattr(db, "_conn") and db._conn:
        return db._conn.cursor()
    if hasattr(db, "cursor"):
        return db.cursor()
    return None


def resolve_canonical_path_for_song(
    db,
    base_dir: Path,
    song_id: Optional[int] = None,
    song_title: Optional[str] = None,
    artist: Optional[str] = None,
    album: Optional[str] = None,
    year: Optional[int] = None,
    track_number: Optional[int] = None,
) -> Tuple[Path, Optional[Dict[str, Any]], str]:
    """
    Deterministically resolve canonical path and movie metadata using DB canonical relationships.
    Returns: (canonical_path, movie_dict_or_None, primary_artist)
    """
    base_dir = Path(base_dir)
    effective_movie: Optional[str] = None
    effective_year: Optional[int] = None
    effective_track: Optional[int] = track_number
    movie_info: Optional[Dict[str, Any]] = None
    cur = _get_db_cursor(db)

    # 1. Check direct song_id in DB if available
    if song_id and db:
        if hasattr(db, "get_song_movie_context"):
            m_ctx = db.get_song_movie_context(song_id)
            if m_ctx:
                effective_movie = m_ctx.get("movie_title")
                effective_year = m_ctx.get("movie_year")
                if m_ctx.get("track_number") and not effective_track:
                    effective_track = m_ctx.get("track_number")
                movie_info = m_ctx
        elif cur:
            try:
                cur.execute("""
                    SELECT m.id, m.title, m.year, sm.track_number
                    FROM song_movies sm
                    JOIN movies m ON sm.movie_id = m.id
                    WHERE sm.song_id = ?
                """, (song_id,))
                row = cur.fetchone()
                if row:
                    effective_movie = row[1]
                    effective_year = row[2]
                    if row[3] and not effective_track:
                        effective_track = row[3]
                    movie_info = {"movie_id": row[0], "movie_title": effective_movie, "movie_year": effective_year, "track_number": effective_track}
            except Exception:
                pass

    # 2. Check title for '(From "MovieName")' or '(From MovieName)'
    if not effective_movie and song_title and cur:
        m_match = re.search(r'\(From\s+["\']?([^"\'\)]+)["\']?\)', song_title, re.IGNORECASE)
        if m_match:
            cand_name = m_match.group(1).strip().strip("\"'")
            try:
                cur.execute("SELECT id, title, year FROM movies WHERE LOWER(title) = LOWER(?)", (cand_name,))
                row = cur.fetchone()
                if not row:
                    # Normalized match
                    cand_norm = re.sub(r'[^a-zA-Z0-9]', '', cand_name.lower())
                    cur.execute("SELECT id, title, year FROM movies")
                    for m_row in cur.fetchall():
                        if re.sub(r'[^a-zA-Z0-9]', '', m_row[1].lower()) == cand_norm:
                            row = m_row
                            break
                if row:
                    effective_movie = row[1]
                    effective_year = row[2]
                    movie_info = {"movie_id": row[0], "movie_title": effective_movie, "movie_year": effective_year}
            except Exception:
                pass

    # 3. Check album against movies table
    if not effective_movie and album and album.strip() and album.lower() != "singles" and cur:
        try:
            cur.execute("SELECT id, title, year FROM movies WHERE LOWER(title) = LOWER(?)", (album.strip(),))
            row = cur.fetchone()
            if not row:
                alb_norm = re.sub(r'[^a-zA-Z0-9]', '', album.lower())
                cur.execute("SELECT id, title, year FROM movies")
                for m_row in cur.fetchall():
                    if re.sub(r'[^a-zA-Z0-9]', '', m_row[1].lower()) == alb_norm:
                        row = m_row
                        break
            if row:
                effective_movie = row[1]
                effective_year = row[2]
                movie_info = {"movie_id": row[0], "movie_title": effective_movie, "movie_year": effective_year}
        except Exception:
            pass

    # 4. Check other songs with same title in DB that have movie associations
    if not effective_movie and song_title and cur:
        try:
            clean_t = re.sub(r'\s*\((?:From|from)\s+[^)]+\)', '', song_title).strip()
            clean_t = re.sub(r'\s*-\s*the\s+.*', '', clean_t, flags=re.IGNORECASE).strip()
            norm_t = re.sub(r'[^a-zA-Z0-9]', '', clean_t.lower())
            cur.execute("""
                SELECT m.id, m.title, m.year, sm.track_number
                FROM songs s
                JOIN song_movies sm ON s.id = sm.song_id
                JOIN movies m ON sm.movie_id = m.id
                WHERE s.title_normalized = ?
                LIMIT 1
            """, (norm_t,))
            row = cur.fetchone()
            if row:
                effective_movie = row[1]
                effective_year = row[2]
                if row[3] and not effective_track:
                    effective_track = row[3]
                movie_info = {"movie_id": row[0], "movie_title": effective_movie, "movie_year": effective_year, "track_number": effective_track}
        except Exception:
            pass

    # 5. If still no movie, fallback to song year if known
    if effective_movie and not effective_year and year:
        effective_year = year

    title_to_use = song_title or "Unknown Track"
    dest_path = get_canonical_download_path(
        base_dir=base_dir,
        song_title=title_to_use,
        artist=artist,
        movie_title=effective_movie,
        movie_year=effective_year,
        track_number=effective_track,
    )
    primary_art = get_primary_artist(artist)
    return dest_path, movie_info, primary_art


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
    Safely migrate existing physical files in base_dir to the canonical directory structure:
    Songs New/
    ├── Movies/<Movie Name> (<Year>)/<Track> - <Title>.mp3
    └── Singles/<Primary Artist> - <Title>.mp3

    Preserves user audio, cleans up empty legacy year/bare folders, deletes temporary/0-byte
    artifacts, updates SQLite songs and downloads records, and provides a forensic audit report.
    """
    base_dir = Path(base_dir).resolve()
    cursor = db_conn.cursor()

    # Pre-load movies map
    cursor.execute("SELECT id, title, year FROM movies")
    movies_list = [{"id": r[0], "title": r[1], "year": r[2]} for r in cursor.fetchall()]

    # Pre-load songs map
    cursor.execute("""
        SELECT s.id, s.title, s.artist, s.album, s.year, s.file_path, s.file_size_bytes,
               m.id as movie_id, m.title as movie_title, m.year as movie_year, sm.track_number
        FROM songs s
        LEFT JOIN song_movies sm ON s.id = sm.song_id
        LEFT JOIN movies m ON sm.movie_id = m.id
    """)
    songs_by_fp = {}
    songs_by_id = {}
    for r in cursor.fetchall():
        row_dict = {
            "id": r[0], "title": r[1], "artist": r[2], "album": r[3], "year": r[4],
            "file_path": r[5], "file_size_bytes": r[6], "movie_id": r[7],
            "movie_title": r[8], "movie_year": r[9], "track_number": r[10]
        }
        songs_by_id[r[0]] = row_dict
        if r[5]:
            try:
                songs_by_fp[Path(r[5]).resolve()] = row_dict
            except Exception:
                pass

    total_discovered = 0
    migrated = []
    already_canonical = []
    duplicates_detected = []
    ambiguous_unmapped = []
    temporary_artifacts_removed = []
    files_untouched = []
    errors = []

    # 1. Traverse all physical files
    all_disk_files: List[Path] = []
    for root, dirs, files in os.walk(base_dir):
        for f in files:
            all_disk_files.append(Path(root) / f)

    total_discovered = len(all_disk_files)

    for fp in all_disk_files:
        try:
            rel = fp.relative_to(base_dir)
        except Exception:
            rel = Path(fp.name)

        rel_str = str(rel).replace("\\", "/")

        # 1a. Handle legacy .download_state.json debris in root or legacy subfolders
        if fp.name == ".download_state.json":
            if not rel_str.startswith("Movies/"):
                if not dry_run:
                    try:
                        fp.unlink()
                        temporary_artifacts_removed.append(str(rel))
                    except Exception as e:
                        errors.append({"file": str(rel), "error": str(e)})
                else:
                    temporary_artifacts_removed.append(str(rel))
            continue

        # 1b. Handle 0-byte or temporary .part / .webm files
        size = fp.stat().st_size
        suffix = fp.suffix.lower()
        if size == 0 or suffix in [".part", ".crdownload"]:
            if not dry_run:
                try:
                    fp.unlink()
                    temporary_artifacts_removed.append(str(rel))
                except Exception as e:
                    errors.append({"file": str(rel), "error": str(e)})
            else:
                temporary_artifacts_removed.append(str(rel))
            continue

        # Check if non-audio file
        if suffix not in [".mp3", ".m4a", ".flac", ".wav", ".webm", ".opus", ".aac"]:
            files_untouched.append({"file": str(rel), "reason": f"Non-audio file: {suffix}"})
            continue

        # 1c. Match to canonical song in DB
        matched_song = songs_by_fp.get(fp.resolve())

        # If not matched by exact file_path, match by clean title & artist
        if not matched_song:
            stem = fp.stem
            # Clean stem
            clean_stem = re.sub(r"^\d+\s*-\s*", "", stem).strip()
            clean_title = clean_stem
            cand_artist = None
            if " - " in clean_stem:
                parts = clean_stem.split(" - ")
                cand_artist = parts[0].strip()
                clean_title = parts[-1].strip()

            # Strip (From ...) for lookup
            clean_title_core = re.sub(r'\s*\((?:From|from)\s+[^)]+\)', '', clean_title).strip()
            norm_title = re.sub(r'[^a-zA-Z0-9]', '', clean_title_core.lower())

            # Find matching song in database
            matched_candidates = []
            for s in songs_by_id.values():
                s_norm = re.sub(r'[^a-zA-Z0-9]', '', s["title"].lower())
                if s_norm == norm_title:
                    matched_candidates.append(s)

            if len(matched_candidates) == 1:
                matched_song = matched_candidates[0]
            elif len(matched_candidates) > 1 and cand_artist:
                norm_art = re.sub(r'[^a-zA-Z0-9]', '', cand_artist.lower())
                for c in matched_candidates:
                    c_art = re.sub(r'[^a-zA-Z0-9]', '', (c["artist"] or "").lower())
                    if norm_art in c_art or c_art in norm_art:
                        matched_song = c
                        break
                if not matched_song:
                    matched_song = matched_candidates[0]

        # 1d. Resolve canonical destination path
        if not matched_song:
            # If already inside Movies/ or Singles/, it's already in the canonical directory hierarchy
            if rel_str.startswith("Movies/") or rel_str.startswith("Singles/"):
                already_canonical.append({"id": None, "title": fp.stem, "path": str(rel)})
                continue

            # Check if filename specifies a movie or artist
            dest_path, m_info, p_art = resolve_canonical_path_for_song(
                db=db_conn,
                base_dir=base_dir,
                song_title=clean_title if 'clean_title' in locals() else fp.stem,
                artist=cand_artist if 'cand_artist' in locals() else None,
            )
            ambiguous_unmapped.append({
                "file": str(rel),
                "proposed_destination": str(dest_path.relative_to(base_dir)),
                "reason": "No direct database song record matched"
            })
            continue

        sid = matched_song["id"]
        title = matched_song["title"]
        artist = matched_song["artist"]

        # If already inside canonical Movies/ or Singles/ folder structure
        if rel_str.startswith("Movies/") or rel_str.startswith("Singles/"):
            # Check if folder matches movie name
            already_canonical.append({"id": sid, "title": title, "path": str(rel)})
            continue

        # Resolve using canonical movie relationships
        dest_path, movie_info, primary_artist = resolve_canonical_path_for_song(
            db=db_conn,
            base_dir=base_dir,
            song_id=sid,
            song_title=title,
            artist=artist,
            album=matched_song["album"],
            year=matched_song["year"],
            track_number=matched_song["track_number"]
        )

        # Check if already canonical
        try:
            if fp.resolve() == dest_path.resolve():
                already_canonical.append({"id": sid, "title": title, "path": str(rel)})
                continue
        except Exception:
            pass

        # Check if destination already exists
        if dest_path.exists() and dest_path.stat().st_size > 0:
            # Duplicate physical file exists at canonical destination!
            duplicates_detected.append({
                "id": sid,
                "title": title,
                "source": str(rel),
                "canonical_target": str(dest_path.relative_to(base_dir)),
                "target_size": dest_path.stat().st_size,
                "source_size": size,
            })
            if not dry_run:
                # Update DB to point to canonical destination
                cursor.execute(
                    "UPDATE songs SET file_path = ?, file_size_bytes = ?, state = 'OWNED' WHERE id = ?",
                    (str(dest_path), dest_path.stat().st_size, sid)
                )
                cursor.execute(
                    "UPDATE downloads SET output_path = ?, file_size_bytes = ? WHERE song_id = ?",
                    (str(dest_path), dest_path.stat().st_size, sid)
                )
                # Safely delete duplicate source if sizes match or target is valid
                try:
                    fp.unlink()
                except Exception as e:
                    logger.warning(f"Could not remove duplicate source file {fp}: {e}")
            continue

        if dry_run:
            migrated.append({
                "id": sid,
                "title": title,
                "from": str(rel),
                "to": str(dest_path.relative_to(base_dir)),
                "dry_run": True,
            })
            continue

        try:
            # Create destination folder
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # Safely move file
            shutil.move(str(fp), str(dest_path))

            # Verify destination file
            if not dest_path.exists() or dest_path.stat().st_size == 0:
                raise RuntimeError(f"Destination file verification failed: {dest_path}")

            # Ensure ID3 tags are complete
            tag_mp3_metadata(
                file_path=dest_path,
                title=title,
                artist=artist,
                album_or_movie=movie_info["movie_title"] if movie_info else (matched_song["album"] or title),
                year=movie_info["movie_year"] if movie_info else matched_song["year"],
                track_number=matched_song["track_number"],
            )

            # Update database
            new_size = dest_path.stat().st_size
            cursor.execute(
                "UPDATE songs SET file_path = ?, file_size_bytes = ?, state = 'OWNED' WHERE id = ?",
                (str(dest_path), new_size, sid)
            )
            cursor.execute(
                "UPDATE downloads SET output_path = ?, file_size_bytes = ? WHERE song_id = ?",
                (str(dest_path), new_size, sid)
            )

            migrated.append({
                "id": sid,
                "title": title,
                "from": str(rel),
                "to": str(dest_path.relative_to(base_dir)),
                "size": new_size,
            })
            logger.info(f"Successfully migrated song {sid} ('{title}') -> {dest_path}")
        except Exception as e:
            logger.error(f"Error migrating song {sid} ('{title}'): {e}")
            errors.append({"id": sid, "title": title, "error": str(e)})

    # 2. Clean up empty legacy directories in base_dir
    if not dry_run:
        for root, dirs, files in os.walk(base_dir, topdown=False):
            curr_dir = Path(root)
            if curr_dir == base_dir or curr_dir == (base_dir / "Movies") or curr_dir == (base_dir / "Singles"):
                continue
            # If directory is empty, remove it
            try:
                if not any(curr_dir.iterdir()):
                    curr_dir.rmdir()
                    logger.info(f"Removed empty directory: {curr_dir}")
            except Exception:
                pass

        db_conn.commit()

    return {
        "total_files_discovered": total_discovered,
        "successfully_mapped": len(migrated) + len(already_canonical) + len(duplicates_detected),
        "migrated_count": len(migrated),
        "already_canonical_count": len(already_canonical),
        "duplicates_detected": duplicates_detected,
        "ambiguous_unmapped": ambiguous_unmapped,
        "temporary_artifacts_removed": temporary_artifacts_removed,
        "files_untouched": files_untouched,
        "errors": errors,
        "migrated": migrated,
    }
