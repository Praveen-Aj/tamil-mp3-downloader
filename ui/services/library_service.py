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

import logging
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Tuple

from config.settings import settings
from library.database import SQLiteDatabase
from library.discovery import DiscoveryPipeline
from library.importer import LibraryImporter
from library.models import (
    LibrarySong, SongSource, SongState, DownloadState, Download,
    ImportJob, ImportJobItem, JobStatus, ItemState
)
from library.planner import DownloadPlanner, DownloadPlan, SourceSelection
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


class LibraryService:
    """
    Central service coordinating backend components for the UI.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or settings.library_db_path
        self.db = SQLiteDatabase(self.db_path)
        self.db.connect()

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

        self._lock = threading.RLock()
        self._last_discovery_session: Optional[Dict[str, Any]] = None
        self._init_default_sources()

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
        """Get summary metrics for Dashboard."""
        lib_stats = self.db.get_library_stats()
        sources = self.source_registry.get_all_sources()
        enabled_sources = [s for s in sources if s.enabled]
        disabled_sources = [s for s in sources if not s.enabled]
        healthy_enabled = sum(1 for s in enabled_sources if s.is_usable)

        # Count quality upgrades available
        owned = self.db.get_songs_by_state(SongState.OWNED)
        
        upgrades_count = 0
        for s in owned:
            if s.quality_kbps and s.quality_kbps < 320:
                s_sources = self.db.get_sources_for_song(s.id)
                if any(src.quality_kbps and src.quality_kbps >= 320 for src in s_sources):
                    upgrades_count += 1

        active_downloads = len(self.registry.get_active_downloads())

        return {
            "total_songs": lib_stats.get("total_songs", 0),
            "owned_songs": lib_stats.get("songs_by_state", {}).get("OWNED", 0),
            "unowned_songs": lib_stats.get("songs_by_state", {}).get("NEW", 0),
            "upgrades_available": upgrades_count,
            "active_downloads": active_downloads,
            "healthy_sources": f"{healthy_enabled}/{len(enabled_sources)} Core Healthy",
            "disabled_sources": len(disabled_sources),
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
    ) -> Dict[str, Any]:
        """
        Get paginated songs from SQLite with filter criteria.
        """
        effective_state = state or state_filter
        return self.db.get_paginated_songs(
            query=query,
            state_filter=effective_state,
            page=page,
            page_size=page_size,
        )

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

    def execute_single_download(self, download_id: int) -> bool:
        """
        Execute a complete production download pipeline for a single download slot.

        Workflow:
        Download Plan -> DownloadRegistry acquire -> resolve source download URL
        -> invoke existing HTTPDownloader -> write file to configured location
        -> verify successful download -> update database/library state
        -> DownloadRegistry complete -> Canonical Song becomes OWNED.

        For Tamilmp3:
        SongSource.download_reference -> Tamilmp3Scraper.get_download_url()
        -> fresh token.php request -> fresh signed CDN URL -> HTTPDownloader -> filesystem.
        """
        dl = self.db.get_download(download_id)
        if not dl:
            logger.error(f"execute_single_download: download_id {download_id} not found")
            return False

        song = self.db.get_song(dl.song_id)
        if not song:
            self.registry.fail(dl.song_id, download_id, "Song record missing from database", dl.song_source_id)
            return False

        source = self.db.get_source_by_id(dl.song_source_id)
        if not source:
            self.registry.fail(dl.song_id, download_id, "Source variant missing from database", dl.song_source_id)
            return False

        # Resolve fresh download URL via registered scraper if available
        download_url = None
        reg_src = self.source_registry.get_source(source.source_name)
        if reg_src and reg_src.scraper and hasattr(reg_src.scraper, "get_download_url"):
            try:
                download_url = reg_src.scraper.get_download_url(source, quality=str(source.quality_kbps or 320))
            except Exception as e:
                logger.warning(f"Error resolving download URL from scraper '{source.source_name}': {e}")

        if not download_url:
            download_url = source.download_reference or source.source_url

        if not download_url or not (download_url.startswith("http://") or download_url.startswith("https://")):
            err_msg = f"Invalid or empty download URL: '{download_url}'"
            self.registry.fail(song.id, download_id, err_msg, source.id)
            return False

        from models.song import Song as DownloadSong
        from downloaders.http_downloader import HTTPDownloader

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
                output_dir=Path(settings.output_dir),
                max_workers=settings.get("download.max_workers", 3),
                show_progress=False,
            )
            result = downloader.download_song(dl_song)

            if result.success and result.file_path and result.file_path.exists() and result.file_path.stat().st_size > 0:
                was_upgrade = (song.state == SongState.OWNED)
                file_size = result.size_downloaded or result.file_path.stat().st_size
                self.registry.complete(
                    song_id=song.id,
                    download_id=download_id,
                    file_path=str(result.file_path),
                    file_size_bytes=file_size,
                    quality_kbps=source.quality_kbps,
                    library_location_id=1,
                    was_upgrade=was_upgrade,
                    previous_file_path=song.file_path,
                    previous_quality_kbps=song.quality_kbps,
                )
                self.registry.reward_source(source.id)
                return True
            else:
                err_msg = result.error_message or "Download verification failed (empty or missing file)"
                self.registry.fail(song.id, download_id, err_msg, source.id)
                return False

        except Exception as exc:
            err_msg = f"Download execution exception: {exc}"
            self.registry.fail(song.id, download_id, err_msg, source.id)
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
                for idx, dl_id in enumerate(enqueued_ids, start=1):
                    self.execute_single_download(dl_id)
                    if progress_cb:
                        progress_cb(idx, len(enqueued_ids))

            threading.Thread(target=_worker, daemon=True).start()
        elif not run_async:
            for idx, dl_id in enumerate(enqueued_ids, start=1):
                self.execute_single_download(dl_id)
                if progress_cb:
                    progress_cb(idx, len(enqueued_ids))

        return enqueued_ids

    def retry_failed_downloads(
        self,
        download_ids: Optional[List[int]] = None,
        run_async: bool = True,
        progress_cb: Optional[Callable[[int, int], None]] = None,
    ) -> List[int]:
        """
        Identify failed downloads, safely re-acquire registry slots, and execute the downloader again.
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
            
            # Transition song back to NEW so acquire slot can succeed
            self.db.update_song_state(d.song_id, SongState.NEW)
            new_dl_id = self.registry.acquire_download(
                song_id=d.song_id,
                song_source_id=d.song_source_id,
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
        run_async: bool = True,
        progress_cb: Optional[Callable[[int, int, str], None]] = None,
    ) -> None:
        """
        Start executing downloads for an analyzed import job.
        """
        if run_async:
            def _worker():
                self.job_manager.execute_job(
                    job_id=job_id,
                    item_ids=item_ids,
                    progress_cb=progress_cb,
                )
            threading.Thread(target=_worker, daemon=True).start()
        else:
            self.job_manager.execute_job(
                job_id=job_id,
                item_ids=item_ids,
                progress_cb=progress_cb,
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
        """Fetch songs needing review/unowned."""
        return self.db.get_songs_by_state(SongState.NEW, limit=limit)

    def get_all_downloads(self) -> List[Download]:
        """Fetch all download records."""
        return self.db.get_all_downloads()

    def pause_downloads(self) -> None:
        """Pause ongoing downloads."""
        pass

    def resume_downloads(self) -> None:
        """Resume pending downloads."""
        pass
