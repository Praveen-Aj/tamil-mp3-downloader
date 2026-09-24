"""
Song Schemas for V6 API.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class SongSourceResponse(BaseModel):
    """Song source metadata model."""
    id: Optional[int] = None
    source_name: str
    source_url: str
    quality: int = 128
    format: str = "mp3"
    bitrate: Optional[str] = None
    size_bytes: Optional[int] = None
    is_available: bool = True


class SongResponse(BaseModel):
    """Song summary and detail model."""
    id: int
    canonical_hash: str
    title: str
    artist: Optional[str] = None
    album: Optional[str] = None
    year: Optional[int] = None
    state: str = "NEW"
    rating: Optional[int] = None
    is_favorite: bool = False
    has_file: bool = False
    file_path: Optional[str] = None
    quality: Optional[int] = None
    movies: List[Dict[str, Any]] = Field(default_factory=list)
    artists: List[Dict[str, Any]] = Field(default_factory=list)
    sources_count: int = 0
    created_at: Optional[str] = None


class SongFilterParams(BaseModel):
    """Query parameters for song filtering and search."""
    query: str = ""
    state: Optional[str] = None
    min_quality: Optional[int] = None
    year: Optional[int] = None
    favorites_only: bool = False
    min_rating: Optional[int] = None
    page: int = 1
    page_size: int = 50
    sort_by: str = "title"
    sort_dir: str = "asc"


class SongRatingUpdate(BaseModel):
    """Request model for updating song rating."""
    rating: Optional[int] = Field(default=None, ge=1, le=5)


class SongFavoriteUpdate(BaseModel):
    """Request model for toggling song favorite."""
    is_favorite: Optional[bool] = None
