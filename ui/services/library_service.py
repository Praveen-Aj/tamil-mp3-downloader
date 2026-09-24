"""
UI Services - Library Service Adapter (backward compatibility for V5 desktop).

This module re-exports all symbols from `library.service`, which is the core
UI-independent service layer for both the desktop app and the V6 web backend.
"""

from library.service import (
    LibraryService,
    DownloadProgressEvent,
    split_artist_names,
)
from library.service import *  # noqa: F401, F403

__all__ = [
    "LibraryService",
    "DownloadProgressEvent",
    "split_artist_names",
]
