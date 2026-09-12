"""
Download Planner for the library system.

Provides intelligent download planning with cross-category/source
deduplication, source ranking, and quality-upgrade detection.
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
        song: Original Song object (for UI display)
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
        existing: Currently owned song
        song: New song with better quality
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
        new_songs: New songs to download
        upgrades: Quality upgrades for existing songs
    """
    raw_discovered: int = 0
    unique_canonical: int = 0
    owned: List[LibrarySong] = field(default_factory=list)
    new_songs: List[SourceSelection] = field(default_factory=list)
    upgrades: List[UpgradePlan] = field(default_factory=list)

    @property
    def total_to_download(self) -> int:
        """Total songs that will be downloaded."""
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

    Steps:
    1. Canonicalize each discovered song
    2. Check library for existing songs
    3. Aggregate source variants (per canonical song)
    4. Select best source per canonical song
    5. Filter already-owned songs
    6. Check for quality upgrades
    7. Generate final download queue
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
            DownloadPlan with deduplication applied
        """
        plan = DownloadPlan(raw_discovered=len(discovered_songs))

        # Register all songs in library (discovery pipeline handles dedup)
        self._pipeline.register_batch(discovered_songs, source_name, album, category)

        # Track which canonical hashes we've already processed in this batch
        seen_hashes: set = set()

        for song in discovered_songs:
            identity = song_to_canonical(song, source_name)

            # Skip duplicates within this batch
            if identity.hash in seen_hashes:
                logger.debug(f"Skipping duplicate in batch: {song.name}")
                continue
            seen_hashes.add(identity.hash)
            plan.unique_canonical += 1

            # Retrieve library entry
            lib_song = self.db.get_song_by_canonical_hash(identity.hash)
            if lib_song is None:
                logger.warning(f"Song not found in library after registration: {identity}")
                continue

            if lib_song.state == SongState.OWNED:
                # Check for upgrade opportunity
                upgrade = self._check_upgrade(lib_song, song, source_name)
                if upgrade:
                    plan.upgrades.append(upgrade)
                else:
                    plan.owned.append(lib_song)
            else:
                # Song is new or failed — queue for download
                best = self._select_best_source(lib_song.id, song, source_name)
                if best:
                    plan.new_songs.append(best)

        logger.info(
            f"Download plan: {plan.raw_discovered} raw → {plan.unique_canonical} unique | "
            f"{len(plan.owned)} owned, {len(plan.new_songs)} new, {len(plan.upgrades)} upgrades"
        )
        return plan

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _select_best_source(
        self, song_id: int, original_song: Song, source_name: str
    ) -> Optional[SourceSelection]:
        """
        Select the best available source for a song.

        Priority: availability > quality_kbps > reliability_score > smaller size

        Args:
            song_id: Library song ID
            original_song: Original Song object
            source_name: Source name

        Returns:
            SourceSelection or None if no sources
        """
        sources = self.db.get_sources_for_song(song_id)
        if not sources:
            return None

        available = [s for s in sources if s.is_available]
        if not available:
            available = sources  # Fallback to all sources

        ranked = sorted(available, key=self._source_ranking_key, reverse=True)

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

        Priority order:
        1. Availability (available first)
        2. Quality (higher kbps first)
        3. Reliability (higher score first)
        4. Size (smaller first — prefer smaller if same quality)
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
        Check if a quality upgrade is possible for an owned song.

        Args:
            existing: Currently owned song
            song: Newly discovered song
            source_name: Source name

        Returns:
            UpgradePlan if upgrade is worthwhile, None otherwise
        """
        if existing.quality_kbps is None:
            return None  # Unknown existing quality — skip

        new_quality = extract_quality_kbps(song)
        if new_quality is None:
            return None  # Unknown new quality — skip

        quality_gain = new_quality - existing.quality_kbps
        if quality_gain < self.upgrade_quality_threshold:
            return None  # Not enough improvement

        # Find the best source for this song
        sources = self.db.get_sources_for_song(existing.id)
        if not sources:
            return None

        # Find source matching the new quality
        matching = [s for s in sources if s.quality_kbps == new_quality and s.is_available]
        if not matching:
            matching = sorted(sources, key=self._source_ranking_key, reverse=True)

        if not matching:
            return None

        best_source = matching[0]
        return UpgradePlan(
            existing=existing,
            song=song,
            source_name=source_name,
            new_source=best_source,
            quality_gain=quality_gain,
        )
