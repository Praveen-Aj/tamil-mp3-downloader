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
    ):
        """
        Initialize download planner.

        Args:
            db: Connected SQLiteDatabase instance
            upgrade_quality_threshold: Min kbps gain to trigger upgrade (default 64)
        """
        self.db = db
        self.upgrade_quality_threshold = upgrade_quality_threshold
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
        # Track song_ids we've already added to plan to prevent double-counting
        # when the same canonical ID appears under multiple hashes due to aliasing
        seen_song_ids: set = set()

        for song in discovered_songs:
            identity = song_to_canonical(song, source_name)

            # Skip within-batch duplicates
            if identity.hash in seen_hashes:
                logger.debug(f"Dedup within batch: '{song.name}' (hash already seen)")
                continue
            seen_hashes.add(identity.hash)
            plan.unique_canonical += 1

            # Retrieve the canonical library entry
            lib_song = self.db.get_song_by_canonical_hash(identity.hash)
            if lib_song is None:
                logger.warning(f"Song not found in library after registration: {identity}")
                continue

            # Guard against the same DB song_id appearing via different hashes
            # (shouldn't happen with SHA256, but be defensive)
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
                # NEW, FAILED, QUEUED — queue for download with best source
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

        This is the recommended entry point when songs have been discovered
        from multiple sites/categories.  All registrations happen first, then
        planning deduplicates across all batches.

        Args:
            source_batches: List of dicts, each with keys:
                - songs: List[Song]
                - source_name: str
                - album: Optional[Album]
                - category: Optional[str]

        Returns:
            DownloadPlan with at most 1 entry per canonical song across all batches
        """
        total_raw = sum(len(b["songs"]) for b in source_batches)
        plan = DownloadPlan(raw_discovered=total_raw)

        # Step 1: Register all batches first (with source failure isolation)
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

        # Step 2: Deduplicate and plan across all batches
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

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _select_best_source(
        self, song_id: int, original_song: Song, source_name: str
    ) -> Optional[SourceSelection]:
        """
        Select the best available source for a song from ALL registered sources.

        Priority: availability > quality_kbps > reliability_score > smaller size

        Args:
            song_id: Library song ID
            original_song: Representative Song object (for display)
            source_name: Source name of the representative song

        Returns:
            SourceSelection with ranked sources, or None if no sources exist
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
        Ranking key for source selection.

        Priority:
        1. Availability (True > False)
        2. Quality kbps (higher = better)
        3. Reliability score (higher = better)
        4. Size (smaller = preferred when quality is equal)
        """
        return (
            int(source.is_available),
            source.quality_kbps or 0,
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

        Args:
            existing: Currently owned LibrarySong
            song: Newly discovered Song
            source_name: Source name

        Returns:
            UpgradePlan if upgrade is warranted, None otherwise
        """
        if existing.quality_kbps is None:
            return None  # Unknown existing quality — cannot compare

        # Find the best quality source available (from ALL registered sources)
        sources = self.db.get_sources_for_song(existing.id)
        if not sources:
            return None

        best_source = max(
            (s for s in sources if s.is_available),
            key=lambda s: s.quality_kbps or 0,
            default=None,
        )
        if best_source is None:
            best_source = max(sources, key=lambda s: s.quality_kbps or 0)

        best_quality = best_source.quality_kbps or 0
        quality_gain = best_quality - existing.quality_kbps

        # Never downgrade
        if quality_gain <= 0:
            return None

        # Only upgrade if improvement meets threshold
        if quality_gain < self.upgrade_quality_threshold:
            return None

        return UpgradePlan(
            existing=existing,
            song=song,
            source_name=best_source.source_name,
            new_source=best_source,
            quality_gain=quality_gain,
        )
