"""
Library module for Tamil MP3 Downloader.

This module provides:
- Persistent SQLite-based music library
- Canonical song identity system
- Cross-category/source deduplication
- Download planning and execution
- Library import from existing files
"""

from library.database import SQLiteDatabase
from library.models import LibrarySong, SongSource, Download, LibraryLocation
from library.canonical import CanonicalIdentity, compute_canonical_hash
from library.migrator import DatabaseMigrator
from library.init import initialize_library, get_library
from library.discovery import DiscoveryPipeline, song_to_canonical
from library.planner import DownloadPlanner, DownloadPlan, SourceSelection, UpgradePlan
from library.registry import DownloadRegistry

__all__ = [
    'SQLiteDatabase',
    'LibrarySong',
    'SongSource',
    'Download',
    'LibraryLocation',
    'CanonicalIdentity',
    'compute_canonical_hash',
    'DatabaseMigrator',
    'initialize_library',
    'get_library',
    'DiscoveryPipeline',
    'song_to_canonical',
    'DownloadPlanner',
    'DownloadPlan',
    'SourceSelection',
    'UpgradePlan',
    'DownloadRegistry',
]
