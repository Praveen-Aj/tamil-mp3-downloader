"""
Base scraper class for Tamil MP3 sources.
"""

from abc import ABC, abstractmethod
from typing import Callable, List, Optional
from models.song import Album, Song


class BaseScraper(ABC):
    """Abstract base class for all music source scrapers."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip('/')

    @abstractmethod
    def get_albums(
        self,
        category: str = "latest",
        max_pages: int = 3,
        progress_cb: Optional[Callable[[int, int], None]] = None,
    ) -> List[Album]:
        """
        Get list of available albums/movies.

        Args:
            category: Category to fetch (e.g., "latest", "old", etc.)

        Returns:
            List of Album objects
        """
        pass

    @abstractmethod
    def get_songs(self, album: Album) -> List[Song]:
        """
        Get songs from a specific album.

        Args:
            album: Album object to get songs for

        Returns:
            List of Song objects
        """
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """
        Test if the source is accessible.

        Returns:
            True if accessible, False otherwise
        """
        pass

    def get_source_name(self) -> str:
        """Get the name of this source."""
        return self.__class__.__name__.replace('Scraper', '').lower()
