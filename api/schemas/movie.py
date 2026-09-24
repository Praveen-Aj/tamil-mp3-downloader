"""
Movie Schemas for V6 API.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class MovieResponse(BaseModel):
    """Movie summary model."""
    id: int
    name: str
    year: Optional[int] = None
    poster_url: Optional[str] = None
    songs_count: int = 0
    downloaded_count: int = 0
    created_at: Optional[str] = None


class MovieDetailResponse(MovieResponse):
    """Detailed movie view including cast, crew, and tracklist."""
    actors: List[str] = Field(default_factory=list)
    composers: List[str] = Field(default_factory=list)
    songs: List[Dict[str, Any]] = Field(default_factory=list)
