"""
Import Job Schemas for V6 API.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ImportAnalyzeRequest(BaseModel):
    """Payload to analyze a URL (Spotify, YouTube, or Direct URL)."""
    url: str = Field(min_length=5)


class ImportCandidateItem(BaseModel):
    """Candidate track detected from an imported URL."""
    title: str
    artist: Optional[str] = None
    album: Optional[str] = None
    duration_sec: Optional[int] = None
    match_status: str = "UNMATCHED"  # EXACT_MATCH, CANONICAL_EXISTS, NEW
    matched_song_id: Optional[int] = None
    existing_quality: Optional[int] = None


class ImportAnalyzeResponse(BaseModel):
    """Result of analyzing an import URL."""
    url: str
    source_type: str  # spotify, youtube, direct, regional
    title: str
    total_tracks: int
    items: List[ImportCandidateItem] = Field(default_factory=list)


class ImportExecuteRequest(BaseModel):
    """Payload to execute an import job."""
    url: str
    playlist_name: Optional[str] = None
    auto_download: bool = True
