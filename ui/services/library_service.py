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
from typing import Dict, List, Optional, Any, Callable

from config.settings import settings
from library.database import SQLiteDatabase
from library.discovery import DiscoveryPipeline
from library.importer import LibraryImporter
from library.models import LibrarySong, SongSource, SongState, DownloadState, Download
from library.planner import DownloadPlanner, DownloadPlan, SourceSelection
from library.registry import DownloadRegistry
from scrapers.base import BaseScraper
from scrapers.friendstamilmp3 import FriendsTamilMP3Scraper
from scrapers.isaimini import IsaiminiScraper
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

        self._lock = threading.RLock()
        self._last_discovery_session: Optional[Dict[str, Any]] = None
        self._init_default_sources()

    def _init_default_sources(self) -> None:
        """Register default core sources in SourceRegistry."""
        # 1. MassTamilan
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

        # 2. Tamilmp3.in / Kuttyweb
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

        # 3. FriendsTamilMP3
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

    # ── Summary & Stats ──────────────────────────────────────────
    def get_dashboard_stats(self) -> Dict[str, Any]:
        """Get summary metrics for Dashboard."""
        lib_stats = self.db.get_library_stats()
        sources = self.source_registry.get_all_sources()
        healthy_count = sum(1 for s in sources if s.is_usable)

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
            "healthy_sources": f"{healthy_count}/{len(sources)}",
            "last_session": self._last_discovery_session,
        }

    # ── Library Query & Pagination ──────────────────────────────
    def get_library_page(
        self,
        query: str = "",
        state_filter: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """
        Get paginated songs from SQLite with filter criteria.

        Args:
            query: Search query (title, artist, album)
            state_filter: "ALL", "OWNED", "UNOWNED", "UPGRADES"
            page: 1-indexed page number
            page_size: Rows per page

        Returns:
            Dict containing list of songs, total count, total pages, current page
        """
        offset = (page - 1) * page_size
        cursor = self.db._conn.cursor()

        base_sql = "FROM songs WHERE 1=1"
        params: List[Any] = []

        if query.strip():
            search_pat = f"%{query.strip()}%"
            base_sql += " AND (title LIKE ? OR artist LIKE ? OR album LIKE ?)"
            params.extend([search_pat, search_pat, search_pat])

        if state_filter == "OWNED":
            base_sql += " AND state = 'OWNED'"
        elif state_filter == "UNOWNED":
            base_sql += " AND state = 'NEW'"

        # Count total items
        cursor.execute(f"SELECT COUNT(*) {base_sql}", params)
        total_items = cursor.fetchone()[0]
        total_pages = max(1, (total_items + page_size - 1) // page_size)

        # Query page slice
        query_sql = f"SELECT * {base_sql} ORDER BY id DESC LIMIT ? OFFSET ?"
        query_params = list(params) + [page_size, offset]
        cursor.execute(query_sql, query_params)

        songs = [LibrarySong.from_row(row) for row in cursor.fetchall()]

        return {
            "songs": songs,
            "total_items": total_items,
            "total_pages": total_pages,
            "page": page,
            "page_size": page_size,
        }

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

    def execute_download_plan(self, plan: DownloadPlan) -> List[int]:
        """Enqueue planned downloads into DownloadRegistry."""
        enqueued_ids = []
        for planned in plan.new_songs:
            dl_id = self.registry.acquire_download(
                song_id=planned.song.id,
                song_source_id=planned.primary.id,
            )
            if dl_id:
                enqueued_ids.append(dl_id)
        return enqueued_ids
