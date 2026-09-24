"""
Download Schemas for V6 API.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class DownloadItemResponse(BaseModel):
    """Active or historical download item model."""
    id: int
    song_id: int
    title: str
    artist: Optional[str] = None
    source_name: Optional[str] = None
    target_quality: int = 128
    status: str = "QUEUED"
    progress_percent: float = 0.0
    bytes_downloaded: int = 0
    total_bytes: Optional[int] = None
    speed_kbps: float = 0.0
    eta_seconds: Optional[int] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    completed_at: Optional[str] = None


class DownloadPlanRequest(BaseModel):
    """Request to generate download plans for songs."""
    song_ids: List[int]
    force_upgrade: bool = False


class DownloadPlanItemResponse(BaseModel):
    """Planned download execution item."""
    song_id: int
    title: str
    artist: Optional[str] = None
    action: str  # DOWNLOAD, SKIP, UPGRADE
    source_name: Optional[str] = None
    source_url: Optional[str] = None
    quality: int = 128
    reason: Optional[str] = None


class DownloadPlanResponse(BaseModel):
    """Batch download plan overview."""
    total_requested: int
    to_download: int
    to_skip: int
    to_upgrade: int
    items: List[DownloadPlanItemResponse] = Field(default_factory=list)


class DownloadExecuteRequest(BaseModel):
    """Request to trigger background downloads for specified songs."""
    song_ids: List[int]
    category: Optional[str] = None  # e.g., 'movie', 'playlist', 'chart', 'selected'


def format_download_plan(plan: Any) -> DownloadPlanResponse:
    """Helper to convert core DownloadPlan dataclass to DownloadPlanResponse."""
    items: List[DownloadPlanItemResponse] = []

    # 1. New downloads
    for sel in getattr(plan, "new_songs", []):
        items.append(DownloadPlanItemResponse(
            song_id=sel.song_id,
            title=getattr(sel.song, "title", "Unknown"),
            artist=getattr(sel.song, "artist", None),
            action="DOWNLOAD",
            source_name=sel.source_name,
            source_url=sel.primary.source_url if sel.primary else None,
            quality=sel.primary.quality_kbps if sel.primary else 128,
            reason="New track to download",
        ))

    # 2. Upgrades
    for up in getattr(plan, "upgrades", []):
        items.append(DownloadPlanItemResponse(
            song_id=up.existing.id,
            title=getattr(up.song, "title", "Unknown"),
            artist=getattr(up.song, "artist", None),
            action="UPGRADE",
            source_name=up.source_name,
            source_url=up.new_source.source_url if up.new_source else None,
            quality=up.new_source.quality_kbps if up.new_source else 320,
            reason=f"Quality upgrade available (+{up.quality_gain} kbps)",
        ))

    # 3. Owned / Skip
    for ow in getattr(plan, "owned", []):
        items.append(DownloadPlanItemResponse(
            song_id=ow.id,
            title=ow.title,
            artist=ow.artist,
            action="SKIP",
            source_name=None,
            source_url=None,
            quality=ow.quality_kbps or 128,
            reason="Already owned on disk",
        ))

    to_download = len(getattr(plan, "new_songs", []))
    to_skip = len(getattr(plan, "owned", []))
    to_upgrade = len(getattr(plan, "upgrades", []))

    return DownloadPlanResponse(
        total_requested=len(items),
        to_download=to_download,
        to_skip=to_skip,
        to_upgrade=to_upgrade,
        items=items,
    )
