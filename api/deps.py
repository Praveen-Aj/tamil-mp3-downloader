"""
FastAPI Dependencies for Service and Resource Injection.
"""

from typing import Optional
from pathlib import Path
from config.settings import settings, Settings
from library.service import LibraryService
from library.database import SQLiteDatabase
from library.artwork import ArtworkManager

_service_instance: Optional[LibraryService] = None
_artwork_manager_instance: Optional[ArtworkManager] = None


def get_service() -> LibraryService:
    """Return singleton or configured LibraryService."""
    global _service_instance
    if _service_instance is None:
        _service_instance = LibraryService()
    return _service_instance


def set_service(service: LibraryService) -> None:
    """Override service instance (useful for testing)."""
    global _service_instance
    _service_instance = service


def get_settings() -> Settings:
    """Return global application settings."""
    return settings


def get_artwork_manager() -> ArtworkManager:
    """Return singleton ArtworkManager instance."""
    global _artwork_manager_instance
    if _artwork_manager_instance is None:
        cache_dir = Path("cache/artwork")
        _artwork_manager_instance = ArtworkManager(cache_dir=cache_dir)
    return _artwork_manager_instance
