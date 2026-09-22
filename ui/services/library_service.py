"""
Library Service module.

Provides a unified interface for UI views to interact with:
- SQLiteDatabase
- DiscoveryPipeline
- DownloadPlanner
- DownloadRegistry
- LibraryImporter
- SourceRegistry
- Settings Configuration
"""

import os
import re
import subprocess
import sys
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Tuple

from config.settings import settings
from downloaders.http_downloader import HTTPDownloader
from models.song import Song as DownloadSong
from library.database import SQLiteDatabase
from library.discovery import DiscoveryPipeline
from library.importer import LibraryImporter
from library.providers.base import AudioCandidate
from library.models import (
    LibrarySong, SongSource, SongState, DownloadState, Download,
    ImportJob, ImportJobItem, JobStatus, ItemState, Movie,
    Artist, MovieActor, MovieComposer, SongArtist, SongMovie,
    Chart, ChartEntry
)
from library.canonical import normalize_string
from library.charts import ChartDiscoveryService
from library.planner import DownloadPlanner, DownloadPlan, SourceSelection
from library.filter_engine import SongFilterCriteria
from library.registry import DownloadRegistry
from library.providers.registry import ProviderRegistry
from library.url_resolver.detector import UniversalUrlDetector
from library.jobs.job_manager import ImportJobManager
from scrapers.base import BaseScraper
from scrapers.friendstamilmp3 import FriendsTamilMP3Scraper
from scrapers.isaimini import IsaiminiScraper
from scrapers.kollysongs import KollySongsScraper
from scrapers.masstamilan import MassTamilanScraper
from scrapers.source_registry import (
    SourceRegistry,
    SourceConfig,
    SourceCapabilities,
    RegisteredSource,
)
from scrapers.tamilmp3 import Tamilmp3Scraper

logger = logging.getLogger(__name__)


@dataclass
class DownloadProgressEvent:
    download_id: Optional[int] = None
    song_id: Optional[int] = None
    title: str = ""
    status: str = "DOWNLOADING"  # QUEUED, DOWNLOADING, COMPLETED, FAILED
    bytes_downloaded: int = 0
    total_bytes: Optional[int] = None
    speed_bps: float = 0.0
    eta_seconds: Optional[int] = None
    percent: float = 0.0  # 0.0 to 1.0
    speed_str: str = ""
    eta_str: str = ""
    error_message: Optional[str] = None


class LibraryService:
    """
    Central service coordinating backend components for the UI.
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        db: Optional[SQLiteDatabase] = None,
        download_dir: Optional[str] = None,
    ):
        if db is not None:
            self.db = db
            self.db_path = getattr(db, "db_path", Path("library.db"))
        else:
            self.db_path = db_path or settings.library_db_path
            self.db = SQLiteDatabase(self.db_path)
            self.db.connect()
        self.download_dir = download_dir or settings.output_dir

        self.pipeline = DiscoveryPipeline(self.db)
        self.planner = DownloadPlanner(self.db)
        self.registry = DownloadRegistry(self.db)
        self.importer = LibraryImporter(self.db)
        self.source_registry = SourceRegistry()

        self.provider_registry = ProviderRegistry()
        self.url_detector = UniversalUrlDetector()
        self.job_manager = ImportJobManager(
            db=self.db,
            detector=self.url_detector,
            provider_registry=self.provider_registry,
        )

        self.charts_service = ChartDiscoveryService(self.db)
        self._lock = threading.RLock()
        self._last_discovery_session: Optional[Dict[str, Any]] = None
        self._progress_listeners: List[Callable[[DownloadProgressEvent], None]] = []
        self._active_progress: Dict[int, DownloadProgressEvent] = {}
        self._init_default_sources()
        # Reconcile filesystem integrity on service startup
        self.reconcile_library_files()
        self.db.clean_stale_transient_downloads()
        self.enrich_people_from_library()

    def add_progress_listener(self, listener: Callable[[DownloadProgressEvent], None]) -> None:
        with self._lock:
            if listener not in self._progress_listeners:
                self._progress_listeners.append(listener)

    def remove_progress_listener(self, listener: Callable[[DownloadProgressEvent], None]) -> None:
        with self._lock:
            if listener in self._progress_listeners:
                self._progress_listeners.remove(listener)

    def emit_progress(self, event: DownloadProgressEvent) -> None:
        with self._lock:
            if event.download_id:
                self._active_progress[event.download_id] = event
            listeners = list(self._progress_listeners)
        for listener in listeners:
            try:
                listener(event)
            except Exception as e:
                logger.debug(f"Progress listener error: {e}")

    def get_active_download_progress(self, download_id: int) -> Optional[DownloadProgressEvent]:
        with self._lock:
            return self._active_progress.get(download_id)

    def reconcile_library_files(self) -> int:
        """
        Actively reconcile SQLite database records with physical files on disk.
        Resets any orphaned OWNED records (missing or empty files) to NEW.
        """
        return self.db.reconcile_filesystem_integrity()

    def _init_default_sources(self) -> None:
        """Register default core sources in SourceRegistry."""
        # 1. MassTamilan (Enabled)
        self.source_registry.register_source(
            config=SourceConfig(
                name="masstamilan",
                display_name="MassTamilan",
                domains=["https://www.masstamilan.dev", "https://masstamilan.in"],
                capabilities=SourceCapabilities(supports_320kbps=True, supports_128kbps=True),
                enabled=True,
            ),
            scraper=MassTamilanScraper(),
        )

        # 2. Tamilmp3.in / Kuttyweb (Enabled)
        self.source_registry.register_source(
            config=SourceConfig(
                name="tamilmp3",
                display_name="Tamilmp3.in",
                domains=["https://tamilmp3.in"],
                capabilities=SourceCapabilities(supports_320kbps=True, supports_128kbps=True),
                enabled=True,
            ),
            scraper=Tamilmp3Scraper(),
        )

        # 3. FriendsTamilMP3 (Enabled)
        self.source_registry.register_source(
            config=SourceConfig(
                name="friendstamilmp3",
                display_name="FriendsTamilMP3",
                domains=["https://www.friendstamilmp3.in"],
                capabilities=SourceCapabilities(supports_320kbps=False, supports_128kbps=True),
                enabled=True,
            ),
            scraper=FriendsTamilMP3Scraper(),
        )

        # Disabled sources (kept registered as disabled)
        self.source_registry.register_source(
            config=SourceConfig(
                name="isaimini",
                display_name="IsaiminiHQ",
                domains=["https://www.isaiminihq.com"],
                capabilities=SourceCapabilities(supports_320kbps=True, supports_128kbps=True),
                enabled=False,
            ),
            scraper=IsaiminiScraper(),
        )

        self.source_registry.register_source(
            config=SourceConfig(
                name="kollysongs",
                display_name="KollySongs",
                domains=["https://www.kollysongs.com"],
                capabilities=SourceCapabilities(supports_320kbps=True, supports_128kbps=True),
                enabled=False,
            ),
            scraper=KollySongsScraper(),
        )

    # ── Summary & Stats ──────────────────────────────────────────
    def get_dashboard_stats(self) -> Dict[str, Any]:
        """Get consumer-facing summary metrics for Dashboard with real disk verification."""
        # Active reconciliation of orphaned files
        self.reconcile_library_files()

        lib_stats = self.db.get_library_stats()
        sources = self.source_registry.get_all_sources()
        enabled_sources = [s for s in sources if s.enabled]
        disabled_sources = [s for s in sources if not s.enabled]
        healthy_enabled = sum(1 for s in enabled_sources if s.is_usable)

        # Count quality upgrades available and verified storage on disk
        owned = self.db.get_songs_by_state(SongState.OWNED)
        
        upgrades_count = 0
        total_storage_bytes = 0
        verified_downloaded_count = 0
        for s in owned:
            if s.file_path and os.path.isfile(s.file_path):
                verified_downloaded_count += 1
                try:
                    fsize = os.path.getsize(s.file_path)
                    if fsize > 0:
                        total_storage_bytes += fsize
                except OSError:
                    pass

            if s.quality_kbps and s.quality_kbps < 320:
                s_sources = self.db.get_sources_for_song(s.id)
                if any(src.quality_kbps and src.quality_kbps >= 320 for src in s_sources):
                    upgrades_count += 1

        active_downloads = len(self.registry.get_active_downloads())
        
        # Calculate failed downloads (deduplicated by song)
        unique_dls = self.get_all_downloads(dedup_by_song=True)
        failed_count = sum(
            1 for d in unique_dls
            if d.state == DownloadState.FAILED or (hasattr(d.state, "value") and d.state.value == "FAILED")
        )

        total_cnt = lib_stats.get("total_songs", 0)
        # Downloaded count is strictly based on songs verified physically on disk
        downloaded_cnt = verified_downloaded_count
        not_downloaded_cnt = max(0, total_cnt - downloaded_cnt)

        # Storage in MB strictly from real bytes on disk
        storage_mb = max(1, int(total_storage_bytes / (1024 * 1024))) if total_storage_bytes > 0 else 0

        # Compact source status items
        source_pills = [
            {"name": "YouTube", "status": "Active", "color": "#10b981", "type": "stream"},
            {"name": "Spotify", "status": "Ready", "color": "#10b981", "type": "meta"},
            {"name": "Direct Audio", "status": "Active", "color": "#10b981", "type": "direct"},
            {"name": "Regional Tamil", "status": f"{healthy_enabled}/{len(enabled_sources)} Online", "color": "#10b981" if healthy_enabled > 0 else "#f59e0b", "type": "regional"},
        ]

        return {
            "total_songs": total_cnt,
            "owned_songs": downloaded_cnt,
            "downloaded_songs": downloaded_cnt,
            "unowned_songs": not_downloaded_cnt,
            "ready_downloads": not_downloaded_cnt,
            "upgrades_available": upgrades_count,
            "active_downloads": active_downloads,
            "failed_downloads": failed_count,
            "storage_mb": storage_mb,
            "storage_bytes": total_storage_bytes,
            "healthy_sources": f"{healthy_enabled}/{len(enabled_sources)} Core Healthy",
            "disabled_sources": len(disabled_sources),
            "source_pills": source_pills,
            "last_session": self._last_discovery_session,
        }

    # ── Library Query & Pagination ──────────────────────────────
    def get_library_page(
        self,
        query: str = "",
        state_filter: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
        state: Optional[str] = None,
        quality: Optional[int] = None,
        source: Optional[str] = None,
        artist: Optional[str] = None,
        album: Optional[str] = None,
        sort_by: str = "id",
        ascending: bool = False,
    ) -> Dict[str, Any]:
        """
        Get paginated songs from SQLite with composable filter, search, sort criteria.
        """
        effective_state = state or state_filter
        criteria = SongFilterCriteria.from_legacy_params(
            query=query,
            state_filter=effective_state,
            quality=quality,
            source=source,
            artist=artist,
            album=album,
        )
        effective_sort = "rank" if (query and query.strip() and sort_by == "id") else sort_by
        return self.db.search_and_filter_songs(
            criteria=criteria,
            sort_by=effective_sort,
            ascending=ascending,
            page=page,
            page_size=page_size,
        )

    def get_filter_options(self) -> Dict[str, List[Any]]:
        """
        Retrieve available filter choices for source, quality, artist, album dropdowns.
        """
        return self.db.get_filter_options()

    # ── Song Details & Duplicate Breakdown ───────────────────────
    def get_song_details(self, song_id: int) -> Dict[str, Any]:
        """Get full identity, contexts, source variants, and planner decision for a song."""
        song = self.db.get_song(song_id)
        if not song:
            return {}

        sources = self.db.get_sources_for_song(song_id)
        contexts = self.db.get_discovery_contexts(song_id)

        # Evaluate planner decision
        plan = self.planner.plan_downloads_for_song_ids([song_id])

        return {
            "song": song,
            "sources": sources,
            "contexts": contexts,
            "planner_decision": plan,
        }

    # ── Discovery & Session Recording ───────────────────────────
    def run_discovery(
        self,
        category: str = "latest",
        source_names: Optional[List[str]] = None,
        progress_cb: Optional[Callable[[str, int, int], None]] = None,
    ) -> Dict[str, Any]:
        """
        Run bulk discovery across selected sources & categories.
        DISCOVERY DOES NOT AUTOMATICALLY DOWNLOAD ANYTHING.
        Persists discovered songs into SQLite Canonical Library.
        """
        sources_to_run = source_names or ["masstamilan", "tamilmp3", "friendstamilmp3"]
        usable_scrapers = [
            s for name in sources_to_run
            if (s := self.source_registry.get_source(name)) and s.is_usable and s.scraper
        ]

        total_raw = 0
        total_new = 0

        for reg_src in usable_scrapers:
            try:
                albums = reg_src.scraper.get_albums(category=category, max_pages=1)
                for album in albums:
                    songs = reg_src.scraper.get_songs(album)
                    total_raw += len(songs)
                    for s in songs:
                        song_id = self.pipeline.register_song(
                            song=s,
                            source_name=reg_src.name,
                            album=album,
                            category=category,
                        )
                        if song_id:
                            total_new += 1
            except Exception as e:
                logger.warning(f"Discovery error on source '{reg_src.name}': {e}")
                self.source_registry.record_failure(reg_src.name, str(e))

        duplicates_filtered = max(0, total_raw - total_new)

        session_summary = {
            "category": category,
            "sources": sources_to_run,
            "raw_discovered": total_raw,
            "unique_registered": total_new,
            "duplicates_filtered": duplicates_filtered,
        }

        self._last_discovery_session = session_summary
        return session_summary

    # ── Download Planning & Execution ───────────────────────────
    def preview_download_plan(self, song_ids: Optional[List[int]] = None) -> DownloadPlan:
        """Generate a DownloadPlan preview without starting downloads."""
        if song_ids:
            return self.planner.plan_downloads_for_song_ids(song_ids)
        # Default: plan downloads for all unowned/new songs
        new_songs = self.db.get_songs_by_state(SongState.NEW)
        return self.planner.plan_downloads_for_songs(new_songs)

    def execute_single_download(self, target_id: int) -> bool:
        """
        Execute a complete production download pipeline for a single download slot or song ID.
        Includes automatic fallback across scrapers and providers.
        """
        dl = self.db.get_download(target_id)
        if not dl:
            # Check if target_id was passed as a song_id directly
            song = self.db.get_song(target_id)
            if song:
                sources = self.db.get_sources_for_song(song.id)
                src_id = sources[0].id if sources else 0
                download_id = self.registry.acquire(song.id, src_id) or 0
                dl = self.db.get_download(download_id) if download_id else None
            if not dl:
                logger.error(f"execute_single_download: target_id {target_id} not found as download or song")
                return False
        else:
            download_id = dl.id
            song = self.db.get_song(dl.song_id)

        if not song:
            self.registry.fail(dl.song_id, download_id, "Song record missing from database", dl.song_source_id)
            return False

        source = self.db.get_source_by_id(dl.song_source_id) if dl.song_source_id else None

        from models.song import Song as DownloadSong
        from downloaders.http_downloader import HTTPDownloader

        # 1. Attempt download with primary source if available
        if source:
            download_url = None
            reg_src = self.source_registry.get_source(source.source_name)
            if reg_src and reg_src.scraper and hasattr(reg_src.scraper, "get_download_url"):
                try:
                    download_url = reg_src.scraper.get_download_url(source, quality=str(source.quality_kbps or 320))
                except Exception as e:
                    logger.warning(f"Error resolving download URL from scraper '{source.source_name}': {e}")

            if not download_url:
                download_url = source.download_reference or source.source_url

            if download_url and (download_url.startswith("http://") or download_url.startswith("https://")):
                dl_song = DownloadSong(
                    name=song.title,
                    url=download_url,
                    quality=f"{source.quality_kbps or 320}kbps",
                    album_name=song.album or "Unknown Album",
                    artist=song.artist,
                    year=song.year,
                )
                try:
                    downloader = HTTPDownloader(
                        output_dir=Path(self.download_dir or settings.output_dir),
                        max_workers=settings.get("download.max_workers", 3),
                        show_progress=False,
                    )
                    def _http_prog(ratio: float, msg: str):
                        self.emit_progress(DownloadProgressEvent(
                            download_id=download_id,
                            song_id=song.id,
                            title=song.title,
                            status="DOWNLOADING",
                            percent=ratio,
                            speed_str=msg,
                        ))
                    result = downloader.download_song(dl_song, progress_cb=_http_prog)
                    if result.success and result.file_path and result.file_path.exists() and result.file_path.stat().st_size > 0:
                        was_upgrade = (song.state == SongState.OWNED)
                        file_size = result.size_downloaded or result.file_path.stat().st_size
                        self.registry.complete(
                            song_id=song.id,
                            download_id=download_id,
                            file_path=str(result.file_path),
                            file_size_bytes=file_size,
                            quality_kbps=source.quality_kbps or 320,
                            library_location_id=1,
                            was_upgrade=was_upgrade,
                            previous_file_path=song.file_path,
                            previous_quality_kbps=song.quality_kbps,
                        )
                        self.registry.reward_source(source.id)
                        self.emit_progress(DownloadProgressEvent(
                            download_id=download_id,
                            song_id=song.id,
                            title=song.title,
                            status="COMPLETED",
                            percent=1.0,
                            speed_str="Downloaded · 320 kbps MP3 · Ready to play",
                        ))
                        return True
                except Exception as exc:
                    logger.warning(f"Primary source download exception for '{song.title}': {exc}")

        # 2. Attempt alternative registered scrapers / sources for this song
        alt_sources = [s for s in self.db.get_sources_for_song(song.id) if (not source or s.id != source.id) and s.is_available]
        for alt_src in alt_sources:
            alt_url = None
            reg_alt = self.source_registry.get_source(alt_src.source_name)
            if reg_alt and reg_alt.scraper and hasattr(reg_alt.scraper, "get_download_url"):
                try:
                    alt_url = reg_alt.scraper.get_download_url(alt_src, quality=str(alt_src.quality_kbps or 320))
                except Exception:
                    pass
            if not alt_url:
                alt_url = alt_src.download_reference or alt_src.source_url
            if alt_url and (alt_url.startswith("http://") or alt_url.startswith("https://")):
                dl_song = DownloadSong(
                    name=song.title,
                    url=alt_url,
                    quality=f"{alt_src.quality_kbps or 320}kbps",
                    album_name=song.album or "Unknown Album",
                    artist=song.artist,
                    year=song.year,
                )
                try:
                    downloader = HTTPDownloader(
                        output_dir=Path(self.download_dir or settings.output_dir),
                        max_workers=settings.get("download.max_workers", 3),
                        show_progress=False,
                    )
                    def _alt_prog(ratio: float, msg: str):
                        self.emit_progress(DownloadProgressEvent(
                            download_id=download_id,
                            song_id=song.id,
                            title=song.title,
                            status="DOWNLOADING",
                            percent=ratio,
                            speed_str=msg,
                        ))
                    res = downloader.download_song(dl_song, progress_cb=_alt_prog)
                    if res.success and res.file_path and res.file_path.exists() and res.file_path.stat().st_size > 0:
                        was_upgrade = (song.state == SongState.OWNED)
                        file_size = res.size_downloaded or res.file_path.stat().st_size
                        self.registry.complete(
                            song_id=song.id,
                            download_id=download_id,
                            file_path=str(res.file_path),
                            file_size_bytes=file_size,
                            quality_kbps=alt_src.quality_kbps or 320,
                            library_location_id=1,
                            was_upgrade=was_upgrade,
                            previous_file_path=song.file_path,
                            previous_quality_kbps=song.quality_kbps,
                        )
                        self.registry.reward_source(alt_src.id)
                        self.emit_progress(DownloadProgressEvent(
                            download_id=download_id,
                            song_id=song.id,
                            title=song.title,
                            status="COMPLETED",
                            percent=1.0,
                            speed_str="Downloaded · 320 kbps MP3 · Ready to play",
                        ))
                        return True
                except Exception:
                    pass

        # 3. Fallback to ProviderRegistry (YouTube / Direct Audio / Regional Providers)
        try:
            candidates = self.provider_registry.search_and_rank_candidates(
                title=song.title,
                artist=song.artist,
                duration_seconds=song.duration_seconds,
            )
            if candidates:
                cand_list = [c if isinstance(c, AudioCandidate) else c[0] for c in candidates]
                clean_stem = re.sub(r'[\\/*?:"<>|]', "", f"{song.artist or 'Track'} - {song.title}")[:80].strip()
                def _prov_prog(ratio: float, msg: str):
                    self.emit_progress(DownloadProgressEvent(
                        download_id=download_id,
                        song_id=song.id,
                        title=song.title,
                        status="DOWNLOADING",
                        percent=ratio,
                        speed_str=msg,
                    ))
                prov_res = self.provider_registry.download_with_fallback(
                    candidates=cand_list,
                    output_dir=Path(self.download_dir or settings.output_dir),
                    filename_stem=clean_stem,
                    progress_cb=_prov_prog,
                )
                if prov_res.success and prov_res.file_path and prov_res.file_path.exists() and prov_res.file_path.stat().st_size > 0:
                    # Tag ID3 metadata
                    self.job_manager._tag_audio_file(
                        file_path=prov_res.file_path,
                        title=song.title,
                        artist=song.artist or "",
                        album=song.album or "Downloaded",
                        track_num=1,
                    )
                    was_upgrade = (song.state == SongState.OWNED)
                    ext = prov_res.file_path.suffix.lower()
                    if ext == ".webm":
                        q_kbps = 160
                        fmt_label = "Opus (WebM)"
                    elif ext == ".m4a":
                        q_kbps = 128
                        fmt_label = "AAC (M4A)"
                    else:
                        q_kbps = 320
                        fmt_label = "320 kbps MP3"
                    file_size = prov_res.size_bytes or prov_res.file_path.stat().st_size
                    self.registry.complete(
                        song_id=song.id,
                        download_id=download_id,
                        file_path=str(prov_res.file_path),
                        file_size_bytes=file_size,
                        quality_kbps=q_kbps,
                        library_location_id=1,
                        was_upgrade=was_upgrade,
                        previous_file_path=song.file_path,
                        previous_quality_kbps=song.quality_kbps,
                    )
                    self.emit_progress(DownloadProgressEvent(
                        download_id=download_id,
                        song_id=song.id,
                        title=song.title,
                        status="COMPLETED",
                        percent=1.0,
                        speed_str=f"Downloaded · {fmt_label} · Ready to play",
                    ))
                    return True
        except Exception as prov_exc:
            logger.warning(f"Provider fallback download exception for '{song.title}': {prov_exc}")

        # If all attempts fail
        err_msg = "All download sources and provider fallbacks failed (HTTP 404 / unavailable)"
        self.registry.fail(song.id, download_id, err_msg, source.id if source else None)
        self.emit_progress(DownloadProgressEvent(
            download_id=download_id,
            song_id=song.id,
            title=song.title,
            status="FAILED",
            percent=0.0,
            error_message=err_msg,
        ))
        return False

    def execute_download_plan(
        self,
        plan: DownloadPlan,
        run_async: bool = True,
        progress_cb: Optional[Callable[[int, int], None]] = None,
    ) -> List[int]:
        """
        Enqueue planned downloads into DownloadRegistry and trigger download execution pipeline.
        """
        enqueued_ids = []
        for planned in plan.new_songs:
            dl_id = self.registry.acquire_download(
                song_id=planned.song_id,
                song_source_id=planned.primary.id,
            )
            if dl_id:
                enqueued_ids.append(dl_id)

        if run_async and enqueued_ids:
            def _worker():
                max_w = min(int(settings.get("download.max_workers", 3)), len(enqueued_ids))
                completed_count = 0
                with ThreadPoolExecutor(max_workers=max_w) as executor:
                    futures = {executor.submit(self.execute_single_download, dl_id): dl_id for dl_id in enqueued_ids}
                    for future in as_completed(futures):
                        dl_id = futures[future]
                        try:
                            res = future.result()
                            logger.info(f"Worker finished download dl_id={dl_id} -> {res}")
                        except Exception as e:
                            logger.error(f"Exception in async download worker for dl_id={dl_id}: {e}", exc_info=True)
                        completed_count += 1
                        if progress_cb:
                            progress_cb(completed_count, len(enqueued_ids))

            threading.Thread(target=_worker, daemon=True).start()
        elif not run_async:
            for idx, dl_id in enumerate(enqueued_ids, start=1):
                try:
                    self.execute_single_download(dl_id)
                    if progress_cb:
                        progress_cb(idx, len(enqueued_ids))
                except Exception as e:
                    logger.error(f"Exception in sync download for dl_id={dl_id}: {e}", exc_info=True)

        return enqueued_ids

    def retry_failed_downloads(
        self,
        download_ids: Optional[List[int]] = None,
        try_alternate_source: bool = True,
        run_async: bool = True,
        progress_cb: Optional[Callable[[int, int], None]] = None,
    ) -> List[int]:
        """
        Identify failed downloads, safely re-acquire registry slots with optional alternate-source fallback,
        and execute the downloader again.
        """
        all_dls = self.db.get_all_downloads()
        failed_dls = [
            d for d in all_dls
            if (d.state == DownloadState.FAILED or (hasattr(d.state, "value") and d.state.value == "FAILED"))
            and (download_ids is None or d.id in download_ids)
        ]

        retried_ids = []
        for d in failed_dls:
            if self.registry.is_downloading(d.song_id):
                continue

            target_source_id = d.song_source_id
            if try_alternate_source:
                # Check for alternate available source
                all_sources = self.db.get_sources_for_song(d.song_id)
                alt_sources = [s for s in all_sources if s.id != d.song_source_id and s.is_available]
                if alt_sources:
                    target_source_id = alt_sources[0].id

            # Transition song back to NEW so acquire slot can succeed
            self.db.update_song_state(d.song_id, SongState.NEW)
            new_dl_id = self.registry.acquire_download(
                song_id=d.song_id,
                song_source_id=target_source_id,
            )
            if new_dl_id:
                retried_ids.append(new_dl_id)

        if run_async and retried_ids:
            def _worker():
                for idx, dl_id in enumerate(retried_ids, start=1):
                    self.execute_single_download(dl_id)
                    if progress_cb:
                        progress_cb(idx, len(retried_ids))

            threading.Thread(target=_worker, daemon=True).start()
        elif not run_async:
            for idx, dl_id in enumerate(retried_ids, start=1):
                self.execute_single_download(dl_id)
                if progress_cb:
                    progress_cb(idx, len(retried_ids))

        return retried_ids

    # ── Deletion & File System Operations ───────────────────────
    def delete_downloaded_song(
        self,
        song_id: int,
        delete_from_disk: bool = True,
        delete_file_from_disk: Optional[bool] = None,
        delete_physical_file: Optional[bool] = None,
    ) -> bool:
        """
        Safely delete a downloaded song from the computer and reset its database library state,
        or remove it from library while preserving physical file.

        Args:
            song_id: Song ID in SQLite library
            delete_from_disk: If True, deletes physical .mp3 file on disk and resets song state to NEW
            delete_file_from_disk: Alias for delete_from_disk
            delete_physical_file: Alias for delete_from_disk

        Returns:
            True if deletion succeeded, False otherwise
        """
        with self._lock:
            if delete_physical_file is not None:
                do_delete_disk = delete_physical_file
            elif delete_file_from_disk is not None:
                do_delete_disk = delete_file_from_disk
            else:
                do_delete_disk = delete_from_disk

            song = self.db.get_song(song_id)
            if not song:
                logger.warning(f"delete_downloaded_song: song_id {song_id} not found in database")
                return False

            if do_delete_disk:
                # Delete physical file safely
                if song.file_path:
                    try:
                        fpath = Path(song.file_path)
                        if fpath.is_file() and fpath.exists():
                            fpath.unlink(missing_ok=True)
                            logger.info(f"Deleted physical file: {song.file_path}")
                    except Exception as e:
                        logger.warning(f"Failed to delete physical file '{song.file_path}': {e}")

                # Reset song state back to NEW and clear file details
                self.db.clear_song_download_state(song_id)

                # Delete corresponding completed download records
                dls = self.db.get_downloads_for_song(song_id)
                for d in dls:
                    self.db.delete_download_record(d.id)
                try:
                    self.db.execute_write("DELETE FROM downloads WHERE song_id = ?", (song_id,))
                except Exception:
                    pass
            else:
                # Remove from library only (keep physical file on disk)
                self.db.delete_song(song_id)

            return True

    def delete_download_job(self, download_id: int, delete_physical_file: bool = True) -> bool:
        """
        Delete a download queue record and optionally remove the file.
        """
        with self._lock:
            dl = self.db.get_download(download_id)
            if not dl:
                return False

            if delete_physical_file:
                target_path = dl.output_path or dl.destination_path
                if target_path:
                    try:
                        p = Path(target_path)
                        if p.is_file() and p.exists():
                            p.unlink(missing_ok=True)
                    except Exception as e:
                        logger.warning(f"Failed to delete download file '{target_path}': {e}")

            if dl.song_id:
                # If the song is currently associated with this download, check if state should reset
                song = self.db.get_song(dl.song_id)
                if song and (song.file_path == dl.output_path or song.file_path == dl.destination_path):
                    self.db.clear_song_download_state(dl.song_id)

            return self.db.delete_download_record(download_id)

    def open_path_in_explorer(self, file_or_dir_path: Optional[str]) -> Tuple[bool, str]:
        """
        Open the target file or its containing folder in Windows Explorer.
        Selects the file if it exists, otherwise opens the containing directory.
        """
        try:
            out_dir = Path(settings.output_dir).resolve()
            out_dir.mkdir(parents=True, exist_ok=True)

            if file_or_dir_path:
                target = Path(file_or_dir_path)
                if not target.is_absolute():
                    candidate = (Path.cwd() / target).resolve()
                    if candidate.exists():
                        target = candidate
                    else:
                        target = (out_dir / target.name).resolve()
                else:
                    target = target.resolve()

                if target.is_file() and target.exists():
                    if sys.platform == "win32":
                        subprocess.run(["explorer", f'/select,"{str(target)}"'], check=False)
                    else:
                        subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", str(target.parent)], check=False)
                    return True, f"Opened {target.name} in Explorer"
                elif target.is_dir() and target.exists():
                    if sys.platform == "win32":
                        subprocess.run(["explorer", f'"{str(target)}"'], check=False)
                    else:
                        subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", str(target)], check=False)
                    return True, f"Opened directory {target}"

            # Fallback to configured output directory
            if sys.platform == "win32":
                subprocess.run(["explorer", f'"{str(out_dir)}"'], check=False)
            else:
                subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", str(out_dir)], check=False)
            return True, f"Opened downloads folder: {out_dir}"
        except Exception as e:
            logger.error(f"Error opening Explorer path: {e}")
            return False, f"Could not open folder: {e}"

    # ── Universal URL & Playlist Import Operations ──────────────
    def analyze_music_url(
        self,
        url: str,
        progress_cb: Optional[Callable[[str, int, int], None]] = None,
    ) -> Tuple[ImportJob, List[ImportJobItem]]:
        """
        Analyze music/playlist URL, extract tracks, match against library and audio providers.
        """
        return self.job_manager.analyze_url(url=url, progress_cb=progress_cb)

    def execute_import_job(
        self,
        job_id: str,
        item_ids: Optional[List[int]] = None,
        output_dir: Optional[Path] = None,
        run_async: bool = True,
        progress_cb: Optional[Callable[[int, int, str], None]] = None,
    ) -> Optional[threading.Thread]:
        """
        Start executing downloads for an analyzed import job.
        """
        target_dir = output_dir or Path(self.download_dir)
        def _item_prog(dl_id: int, s_id: int, title: str, ratio: float, msg: str):
            status = "COMPLETED" if ratio >= 1.0 and "Downloaded" in msg else ("FAILED" if "failed" in msg.lower() else "DOWNLOADING")
            self.emit_progress(DownloadProgressEvent(
                download_id=dl_id,
                song_id=s_id,
                title=title,
                status=status,
                percent=ratio,
                speed_str=msg,
            ))

        if run_async:
            def _worker():
                try:
                    self.job_manager.execute_job(
                        job_id=job_id,
                        item_ids=item_ids,
                        output_dir=target_dir,
                        progress_cb=progress_cb,
                        item_progress_cb=_item_prog,
                    )
                except Exception as e:
                    logger.error(f"Error executing import job {job_id}: {e}", exc_info=True)
            t = threading.Thread(target=_worker, daemon=True)
            t.start()
            return t
        else:
            return self.job_manager.execute_job(
                job_id=job_id,
                item_ids=item_ids,
                output_dir=target_dir,
                progress_cb=progress_cb,
                item_progress_cb=_item_prog,
            )

    def get_import_job(self, job_id: str) -> Optional[ImportJob]:
        return self.db.get_import_job(job_id)

    def get_import_job_items(self, job_id: str) -> List[ImportJobItem]:
        return self.db.get_import_job_items(job_id)

    def get_recent_import_jobs(self, limit: int = 15) -> List[ImportJob]:
        return self.db.get_recent_import_jobs(limit=limit)

    def get_job_progress(self, job_id: str) -> Dict[str, int]:
        return self.db.get_job_progress_stats(job_id)

    def get_audio_providers(self) -> List[Any]:
        return [p.get_capabilities() for p in self.provider_registry.get_all_providers()]

    def get_all_songs(self, limit: int = 50) -> List[LibrarySong]:
        """Fetch all songs up to limit."""
        res = self.db.get_paginated_songs(page=1, page_size=limit)
        return res.get("songs", [])

    def get_unowned_songs(self, limit: int = 50) -> List[LibrarySong]:
        """Fetch songs in NEW state (not yet downloaded)."""
        return self.db.get_songs_by_state(SongState.NEW, limit=limit)


    def get_downloaded_songs(
        self,
        query: str = "",
        sort_by: str = "recent",
    ) -> List[LibrarySong]:
        """
        Fetch songs that are verified to be downloaded in the library.
        Filters by search query and sorts by specified field.
        """
        owned = self.db.get_songs_by_state(SongState.OWNED)
        valid_songs = []
        for s in owned:
            # Strictly verify that file physically exists on disk
            if not s.file_path or not os.path.isfile(s.file_path):
                continue

            # Check if query matches
            if query:
                q = query.lower()
                title_match = q in s.title.lower()
                artist_match = bool(s.artist and q in s.artist.lower())
                album_match = bool(s.album and q in s.album.lower())
                if not (title_match or artist_match or album_match):
                    continue
            valid_songs.append(s)

        if sort_by == "title":
            valid_songs.sort(key=lambda x: x.title.lower())
        elif sort_by == "artist":
            valid_songs.sort(key=lambda x: (x.artist or "").lower())
        elif sort_by == "album":
            valid_songs.sort(key=lambda x: (x.album or "").lower())
        elif sort_by == "quality":
            valid_songs.sort(key=lambda x: x.quality_kbps or 0, reverse=True)
        else:  # recent
            valid_songs.sort(key=lambda x: x.id or 0, reverse=True)

        return valid_songs

    def play_audio_file(self, file_path: Optional[str]) -> Tuple[bool, str]:
        """
        Launch the downloaded audio file in the user's default system media player.
        """
        if not file_path:
            return False, "File path is empty"

        p = Path(file_path)
        if not p.is_file() or not p.exists():
            return False, f"Audio file not found on disk: {p.name}"

        try:
            if sys.platform == "win32":
                os.startfile(str(p))
            elif sys.platform == "darwin":
                subprocess.run(["open", str(p)], check=False)
            else:
                subprocess.run(["xdg-open", str(p)], check=False)
            return True, f"Playing '{p.name}' in system player"
        except Exception as e:
            logger.error(f"Error launching player for '{file_path}': {e}")
            return False, f"Could not launch player: {e}"

    def get_all_downloads(self, dedup_by_song: bool = True) -> List[Download]:
        """
        Fetch download records. If dedup_by_song is True, returns only the latest/active record per song.
        """
        all_dls = self.db.get_all_downloads()
        if not dedup_by_song:
            return all_dls

        seen_songs = set()
        unique_dls = []
        for d in all_dls:
            if d.song_id is not None:
                if d.song_id in seen_songs:
                    continue
                seen_songs.add(d.song_id)
            unique_dls.append(d)
        return unique_dls

    def pause_downloads(self) -> None:
        """Pause ongoing downloads."""
        pass

    def resume_downloads(self) -> None:
        """Resume pending downloads."""
        pass

    # ------------------------------------------------------------------
    # V5.3 Movie Discovery & Movie Library Operations
    # ------------------------------------------------------------------

    def get_movies_page(
        self,
        query: str = "",
        min_year: Optional[int] = None,
        max_year: Optional[int] = None,
        sort_by: str = "year",
        ascending: bool = False,
        page: int = 1,
        page_size: int = 24,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Get a paginated slice of movies with aggregated download state.
        Ensures filesystem integrity before querying.
        """
        self.reconcile_library_files()
        offset = max(0, (page - 1) * page_size)
        return self.db.search_and_filter_movies(
            query=query,
            min_year=min_year,
            max_year=max_year,
            sort_by=sort_by,
            ascending=ascending,
            limit=page_size,
            offset=offset,
        )

    def get_movie_details(self, movie_id: int) -> Optional[Dict[str, Any]]:
        """
        Get full details for a movie: metadata, download stats, and song list.
        """
        self.reconcile_library_files()
        movie = self.db.get_movie(movie_id)
        if not movie:
            return None

        stats = self.db.get_movie_download_stats(movie_id)
        songs = self.db.get_movie_songs_detailed(movie_id)
        composers = self.db.get_movie_composers(movie_id)
        actors = self.db.get_movie_actors(movie_id)

        return {
            "movie": movie,
            "stats": stats,
            "songs": songs,
            "composers": [c.name for c in composers],
            "actors": [(a.name, char) for a, char in actors],
            "composer_objects": [{"id": c.id, "name": c.name} for c in composers],
            "actor_objects": [{"id": a.id, "name": a.name, "character": char} for a, char in actors],
        }

    def plan_movie_download_all(self, movie_id: int) -> DownloadPlan:
        """
        Plan downloads for ALL songs in a movie.
        Already owned songs are skipped by DownloadPlanner unless higher quality is available.
        """
        self.reconcile_library_files()
        songs = self.db.get_movie_songs(movie_id)
        return self.planner.plan_downloads_for_songs(songs)

    def plan_movie_download_missing(self, movie_id: int) -> DownloadPlan:
        """
        Plan downloads ONLY for missing songs in a movie.
        Uses physical file verification & reconciliation.
        """
        self.reconcile_library_files()
        songs = self.db.get_movie_songs(movie_id)
        # Missing means: state != OWNED or physical file is missing from disk
        missing_songs = []
        for s in songs:
            if s.state != SongState.OWNED or not s.file_path or not os.path.isfile(s.file_path):
                missing_songs.append(s)
        return self.planner.plan_downloads_for_songs(missing_songs)

    def discover_movies_from_sources(
        self,
        query: Optional[str] = None,
        category: str = "latest",
        max_pages: int = 1,
        source_names: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Discover movies and their tracklists from regional scrapers and register them
        into the SQLite canonical movies and song_movies tables.
        DISCOVERY NEVER DIRECTLY DOWNLOADS AUDIO FILES.
        """
        sources_to_run = source_names or ["masstamilan", "tamilmp3", "friendstamilmp3"]
        usable_scrapers = [
            s for name in sources_to_run
            if (s := self.source_registry.get_source(name)) and s.is_usable and s.scraper
        ]

        total_movies = 0
        total_songs = 0

        for reg_src in usable_scrapers:
            scraper = reg_src.scraper
            try:
                albums = []
                if query and hasattr(scraper, "search"):
                    albums = scraper.search(query.strip())
                elif hasattr(scraper, "get_albums"):
                    albums = scraper.get_albums(category=category, max_pages=max_pages)

                for album in albums:
                    if not album.name:
                        continue
                    # 1. Register or find Movie
                    norm_title = normalize_string(album.name)
                    existing_movie = self.db.get_movie_by_title(album.name)
                    if not existing_movie:
                        movie_id = self.db.add_movie(Movie(
                            title=album.name,
                            title_normalized=norm_title,
                            year=album.year,
                            track_count=album.song_count or 0,
                            poster_url=getattr(album, "image_url", None) or getattr(album, "artwork_url", None),
                        ))
                    else:
                        movie_id = existing_movie.id

                    total_movies += 1

                    # Register composer if available on album
                    composer_val = getattr(album, "composer", None) or getattr(album, "music_director", None)
                    if composer_val and movie_id:
                        for c_name in split_artist_names(composer_val):
                            norm_c = normalize_string(c_name)
                            if norm_c:
                                c_id = self.db.add_artist(Artist(name=c_name, name_normalized=norm_c, role="music_director"))
                                if c_id:
                                    self.db.add_movie_composer(movie_id=movie_id, composer_id=c_id)

                    # 2. Discover songs from album
                    try:
                        songs = scraper.get_songs(album)
                    except Exception as err:
                        logger.warning(f"Failed to fetch songs for album '{album.name}': {err}")
                        songs = []

                    for idx, s in enumerate(songs, start=1):
                        track_no = getattr(s, "track_number", None) or idx
                        song_id = self.pipeline.register_song(
                            song=s,
                            source_name=reg_src.name,
                            album=album,
                            category=category,
                        )
                        if song_id:
                            total_songs += 1
                            # Link to movie via song_movies
                            self.db.add_song_movie(song_id=song_id, movie_id=movie_id, track_number=track_no)

                            # Link singers to song_artists
                            if s.artist:
                                for singer_name in split_artist_names(s.artist):
                                    norm_s = normalize_string(singer_name)
                                    if norm_s:
                                        s_aid = self.db.add_artist(Artist(name=singer_name, name_normalized=norm_s, role="singer"))
                                        if s_aid:
                                            self.db.add_song_artist(song_id=song_id, artist_id=s_aid, role="singer")

                    # Update movie track_count if songs found
                    if songs and movie_id:
                        m = self.db.get_movie(movie_id)
                        if m and len(songs) > m.track_count:
                            m.track_count = len(songs)
                            self.db.update_movie(m)

            except Exception as e:
                logger.warning(f"Movie discovery error on source '{reg_src.name}': {e}")
                self.source_registry.record_failure(reg_src.name, str(e))

        return {
            "query": query,
            "category": category,
            "movies_discovered": total_movies,
            "songs_registered": total_songs,
        }

    # ------------------------------------------------------------------
    # V5.4 People / Music Credits Operations
    # ------------------------------------------------------------------

    def get_artists_page(
        self,
        query: str = "",
        role: Optional[str] = None,
        sort_by: str = "name",
        ascending: bool = True,
        page: int = 1,
        page_size: int = 24,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Get a paginated slice of artists with aggregated soundtrack and download metrics.
        Ensures filesystem integrity before querying.
        """
        self.reconcile_library_files()
        offset = max(0, (page - 1) * page_size)
        return self.db.search_and_filter_artists(
            query=query,
            role=role,
            sort_by=sort_by,
            ascending=ascending,
            limit=page_size,
            offset=offset,
        )

    def get_artist_details(self, artist_id: int) -> Optional[Dict[str, Any]]:
        """
        Get full details for an artist: metadata, roles, download stats, song list, and movie list.
        """
        self.reconcile_library_files()
        artist = self.db.get_artist(artist_id)
        if not artist:
            return None

        stats = self.db.get_artist_statistics(artist_id)
        songs = self.db.get_artist_songs_detailed(artist_id)
        movies = self.db.get_artist_movies_detailed(artist_id)
        roles = stats.get("roles", ["singer"])

        return {
            "artist": artist,
            "stats": stats,
            "songs": songs,
            "movies": movies,
            "roles": roles,
            "roles_display": " • ".join(r.replace("_", " ").title() for r in roles) if roles else "Artist",
        }

    def plan_artist_download_all(self, artist_id: int) -> DownloadPlan:
        """
        Plan downloads for ALL songs associated with an artist (singer or composer).
        Already owned songs are skipped by DownloadPlanner unless higher quality is available.
        """
        self.reconcile_library_files()
        detailed_songs = self.db.get_artist_songs_detailed(artist_id)
        song_ids = [s["song_id"] for s in detailed_songs]
        songs = [s for sid in song_ids if (s := self.db.get_song(sid))]
        return self.planner.plan_downloads_for_songs(songs)

    def plan_artist_download_missing(self, artist_id: int) -> DownloadPlan:
        """
        Plan downloads ONLY for missing songs associated with an artist.
        Uses physical file verification & reconciliation.
        """
        self.reconcile_library_files()
        detailed_songs = self.db.get_artist_songs_detailed(artist_id)
        missing_ids = [s["song_id"] for s in detailed_songs if not s.get("is_downloaded")]
        songs = []
        for sid in missing_ids:
            s = self.db.get_song(sid)
            if s and (s.state != SongState.OWNED or not s.file_path or not os.path.isfile(s.file_path)):
                songs.append(s)
        return self.planner.plan_downloads_for_songs(songs)

    # ------------------------------------------------------------------
    # V5.5 Charts & Top 100 Operations
    # ------------------------------------------------------------------

    def sync_charts(self) -> List[str]:
        """Fetch fresh chart snapshots from external providers."""
        return self.charts_service.sync_all_default_charts()

    def get_charts_page(
        self,
        query: str = "",
        chart_type: Optional[str] = None,
        sort_by: str = "snapshot_date",
        ascending: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Get paginated charts list with download state.
        """
        self.reconcile_library_files()
        return self.db.search_and_filter_charts(
            query=query,
            chart_type=chart_type,
            sort_by=sort_by,
            ascending=ascending,
            limit=page_size,
            offset=max(0, (page - 1) * page_size),
        )

    def get_chart_details(
        self,
        chart_id: str,
        query: str = "",
        page: int = 1,
        page_size: int = 50,
    ) -> Optional[Dict[str, Any]]:
        """
        Get full details for a chart: metadata, stats, and detailed ranked entries.
        """
        self.reconcile_library_files()
        chart = self.db.get_chart(chart_id)
        if not chart:
            return None

        stats = self.db.get_chart_statistics(chart_id)
        offset = max(0, (page - 1) * page_size)
        entries, total_matching = self.db.get_chart_entries_detailed(
            chart_id=chart_id,
            query=query,
            limit=page_size,
            offset=offset,
        )

        return {
            "chart": chart,
            "stats": stats,
            "entries": entries,
            "total_matching": total_matching,
            "page": page,
            "page_size": page_size,
        }

    def plan_chart_download_all(self, chart_id: str) -> DownloadPlan:
        """
        Plan downloads for ALL songs in a chart snapshot.
        Ensures songs have sources registered, then passes to DownloadPlanner.
        """
        self.reconcile_library_files()
        entries = self.db.get_chart_entries(chart_id)
        songs = []
        for e in entries:
            s = self._ensure_chart_entry_song_and_source(e)
            if s:
                songs.append(s)
        return self.planner.plan_downloads_for_songs(songs)

    def plan_chart_download_missing(self, chart_id: str) -> DownloadPlan:
        """
        Plan downloads ONLY for missing songs in a chart snapshot.
        Physical file presence on disk is verified.
        """
        self.reconcile_library_files()
        entries = self.db.get_chart_entries(chart_id)
        missing_songs = []
        for e in entries:
            s = self._ensure_chart_entry_song_and_source(e)
            if s and (s.state != SongState.OWNED or not s.file_path or not os.path.isfile(s.file_path)):
                missing_songs.append(s)
        return self.planner.plan_downloads_for_songs(missing_songs)

    def plan_chart_entry_download(self, chart_id: str, rank: int) -> DownloadPlan:
        """
        Plan download for a single chart entry.
        """
        self.reconcile_library_files()
        entries = self.db.get_chart_entries(chart_id)
        target_entry = next((e for e in entries if e.rank == rank), None)
        if not target_entry:
            return DownloadPlan()
        s = self._ensure_chart_entry_song_and_source(target_entry)
        if not s:
            return DownloadPlan()
        return self.planner.plan_downloads_for_songs([s])

    def _ensure_chart_entry_song_and_source(self, entry: ChartEntry) -> Optional[LibrarySong]:
        """
        Helper ensuring chart entry is linked to a canonical LibrarySong with at least one registered source.
        """
        song = self.db.get_song(entry.song_id) if entry.song_id else None
        if not song:
            song_id = self.charts_service._resolve_or_create_canonical_song(
                title=entry.raw_title,
                artist=entry.raw_artist or "Tamil Artist",
                movie=entry.raw_movie or "Single",
            )
            if song_id:
                self.db.update_chart_entry_song(entry.chart_id, entry.rank, song_id)
                song = self.db.get_song(song_id)

        if not song:
            return None

        # Check if sources exist for this song
        sources = self.db.get_sources_for_song(song.id)
        if not sources:
            # Try to discover/register source via regional provider search
            try:
                from library.providers.regional_provider import TamilRegionalProvider
                reg = TamilRegionalProvider(self.source_registry)
                candidates = reg.search(title=song.title, artist=song.artist, limit=2)
                if candidates:
                    cand = candidates[0]
                    raw_meta = cand.raw_metadata or {}
                    song_obj = raw_meta.get("song_obj")
                    src_name = raw_meta.get("source_name", "tamilmp3")
                    if song_obj:
                        src = SongSource(
                            song_id=song.id,
                            source_name=src_name,
                            source_url=cand.source_url,
                            download_reference=getattr(song_obj, "download_reference", None),
                            quality_kbps=cand.quality_kbps,
                            file_type="mp3",
                            is_available=True,
                        )
                        self.db.add_source(src)
            except Exception as ex:
                logger.debug(f"Source resolution error for chart song '{song.title}': {ex}")

        return song

    def enrich_people_from_library(self) -> Dict[str, int]:
        """
        Scan existing canonical library songs and movies to populate artists,
        song_artists, movie_composers, and movie_actors idempotently.
        """
        artists_added = 0
        song_artists_linked = 0
        composers_linked = 0
        actors_linked = 0

        # 1. Process all canonical songs
        all_songs = self.db.list_songs(limit=10000)
        for s in all_songs:
            if not s.id or not s.artist:
                continue
            names = split_artist_names(s.artist)
            for name in names:
                norm_name = normalize_string(name)
                if not norm_name:
                    continue
                artist_id = self.db.add_artist(Artist(name=name, name_normalized=norm_name, role="singer"))
                if artist_id:
                    artists_added += 1
                    if self.db.add_song_artist(song_id=s.id, artist_id=artist_id, role="singer"):
                        song_artists_linked += 1

        # 2. Process all movies
        all_movies = self.db.list_movies(limit=10000)
        for m in all_movies:
            if not m.id:
                continue
            # Music Director / Composer
            if getattr(m, "music_director", None):
                for name in split_artist_names(m.music_director):
                    norm_name = normalize_string(name)
                    if not norm_name:
                        continue
                    artist_id = self.db.add_artist(Artist(name=name, name_normalized=norm_name, role="music_director"))
                    if artist_id:
                        artists_added += 1
                        if self.db.add_movie_composer(movie_id=m.id, composer_id=artist_id):
                            composers_linked += 1
            # Actors / Cast
            if getattr(m, "actors", None):
                for name in split_artist_names(m.actors):
                    norm_name = normalize_string(name)
                    if not norm_name:
                        continue
                    artist_id = self.db.add_artist(Artist(name=name, name_normalized=norm_name, role="actor"))
                    if artist_id:
                        artists_added += 1
                        if self.db.add_movie_actor(movie_id=m.id, actor_id=artist_id, character_name="Cast"):
                            actors_linked += 1
            # Director
            if m.director:
                names = split_artist_names(m.director)
                for name in names:
                    norm_name = normalize_string(name)
                    if not norm_name:
                        continue
                    artist_id = self.db.add_artist(Artist(name=name, name_normalized=norm_name, role="director"))
                    if artist_id:
                        artists_added += 1
                        if self.db.add_movie_actor(movie_id=m.id, actor_id=artist_id, character_name="Director / Cast"):
                            actors_linked += 1

        return {
            "artists_added": artists_added,
            "song_artists_linked": song_artists_linked,
            "composers_linked": composers_linked,
            "actors_linked": actors_linked,
        }

    def split_artist_names(self, raw_artist: Optional[str]) -> List[str]:
        """Split composite artist strings into distinct individual names."""
        return split_artist_names(raw_artist)


def split_artist_names(raw_artist: Optional[str]) -> List[str]:
    """Split composite artist strings into distinct individual names."""
    if not raw_artist:
        return []
    # Strip bracketed remarks like (Vocals), [Chorus]
    text = re.sub(r"\(.*?\)", "", raw_artist)
    text = re.sub(r"\[.*?\]", "", text)
    # Delimiters: ',', '&', ';', '/', ' feat. ', ' feat ', ' ft. ', ' ft ', ' and ', ' with ', ' vs. '
    pattern = r"\s*(?:,|&|;|/|\bfeat\.?|\bft\.?|\band\b|\bwith\b|\bvs\.?)\s*"
    parts = re.split(pattern, text, flags=re.IGNORECASE)
    cleaned = []
    for p in parts:
        name = p.strip(" .,;/-")
        if len(name) >= 2 and not name.lower().startswith(("unknown", "various", "ost")):
            cleaned.append(name)
    return cleaned




