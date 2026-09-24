"""
Chart Schemas for V6 API.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ChartResponse(BaseModel):
    """Chart summary model."""
    id: int
    name: str
    description: Optional[str] = None
    source_url: Optional[str] = None
    frequency: str = "weekly"
    total_entries: int = 0
    downloaded_entries: int = 0
    last_synced_at: Optional[str] = None


class ChartEntryResponse(BaseModel):
    """Chart entry item model."""
    id: int
    chart_id: int
    song_id: int
    rank: int
    previous_rank: Optional[int] = None
    trend: str = "SAME"
    peak_rank: Optional[int] = None
    weeks_on_chart: int = 1
    song_title: str
    artist: Optional[str] = None
    movie: Optional[str] = None
    state: str = "NEW"
    is_downloaded: bool = False
    has_file: bool = False
    file_path: Optional[str] = None


class ChartDetailResponse(ChartResponse):
    """Detailed chart view including ranked tracklist."""
    entries: List[ChartEntryResponse] = Field(default_factory=list)
