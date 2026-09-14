"""
Persistent Import Job Manager orchestrating URL analysis, matching, download execution,
ID3 tagging, and registration in the canonical SQLite library.
"""

import logging
import re
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Callable, Any

from config.settings import settings
from library.database import SQLiteDatabase
from library.canonical import Canonicalizer
from library.models import (
    ImportJob, ImportJobItem, JobStatus, ItemState, LibrarySong, SongState, SongSource
)
from library.url_resolver.detector import UniversalUrlDetector
from library.url_resolver.base import ResolvedContent, TrackMeta, ContentType
from library.providers.registry import ProviderRegistry
from library.providers.base import AudioCandidate, DownloadResult
from library.matching.matcher import TrackMatcher, ConfidenceTier

logger = logging.getLogger(__name__)


class ImportJobManager:
    """
    Coordinates end-to-end URL import jobs with resumability, candidate matching,
    download fallback, and canonical library synchronization.
    """

    def __init__(
        self,
        db: SQLiteDatabase,
        detector: Optional[UniversalUrlDetector] = None,
        provider_registry: Optional[ProviderRegistry] = None,
        matcher: Optional[TrackMatcher] = None,
    ):
        self.db = db
        self.detector = detector or UniversalUrlDetector()
        self.provider_registry = provider_registry or ProviderRegistry()
        self.matcher = matcher or TrackMatcher()
        self._lock = threading.RLock()

    def analyze_url(
        self,
        url: str,
        progress_cb: Optional[Callable[[str, int, int], None]] = None,
    ) -> Tuple[ImportJob, List[ImportJobItem]]:
        """
        Analyze music URL, enumerate tracks, check canonical library for duplicates/owned state,
        and query audio providers for best matching candidates.
        """
        resolved: ResolvedContent = self.detector.resolve(url)
        job_id = f"job-{uuid.uuid4().hex[:8]}"

        job = ImportJob(
            id=job_id,
            url=url,
            platform=resolved.platform.value,
            content_type=resolved.content_type.value,
            title=resolved.title,
            artist=resolved.owner,
            total_tracks=len(resolved.tracks),
            artwork_url=resolved.artwork_url,
            status=JobStatus.READY if resolved.is_valid else JobStatus.FAILED,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        items: List[ImportJobItem] = []
        if not resolved.is_valid:
            # Single error item
            err_item = ImportJobItem(
                job_id=job_id,
                track_index=1,
                title=resolved.title,
                state=ItemState.FAILED,
                error_message=resolved.error_message or "Failed to resolve URL metadata.",
            )
            items.append(err_item)
            self.db.create_import_job(job)
            self.db.add_import_job_items(items)
            return job, items

        total_tracks = len(resolved.tracks)
        for idx, track in enumerate(resolved.tracks, start=1):
            if progress_cb:
                progress_cb(f"Evaluating track {idx}/{total_tracks}: {track.title}", idx, total_tracks)

            # 1. Check if already owned in canonical SQLite database
            canonical_hash = Canonicalizer.compute_hash(
                title=track.title,
                artist=track.artist or "",
                album=track.album or "",
                duration_seconds=track.duration_seconds,
            )
            existing_song = self.db.get_song_by_hash(canonical_hash)

            if existing_song and existing_song.state == SongState.OWNED:
                item = ImportJobItem(
                    job_id=job_id,
                    track_index=idx,
                    title=track.title,
                    artist=track.artist,
                    album=track.album,
                    duration_seconds=track.duration_seconds,
                    state=ItemState.OWNED,
                    match_confidence=1.0,
                    match_explanation="Already in library at high quality",
                    canonical_song_id=existing_song.id,
                )
                items.append(item)
                continue

            # 2. Search candidate audio sources across providers
            scored_candidates = self.provider_registry.search_and_rank_candidates(
                title=track.title,
                artist=track.artist,
                duration_seconds=track.duration_seconds,
                limit_per_provider=2,
            )

            if not scored_candidates:
                item = ImportJobItem(
                    job_id=job_id,
                    track_index=idx,
                    title=track.title,
                    artist=track.artist,
                    album=track.album,
                    duration_seconds=track.duration_seconds,
                    state=ItemState.NO_SOURCE,
                    match_confidence=0.0,
                    match_explanation="No matching audio source found across providers",
                )
            else:
                best_cand, best_score = scored_candidates[0]
                # Automatically mark ready for effortless download without manual review
                item = ImportJobItem(
                    job_id=job_id,
                    track_index=idx,
                    title=track.title,
                    artist=track.artist,
                    album=track.album,
                    duration_seconds=track.duration_seconds,
                    state=ItemState.READY,
                    selected_provider=best_cand.provider_name,
                    selected_source_url=best_cand.source_url,
                    match_confidence=best_score.score,
                    match_explanation=f"{best_cand.title} ({best_score.explanation})",
                )

            items.append(item)


        # Persist to database
        self.db.create_import_job(job)
        self.db.add_import_job_items(items)
        return job, items

    def execute_job(
        self,
        job_id: str,
        item_ids: Optional[List[int]] = None,
        output_dir: Optional[Path] = None,
        progress_cb: Optional[Callable[[int, int, str], None]] = None,
    ) -> Dict[str, int]:
        """
        Execute downloads for job items in READY, NEEDS_REVIEW, or FAILED state.
        Synchronizes downloaded tracks with the canonical SQLite library as OWNED.
        """
        job = self.db.get_import_job(job_id)
        if not job:
            return {"error": 1}

        items = self.db.get_import_job_items(job_id)
        target_items = [
            i for i in items
            if (item_ids is None or i.id in item_ids)
            and i.state in [ItemState.READY, ItemState.NEEDS_REVIEW, ItemState.FAILED]
        ]

        if not target_items:
            return {"completed": 0, "failed": 0, "total": 0}

        self.db.update_import_job_status(job_id, JobStatus.IN_PROGRESS)
        out_dir = output_dir or Path(settings.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        completed_count = 0
        failed_count = 0
        total = len(target_items)

        for idx, item in enumerate(target_items, start=1):
            if progress_cb:
                progress_cb(idx, total, f"Downloading: {item.title}")

            self.db.update_import_job_item_state(item.id, ItemState.DOWNLOADING)

            # Sanitize filename
            clean_name = re.sub(r'[\\/*?:"<>|]', "", f"{item.artist or 'Track'} - {item.title}")[:80].strip()

            # Prepare candidates for download
            candidates: List[AudioCandidate] = []
            if item.selected_source_url and item.selected_provider:
                candidates.append(AudioCandidate(
                    provider_name=item.selected_provider,
                    source_url=item.selected_source_url,
                    title=item.title,
                    uploader=item.artist,
                    duration_seconds=item.duration_seconds,
                ))

            # Query fallback candidates across all providers for automatic failover
            scored = self.provider_registry.search_and_rank_candidates(
                title=item.title,
                artist=item.artist,
                duration_seconds=item.duration_seconds,
                limit_per_provider=2,
            )
            for c, _ in scored:
                if not any(existing.source_url == c.source_url for existing in candidates):
                    candidates.append(c)


            dl_res: DownloadResult = self.provider_registry.download_with_fallback(
                candidates=candidates,
                output_dir=out_dir,
                filename_stem=clean_name,
            )

            if dl_res.success and dl_res.file_path and dl_res.file_path.exists():
                # Apply ID3 tags & artwork
                self._tag_audio_file(
                    file_path=dl_res.file_path,
                    title=item.title,
                    artist=item.artist or "",
                    album=item.album or job.title,
                    track_num=item.track_index,
                    artwork_url=job.artwork_url,
                )

                # Register in canonical SQLite library
                song_id = self._register_in_library(
                    file_path=dl_res.file_path,
                    title=item.title,
                    artist=item.artist or "",
                    album=item.album or job.title,
                    duration_sec=item.duration_seconds,
                )

                self.db.update_import_job_item_state(
                    item_id=item.id,
                    state=ItemState.COMPLETED,
                    canonical_song_id=song_id,
                )
                completed_count += 1
            else:
                self.db.update_import_job_item_state(
                    item_id=item.id,
                    state=ItemState.FAILED,
                    error_message=dl_res.error_message or "Download failed",
                )
                failed_count += 1

        final_status = JobStatus.COMPLETED if failed_count == 0 else JobStatus.READY
        self.db.update_import_job_status(job_id, final_status)
        return {"completed": completed_count, "failed": failed_count, "total": total}

    def _tag_audio_file(
        self,
        file_path: Path,
        title: str,
        artist: str,
        album: str,
        track_num: int,
        artwork_url: Optional[str] = None,
    ) -> None:
        """Write ID3 metadata to the downloaded MP3/audio file using Mutagen."""
        try:
            import mutagen
            from mutagen.easyid3 import EasyID3
            from mutagen.id3 import ID3, APIC

            # Tag standard fields
            try:
                tags = EasyID3(str(file_path))
            except mutagen.id3.ID3NoHeaderError:
                tags = mutagen.File(str(file_path), easy=True)
                if tags is not None:
                    tags.add_tags()

            if tags is not None:
                tags["title"] = title
                if artist:
                    tags["artist"] = artist
                if album:
                    tags["album"] = album
                tags["tracknumber"] = str(track_num)
                tags.save()

            # Embed artwork if available
            if artwork_url and file_path.suffix.lower() == ".mp3":
                try:
                    import requests
                    art_resp = requests.get(artwork_url, timeout=5)
                    if art_resp.status_code == 200:
                        id3 = ID3(str(file_path))
                        id3.add(APIC(
                            encoding=3,
                            mime="image/jpeg",
                            type=3,  # cover front
                            desc="Cover",
                            data=art_resp.content,
                        ))
                        id3.save(v2_version=3)
                except Exception as e:
                    logger.debug(f"Artwork embedding skipped: {e}")

        except Exception as exc:
            logger.warning(f"Failed to tag audio file {file_path.name}: {exc}")

    def _register_in_library(
        self,
        file_path: Path,
        title: str,
        artist: str,
        album: str,
        duration_sec: Optional[int],
    ) -> int:
        """Insert or update song into canonical library as OWNED."""
        norm_title = Canonicalizer.normalize_text(title)
        norm_artist = Canonicalizer.normalize_text(artist)
        norm_album = Canonicalizer.normalize_text(album)
        c_hash = Canonicalizer.compute_hash(title, artist, album, duration_sec)

        file_size = file_path.stat().st_size if file_path.exists() else 0

        song = LibrarySong(
            canonical_hash=c_hash,
            title_normalized=norm_title,
            artist_normalized=norm_artist,
            album_normalized=norm_album,
            duration_seconds=duration_sec,
            title=title,
            artist=artist,
            album=album,
            state=SongState.OWNED,
            quality_kbps=320,
            file_size_bytes=file_size,
            library_location_id=1,
            file_path=str(file_path),
        )

        song_id = self.db.add_song(song)
        self.db.update_song_state(song_id, SongState.OWNED, file_path=str(file_path), quality_kbps=320)
        return song_id
