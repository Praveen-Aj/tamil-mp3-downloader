"""Data models for Tamil MP3 Downloader."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Song:
    """Represents a single downloadable song or ZIP archive."""

    name: str
    url: str
    size_mb: Optional[float] = None
    quality: str = "320kbps"
    album_name: str = ""

    @property
    def is_zip(self) -> bool:
        return ".zip" in self.url.lower()

    @property
    def display_name(self) -> str:
        return re.sub(r"\s+", " ", self.name).strip() or "Unknown Song"

    @property
    def safe_filename(self) -> str:
        """Return a filename-safe version of the name, preserving extension."""
        name = self.display_name
        safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name).strip()
        # keep the extension hint
        if self.is_zip and not safe.lower().endswith(".zip"):
            safe += ".zip"
        elif not self.is_zip and not safe.lower().endswith(".mp3"):
            safe += ".mp3"
        return safe or ("archive.zip" if self.is_zip else "song.mp3")

    @property
    def size_str(self) -> str:
        if self.size_mb is None:
            return "?"
        return f"{self.size_mb:.1f} MB"

    @property
    def quality_color(self) -> str:
        """Rich markup color for quality badge."""
        return "green" if "320" in self.quality else "yellow"


@dataclass
class Album:
    """Represents a movie / album."""

    name: str
    url: str
    year: Optional[int] = None
    song_count: Optional[int] = None
    source: str = "isaimini"

    @property
    def display_name(self) -> str:
        return self.name.strip() or "Unknown Album"

    @property
    def safe_dirname(self) -> str:
        safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", self.display_name).strip()
        return safe or "Unknown Album"

    @property
    def year_str(self) -> str:
        return str(self.year) if self.year else "—"


@dataclass
class DownloadResult:
    """Outcome of a single download attempt."""

    success: bool
    song_name: str = ""
    file_path: Optional[Path] = None
    error_message: Optional[str] = None
    size_downloaded: int = 0
