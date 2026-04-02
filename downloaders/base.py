"""
Base downloader class for handling file downloads.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional
from models.song import Song, DownloadResult


class BaseDownloader(ABC):
    """Abstract base class for all downloaders."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def download_song(self, song: Song) -> DownloadResult:
        """
        Download a single song.

        Args:
            song: Song object to download

        Returns:
            DownloadResult with success status and details
        """
        pass

    def download_songs(self, songs: List[Song]) -> List[DownloadResult]:
        """
        Download multiple songs.

        Args:
            songs: List of Song objects to download

        Returns:
            List of DownloadResult objects
        """
        results = []
        for song in songs:
            result = self.download_song(song)
            results.append(result)
        return results

    def get_output_path(self, song: Song, subfolder: Optional[str] = None) -> Path:
        """
        Get the output path for a song.

        Args:
            song: Song object
            subfolder: Optional subfolder name

        Returns:
            Path object for the output file
        """
        if subfolder:
            output_dir = self.output_dir / subfolder
            output_dir.mkdir(parents=True, exist_ok=True)
        else:
            output_dir = self.output_dir

        # Clean filename
        filename = "".join(c for c in song.name if c.isalnum() or c in '._- ').strip()
        if not filename:
            filename = f"song_{hash(song.url) % 10000}"

        # Add extension if not present
        if not filename.lower().endswith(('.mp3', '.zip', '.wav', '.m4a')):
            if song.url.lower().endswith('.zip'):
                filename += '.zip'
            else:
                filename += '.mp3'

        return output_dir / filename
