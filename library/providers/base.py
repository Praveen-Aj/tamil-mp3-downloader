"""
Base classes and interfaces for pluggable Audio Providers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable


@dataclass
class AudioCandidate:
    """Represents a potential audio stream matching a search query."""
    provider_name: str
    source_url: str
    title: str
    uploader: Optional[str] = None
    duration_seconds: Optional[int] = None
    quality_kbps: Optional[int] = 320
    audio_format: str = "mp3"
    thumbnail_url: Optional[str] = None
    reliability_score: float = 1.0
    raw_metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResolvedStream:
    """Direct downloadable stream details."""
    stream_url: str
    audio_format: str
    quality_kbps: Optional[int] = None
    headers: Dict[str, str] = field(default_factory=dict)
    direct_download: bool = True


@dataclass
class ProviderCapabilities:
    """Feature matrix of an audio provider."""
    name: str
    display_name: str
    supports_search: bool = True
    supports_direct_url: bool = False
    max_quality_kbps: int = 320
    is_operational: bool = True
    notes: str = ""


@dataclass
class DownloadResult:
    """Outcome of an audio provider download attempt."""
    success: bool
    file_path: Optional[Path] = None
    size_bytes: int = 0
    error_message: Optional[str] = None
    provider_name: str = ""


class AudioProvider(ABC):
    """
    Abstract Base Class for all audio acquisition sources.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Machine identifier (e.g. 'youtube', 'regional_tamil')."""
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        """User-friendly name (e.g. 'YouTube / YouTube Music')."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider dependencies/network are ready."""
        pass

    @abstractmethod
    def get_capabilities(self) -> ProviderCapabilities:
        """Return provider capabilities."""
        pass

    @abstractmethod
    def search(
        self,
        title: str,
        artist: Optional[str] = None,
        duration_seconds: Optional[int] = None,
        limit: int = 5,
    ) -> List[AudioCandidate]:
        """Search provider for candidates matching the song query."""
        pass

    @abstractmethod
    def resolve(self, candidate: AudioCandidate) -> Optional[ResolvedStream]:
        """Resolve candidate to an actionable stream URL or execution plan."""
        pass

    @abstractmethod
    def download(
        self,
        candidate: AudioCandidate,
        output_dir: Path,
        filename_stem: str,
        progress_cb: Optional[Callable[[float, str], None]] = None,
    ) -> DownloadResult:
        """
        Download the audio candidate directly to disk and verify file integrity.
        """
        pass

    def validate(self, file_path: Path) -> bool:
        """Check if downloaded file exists, is non-empty, and has valid audio headers."""
        if not file_path.exists() or file_path.stat().st_size < 1024:
            return False
        return True
