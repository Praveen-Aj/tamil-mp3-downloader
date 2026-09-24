"""
Artist Schemas for V6 API.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ArtistResponse(BaseModel):
    """Artist summary model."""
    id: int
    name: str
    image_url: Optional[str] = None
    role: Optional[str] = None
    songs_count: int = 0
    downloaded_count: int = 0
    movies_count: int = 0


class ArtistDetailResponse(ArtistResponse):
    """Detailed artist view including discography and filmography."""
    songs: List[Dict[str, Any]] = Field(default_factory=list)
    movies: List[Dict[str, Any]] = Field(default_factory=list)
