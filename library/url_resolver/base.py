"""
Base interfaces and data structures for URL and playlist platform resolvers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any


class PlatformType(Enum):
    """Identified streaming or audio platform."""
    SPOTIFY = "Spotify"
    YOUTUBE = "YouTube"
    YOUTUBE_MUSIC = "YouTube Music"
    REGIONAL_TAMIL = "Tamil Regional Music"
    DIRECT_AUDIO = "Direct Audio"
    UNKNOWN = "Unknown"


class ContentType(Enum):
    """Type of resolved media content."""
    TRACK = "Track"
    ALBUM = "Album"
    PLAYLIST = "Playlist"
    DIRECT_FILE = "Direct File"


@dataclass
class TrackMeta:
    """Canonical metadata extracted for a track from a playlist or URL."""
    title: str
    artist: Optional[str] = None
    album: Optional[str] = None
    duration_seconds: Optional[int] = None
    track_number: Optional[int] = None
    year: Optional[int] = None
    artwork_url: Optional[str] = None
    isrc: Optional[str] = None
    source_identifier: Optional[str] = None
    raw_info: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResolvedContent:
    """Complete structured metadata output of resolving a URL or playlist."""
    platform: PlatformType
    content_type: ContentType
    title: str
    owner: Optional[str] = None
    tracks: List[TrackMeta] = field(default_factory=list)
    artwork_url: Optional[str] = None
    raw_url: str = ""
    auth_required: bool = False
    error_message: Optional[str] = None

    @property
    def track_count(self) -> int:
        return len(self.tracks)

    @property
    def is_valid(self) -> bool:
        return self.error_message is None and len(self.tracks) > 0


class PlatformResolver(ABC):
    """Abstract Base Class for platform URL resolvers."""

    @property
    @abstractmethod
    def platform(self) -> PlatformType:
        """Target platform."""
        pass

    @abstractmethod
    def can_handle(self, url: str) -> bool:
        """Check if resolver recognizes URL format."""
        pass

    @abstractmethod
    def resolve(self, url: str) -> ResolvedContent:
        """Extract metadata and tracklist from target URL."""
        pass
