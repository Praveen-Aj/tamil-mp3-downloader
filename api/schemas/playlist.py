"""
Playlist Schemas for V6 API.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class PlaylistCreate(BaseModel):
    """Payload to create a new user playlist."""
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = Field(default="", max_length=500)


class PlaylistUpdate(BaseModel):
    """Payload to update an existing playlist."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)


class PlaylistItemAdd(BaseModel):
    """Payload to append a song to a playlist."""
    song_id: int


class PlaylistItemMove(BaseModel):
    """Payload to reorder a playlist item."""
    direction: str = Field(pattern="^(up|down)$")


class PlaylistItemResponse(BaseModel):
    """Song item within a playlist."""
    id: int
    playlist_id: int
    song_id: int
    position: int
    title: str
    artist: Optional[str] = None
    album: Optional[str] = None
    state: str = "NEW"
    is_downloaded: bool = False
    has_file: bool = False
    file_path: Optional[str] = None
    rating: Optional[int] = None
    is_favorite: bool = False


class PlaylistResponse(BaseModel):
    """Playlist summary model."""
    id: int
    name: str
    description: Optional[str] = None
    song_count: int = 0
    downloaded_count: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class PlaylistDetailResponse(PlaylistResponse):
    """Detailed playlist view with items."""
    items: List[PlaylistItemResponse] = Field(default_factory=list)
