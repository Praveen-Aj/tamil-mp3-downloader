"""
Download Planner for the library system.

Provides intelligent download planning with cross-category/source
deduplication, source ranking, and quality-upgrade detection.

Key guarantee: plan_downloads() over any set of discovered songs — regardless
of how many categories or sites they came from — produces at most ONE
download per canonical song, and ZERO downloads for already-owned songs.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional, TYPE_CHECKING

from library.models import LibrarySong, SongSource, SongState
from library.discovery import DiscoveryPipeline, song_to_canonical, extract_quality_kbps
from models.song import Song, Album

if TYPE_CHECKING:
    from library.database import SQLiteDatabase

logger = logging.getLogger(__name__)


@dataclass
class SourceSelection:
    """
    Best source selection for a canonical song.

    Attributes:
        song_id: Library song ID
        song: Representative Song object (for UI display)
        source_name: Name of the chosen source
        primary: Primary (best) source
        fallbacks: Fallback sources in priority order
    """
    song_id: int
    song: Song
    source_name: str
    primary: SongSource
    fallbacks: List[SongSource] = field(default_factory=list)

    @property
    def quality_str(self) -> str:
        """Display quality string."""
        return self.primary.quality_str

    @property
    def size_str(self) -> str:
        """Display size string."""
        return self.primary.size_str


@dataclass
class UpgradePlan:
    """
    Quality upgrade plan for an existing song.

    Attributes:
        existing: Currently owned LibrarySong
        song: Representative Song object
        source_name: Source to download upgrade from
        new_source: Best source for the upgrade
        quality_gain: kbps improvement
    """
    existing: LibrarySong
    song: Song
    source_name: str
    new_source: SongSource
    quality_gain: int


@dataclass
class DownloadPlan:
    """
    Result of download planning.

    Attributes:
        raw_discovered: Total songs discovered before dedup
        unique_canonical: Unique canonical songs after dedup
        owned: Songs already owned (no action needed)
        new_songs: New songs to download (one per canonical song)
        upgrades: Quality upgrades for existing songs
    """
    raw_discovered: int = 0
    unique_canonical: int = 0
    owned: List[LibrarySong] = field(default_factory=list)
    new_songs: List[SourceSelection] = field(default_factory=list)
    upgrades: List[UpgradePlan] = field(default_factory=list)

    @property
    def total_to_download(self) -> int:
        """Total songs that will be downloaded (new + upgrades)."""
        return len(self.new_songs) + len(self.upgrades)

    @property
    def summary(self) -> str:
        """Human-readable summary of the plan."""
        lines = [
            f"Discovered: {self.raw_discovered} songs ({self.unique_canonical} unique)",
            f"Already owned: {len(self.owned)}",
            f"New to download: {len(self.new_songs)}",
        ]
        if self.upgrades:
            lines.append(f"Quality upgrades available: {len(self.upgrades)}")
        return "\n".join(lines)


class DownloadPlanner:
    """
    Plan downloads with cross-category/source deduplication.

    Algorithm
    ---------
    1. Register all discovered songs via DiscoveryPipeline (idempotent upsert)
    2. For each *unique* canonical hash in the input batch:
       a. Load the library song (guaranteed to exist after step 1)
       b. If OWNED: check upgrade eligibility; else: queue for download
    3. Source selection uses ALL registered sources (not just the one
       in this batch), so a song discovered via Site 1 in a previous batch
       can be downloaded via Site 2 if it has better quality.
    4. Dedup within the batch is tracked via a `seen_hashes` set, so a
       song appearing N times in one batch counts as 1 unique canonical song.

    Guarantees
    ----------
    - At most 1 download per canonical song per plan call
    - 0 downloads for OWNED songs (unless quality upgrade threshold met)
    - Never schedules a downgrade (source quality < library quality)
    """

    def __init__(
        self,
        db: "SQLiteDatabase",
        upgrade_quality_threshold: int = 64,
        source_priority: Optional[List[str]] = None,
    ):
        """
        Initialize download planner.

        Args:
            db: Connected SQLiteDatabase instance
            upgrade_quality_threshold: Min kbps gain to trigger upgrade (default 64)
            source_priority: Ordered list of preferred source names (e.g. ["masstamilan", "tamilmp3", "friendstamilmp3"])
        """
        self.db = db
        self.upgrade_quality_threshold = upgrade_quality_threshold
        self.source_priority = source_priority or ["masstamilan", "tamilmp3", "friendstamilmp3"]
        self._pipeline = DiscoveryPipeline(db)

    def plan_downloads(
        self,
        discovered_songs: List[Song],
        source_name: str,
        album: Optional[Album] = None,
        category: Optional[str] = None,
    ) -> DownloadPlan:
        """
        Generate a download plan from a batch of discovered songs.

        Args:
            discovered_songs: Songs from scraper
            source_name: Source name
            album: Album context (optional)
            category: Category (optional)

        Returns:
            DownloadPlan with at most 1 entry per canonical song
        """
        plan = DownloadPlan(raw_discovered=len(discovered_songs))

        # Register all songs in library (idempotent, thread-safe)
        self._pipeline.register_batch(discovered_songs, source_name, album, category)

        # Process each *unique* canonical song exactly once
        seen_hashes: set = set()
        seen_song_ids: set = set()

        for song in discovered_songs:
            identity = song_to_canonical(song, source_name)

            if identity.hash in seen_hashes:
                logger.debug(f"Dedup within batch: '{song.name}' (hash already seen)")
                continue
            seen_hashes.add(identity.hash)
            plan.unique_canonical += 1

            lib_song = self.db.get_song_by_canonical_hash(identity.hash)
            if lib_song is None:
                logger.warning(f"Song not found in library after registration: {identity}")
                continue

            if lib_song.id in seen_song_ids:
                logger.debug(f"Dedup: song_id {lib_song.id} already planned")
                continue
            seen_song_ids.add(lib_song.id)

            if lib_song.state == SongState.OWNED:
                upgrade = self._check_upgrade(lib_song, song, source_name)
                if upgrade:
                    plan.upgrades.append(upgrade)
                else:
                    plan.owned.append(lib_song)
            else:
                best = self._select_best_source(lib_song.id, song, source_name)
                if best:
                    plan.new_songs.append(best)

        logger.info(
            f"Plan ({source_name}/{category}): "
            f"{plan.raw_discovered} raw → {plan.unique_canonical} unique | "
            f"{len(plan.owned)} owned, {len(plan.new_songs)} new, "
            f"{len(plan.upgrades)} upgrades"
        )
        return plan

    def plan_downloads_multi_source(
        self,
        source_batches: List[dict],
    ) -> DownloadPlan:
        """
        Plan downloads from multiple source batches simultaneously.
        """
        total_raw = sum(len(b["songs"]) for b in source_batches)
        plan = DownloadPlan(raw_discovered=total_raw)

        for batch in source_batches:
            try:
                self._pipeline.register_batch(
                    batch["songs"],
                    batch["source_name"],
                    batch.get("album"),
                    batch.get("category"),
                )
            except Exception as e:
                logger.error(f"Source batch failure for '{batch.get('source_name')}': {e}")
                continue

        seen_hashes: set = set()
        seen_song_ids: set = set()

        for batch in source_batches:
            source_name = batch["source_name"]
            for song in batch["songs"]:
                identity = song_to_canonical(song, source_name)

                if identity.hash in seen_hashes:
                    continue
                seen_hashes.add(identity.hash)
                plan.unique_canonical += 1

                lib_song = self.db.get_song_by_canonical_hash(identity.hash)
                if lib_song is None:
                    continue

                if lib_song.id in seen_song_ids:
                    continue
                seen_song_ids.add(lib_song.id)

                if lib_song.state == SongState.OWNED:
                    upgrade = self._check_upgrade(lib_song, song, source_name)
                    if upgrade:
                        plan.upgrades.append(upgrade)
                    else:
                        plan.owned.append(lib_song)
                else:
                    best = self._select_best_source(lib_song.id, song, source_name)
                    if best:
                        plan.new_songs.append(best)

        logger.info(
            f"Multi-source plan: {plan.raw_discovered} raw → "
            f"{plan.unique_canonical} unique | "
            f"{len(plan.owned)} owned, {len(plan.new_songs)} new, "
            f"{len(plan.upgrades)} upgrades"
        )
        return plan

    def plan_downloads_for_songs(
        self,
        lib_songs: List[LibrarySong],
        preferred_quality: Optional[int] = None,
    ) -> DownloadPlan:
        """
        Generate a DownloadPlan for a list of LibrarySong instances from DB.
        """
        plan = DownloadPlan(raw_discovered=len(lib_songs), unique_canonical=len(lib_songs))
        seen_ids = set()

        for lib_song in lib_songs:
            if lib_song.id in seen_ids:
                continue
            seen_ids.add(lib_song.id)

            if lib_song.state == SongState.OWNED:
                from models.song import Song
                rep_song = Song(name=lib_song.title, url="", album_name=lib_song.album or "")
                upgrade = self._check_upgrade(lib_song, rep_song, "library")
                if upgrade:
                    plan.upgrades.append(upgrade)
                else:
                    plan.owned.append(lib_song)
            else:
                sources = self.db.get_sources_for_song(lib_song.id)
                if not sources:
                    continue
                available = [s for s in sources if s.is_available]
                ranked = sorted(
                    available if available else sources,
                    key=self._source_ranking_key,
                    reverse=True,
                )
                primary = ranked[0]

                from models.song import Song
                rep_song = Song(
                    name=lib_song.title,
                    url=primary.source_url or "",
                    album_name=lib_song.album or "",
                    quality=primary.quality_str,
                )
                sel = SourceSelection(
                    song_id=lib_song.id,
                    song=rep_song,
                    source_name=primary.source_name,
                    primary=primary,
                    fallbacks=ranked[1:],
                )
                plan.new_songs.append(sel)
        return plan

    def plan_downloads_for_song_ids(self, song_ids: List[int]) -> DownloadPlan:
        """
        Generate a DownloadPlan for a list of song IDs.
        """
        songs = [s for sid in song_ids if (s := self.db.get_song(sid))]
        return self.plan_downloads_for_songs(songs)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _select_best_source(
        self, song_id: int, original_song: Song, source_name: str
    ) -> Optional[SourceSelection]:
        """
        Select the best available source for a song from ALL registered sources.

        Priority: availability > quality_kbps > user_source_priority > reliability_score > smaller size
        """
        sources = self.db.get_sources_for_song(song_id)
        if not sources:
            return None

        available = [s for s in sources if s.is_available]
        ranked = sorted(
            available if available else sources,
            key=self._source_ranking_key,
            reverse=True,
        )

        return SourceSelection(
            song_id=song_id,
            song=original_song,
            source_name=ranked[0].source_name,
            primary=ranked[0],
            fallbacks=ranked[1:],
        )

    def _source_ranking_key(self, source: SongSource) -> tuple:
        """
        Deterministic Source Ranking Policy:

        1. Availability: True > False (is_available)
        2. Quality kbps: Higher quality tier (e.g. 320 > 128 > 0)
        3. User Source Priority: Priority score based on user source priority configuration
        4. Reliability Score: Higher runtime health/reliability score (0.0 to 1.0)
        5. File Size: Smaller size preferred if quality & priority are equal
        """
        priority_list = self.source_priority or ["masstamilan", "tamilmp3", "friendstamilmp3"]
        s_name = (source.source_name or "").lower()
        try:
            priority_score = len(priority_list) - priority_list.index(s_name)
        except ValueError:
            priority_score = 0

        return (
            int(source.is_available),
            source.quality_kbps or 0,
            priority_score,
            source.reliability_score,
            -(source.file_size_bytes or 0),
        )

    def _check_upgrade(
        self, existing: LibrarySong, song: Song, source_name: str
    ) -> Optional[UpgradePlan]:
        """
        Check if a quality upgrade is warranted for an owned song.

        Never produces a downgrade: only returns an UpgradePlan when the best
        available source quality exceeds the library quality by at least
        `upgrade_quality_threshold` kbps.
        """
        # If existing quality is unknown (None), treat existing kbps as 0 for upgrade evaluation
        existing_quality = existing.quality_kbps if existing.quality_kbps is not None else 0

        sources = self.db.get_sources_for_song(existing.id)
        if not sources:
            return None

        best_source = max(
            (s for s in sources if s.is_available),
            key=self._source_ranking_key,
            default=None,
        )
        if best_source is None:
            best_source = max(sources, key=self._source_ranking_key)

        best_quality = best_source.quality_kbps or 0
        quality_gain = best_quality - existing_quality

        if quality_gain <= 0:
            return None

        if existing.quality_kbps is not None and quality_gain < self.upgrade_quality_threshold:
            return None

        return UpgradePlan(
            existing=existing,
            song=song,
            source_name=best_source.source_name,
            new_source=best_source,
            quality_gain=quality_gain,
        )
