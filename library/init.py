"""
Library initialization utilities.

Provides functions to initialize the library system and database.
"""

import logging
from pathlib import Path

from config.settings import settings
from library.database import SQLiteDatabase
from library.models import LibraryLocation

logger = logging.getLogger(__name__)


def initialize_library() -> SQLiteDatabase:
    """
    Initialize the library system.

    This function:
    1. Creates the database connection
    2. Runs migrations
    3. Sets up default library location if needed

    Returns:
        SQLiteDatabase instance

    Raises:
        RuntimeError: If library is disabled or initialization fails
    """
    if not settings.library_enabled:
        logger.warning("Library system is disabled in settings")
        raise RuntimeError("Library system is disabled")

    try:
        db_path = settings.library_db_path
        logger.info(f"Initializing library database at: {db_path}")

        # Create database connection
        db = SQLiteDatabase(db_path)
        db.connect()

        # Set up default library location if none exists
        _setup_default_library_location(db)

        logger.info("Library system initialized successfully")
        return db

    except Exception as e:
        logger.error(f"Failed to initialize library system: {e}")
        raise


def _setup_default_library_location(db: SQLiteDatabase) -> None:
    """
    Set up default library location if none exists.

    Args:
        db: SQLiteDatabase instance
    """
    existing_locations = db.get_library_locations()

    if not existing_locations:
        # Create default library location from output_dir
        output_dir = settings.output_dir
        default_location = LibraryLocation(
            path=str(output_dir),
            name="Default Library",
            is_primary=True
        )
        db.add_library_location(default_location)
        logger.info(f"Created default library location: {output_dir}")
    else:
        # Ensure there's a primary location
        primary = db.get_primary_library_location()
        if not primary and existing_locations:
            db.set_primary_library_location(existing_locations[0].id)
            logger.info(f"Set primary library location: {existing_locations[0].name}")


def get_library() -> SQLiteDatabase:
    """
    Get or create library database instance.

    This is a convenience function that initializes the library
    on first call and returns the existing instance on subsequent calls.

    Returns:
        SQLiteDatabase instance

    Raises:
        RuntimeError: If library initialization fails
    """
    global _library_instance

    if _library_instance is None:
        _library_instance = initialize_library()

    return _library_instance


# Global library instance (lazy initialization)
_library_instance: SQLiteDatabase = None
