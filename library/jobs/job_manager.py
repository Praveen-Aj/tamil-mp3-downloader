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
    ImportJob, ImportJobItem, JobStatus, ItemState, LibrarySong, SongState, SongSource,
    Download, DownloadState
)
from library.url_resolver.detector import UniversalUrlDetector
from library.url_resolver.base import ResolvedContent, TrackMeta, ContentType, PlatformType
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
            # When resolution fails, save failed job with 0 tracks and do not fabricate fake song items
            self.db.create_import_job(job)
            return job, items

        total_tracks = len(resolved.tracks)
        seen_canonical_hashes: Dict[str, int] = {}
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

            is_playlist_duplicate = canonical_hash in seen_canonical_hashes
            earlier_idx = seen_canonical_hashes.get(canonical_hash)
            if not is_playlist_duplicate:
                seen_canonical_hashes[canonical_hash] = idx

            if existing_song and existing_song.state == SongState.OWNED:
                expl = "Already in library"
                if is_playlist_duplicate:
                    expl += f" (Duplicate of track #{earlier_idx} in playlist)"
                item = ImportJobItem(
                    job_id=job_id,
                    track_index=idx,
                    title=track.title,
                    artist=track.artist,
                    album=track.album,
                    duration_seconds=track.duration_seconds,
                    state=ItemState.OWNED,
                    match_confidence=1.0,
                    match_explanation=expl,
                    canonical_song_id=existing_song.id,
                )
                items.append(item)
                continue

            if is_playlist_duplicate:
                # Same canonical song appears multiple times in playlist
                item = ImportJobItem(
                    job_id=job_id,
                    track_index=idx,
                    title=track.title,
                    artist=track.artist,
                    album=track.album,
                    duration_seconds=track.duration_seconds,
                    state=ItemState.READY,
                    match_confidence=1.0,
                    match_explanation=f"Reuses track #{earlier_idx} in playlist (duplicate)",
                    canonical_song_id=existing_song.id if existing_song else None,
                )
                items.append(item)
                continue

            # 2. Check for direct audio URL
            is_direct_audio = resolved.platform == PlatformType.DIRECT_AUDIO or (
                track.source_identifier and any(
                    track.source_identifier.split("?")[0].lower().endswith(ext)
                    for ext in [".mp3", ".m4a", ".flac", ".wav", ".aac", ".ogg", ".opus"]
                )
            )
            if is_direct_audio:
                item = ImportJobItem(
                    job_id=job_id,
                    track_index=idx,
                    title=track.title,
                    artist=track.artist,
                    album=track.album or resolved.title,
                    duration_seconds=track.duration_seconds,
                    state=ItemState.READY,
                    selected_provider="direct_http",
                    selected_source_url=track.source_identifier or url,
                    match_confidence=1.0,
                    match_explanation="Direct audio source",
                )
                items.append(item)
                continue

            # 3. Search candidate audio sources across providers
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
        persisted_items = self.db.get_import_job_items(job.id)
        return job, persisted_items or items

    def execute_job(
        self,
        job_id: str,
        item_ids: Optional[List[int]] = None,
        output_dir: Optional[Path] = None,
        progress_cb: Optional[Callable[[int, int, str], None]] = None,
        item_progress_cb: Optional[Callable[[int, int, str, float, str], None]] = None,
    ) -> Dict[str, int]:
        """
        Execute downloads for job items in READY, NEEDS_REVIEW, or FAILED state.
        Synchronizes downloaded tracks with the canonical SQLite library as OWNED
        and creates unified Download tracking records.
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

            # Check if canonical song is already OWNED and physical file exists
            c_hash = Canonicalizer.compute_hash(item.title, item.artist or "", item.album or "", item.duration_seconds)
            existing_song = self.db.get_song_by_hash(c_hash) or (self.db.get_song(item.canonical_song_id) if item.canonical_song_id else None)
            if existing_song and existing_song.state == SongState.OWNED and existing_song.file_path:
                p = Path(existing_song.file_path)
                if not p.is_absolute():
                    p = (out_dir.parent / p).resolve() if not (Path.cwd() / p).exists() else (Path.cwd() / p).resolve()
                if p.is_file() and p.exists() and p.stat().st_size > 0:
                    self.db.update_import_job_item_state(
                        item_id=item.id,
                        state=ItemState.COMPLETED,
                        canonical_song_id=existing_song.id,
                    )
                    completed_count += 1
                    if progress_cb:
                        progress_cb(idx, total, f"Reused existing file: {item.title}")
                    continue

            # Ensure canonical song record exists in DB
            if not existing_song:
                norm_title = Canonicalizer.normalize_text(item.title)
                norm_artist = Canonicalizer.normalize_text(item.artist or "")
                norm_album = Canonicalizer.normalize_text(item.album or job.title)
                song_obj = LibrarySong(
                    canonical_hash=c_hash,
                    title_normalized=norm_title,
                    artist_normalized=norm_artist,
                    album_normalized=norm_album,
                    duration_seconds=item.duration_seconds,
                    title=item.title,
                    artist=item.artist or "",
                    album=item.album or job.title,
                    state=SongState.DOWNLOADING,
                    library_location_id=1,
                )
                song_id = self.db.add_song(song_obj)
            else:
                song_id = existing_song.id
                self.db.update_song_state(song_id, SongState.DOWNLOADING)

            # Ensure a valid song_source exists in database for this song
            source_id = None
            sources = self.db.get_sources_for_song(song_id)
            if sources:
                source_id = sources[0].id
            else:
                source_obj = SongSource(
                    song_id=song_id,
                    source_name=item.selected_provider or "direct_http",
                    source_url=item.selected_source_url or f"item:{item.id}",
                    quality_kbps=getattr(item, "quality_kbps", 320) or 320,
                    is_available=True,
                    reliability_score=1.0,
                )
                source_id = self.db.add_source(source_obj)

            # Create unified Download tracking record in database
            now_iso = datetime.now().isoformat()
            dl_record = Download(
                song_id=song_id,
                song_source_id=source_id,
                planned_at=now_iso,
                queued_at=now_iso,
                started_at=now_iso,
                state=DownloadState.DOWNLOADING,
                library_location_id=1,
            )
            dl_id = self.db.add_download(dl_record)
            item.download_id = dl_id
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

            def _item_hook(ratio: float, msg: str):
                if item_progress_cb:
                    item_progress_cb(dl_id, song_id, item.title, ratio, msg)

            dl_res: DownloadResult = self.provider_registry.download_with_fallback(
                candidates=candidates,
                output_dir=out_dir,
                filename_stem=clean_name,
                progress_cb=_item_hook,
            )

            if dl_res.success and dl_res.file_path and dl_res.file_path.exists():
                file_size = dl_res.size_bytes or dl_res.file_path.stat().st_size
                # Apply ID3 tags & artwork
                self._tag_audio_file(
                    file_path=dl_res.file_path,
                    title=item.title,
                    artist=item.artist or "",
                    album=item.album or job.title,
                    track_num=item.track_index,
                    artwork_url=job.artwork_url,
                )

                # Register in canonical SQLite library as OWNED
                self._register_in_library(
                    file_path=dl_res.file_path,
                    title=item.title,
                    artist=item.artist or "",
                    album=item.album or job.title,
                    duration_sec=item.duration_seconds,
                )

                # Update Download record
                self.db.update_download_completed(
                    download_id=dl_id,
                    output_path=str(dl_res.file_path),
                    file_size_bytes=file_size,
                    download_speed_bps=None,
                    was_upgrade=False,
                    previous_file_path=None,
                    previous_quality_kbps=None,
                    library_location_id=1,
                )

                self.db.update_import_job_item_state(
                    item_id=item.id,
                    state=ItemState.COMPLETED,
                    canonical_song_id=song_id,
                )
                completed_count += 1
                if item_progress_cb:
                    item_progress_cb(dl_id, song_id, item.title, 1.0, "Downloaded · 320 kbps MP3 · Ready to play")
            else:
                err = dl_res.error_message or "Download failed"
                self.db.update_download_state(dl_id, state=DownloadState.FAILED, error_message=err)
                self.db.update_song_state(song_id, state=SongState.FAILED)
                self.db.update_import_job_item_state(
                    item_id=item.id,
                    state=ItemState.FAILED,
                    error_message=err,
                )
                failed_count += 1
                if item_progress_cb:
                    item_progress_cb(dl_id, song_id, item.title, 0.0, err)

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
        self.db.update_song_file(song_id, file_path=str(file_path), file_size_bytes=file_size, quality_kbps=320)
        return song_id
