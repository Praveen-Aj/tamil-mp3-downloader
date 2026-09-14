"""
URL Resolver package for universal media resolution.
"""

from library.url_resolver.base import (
    PlatformResolver, PlatformType, ContentType, TrackMeta, ResolvedContent
)
from library.url_resolver.detector import UniversalUrlDetector
from library.url_resolver.spotify import SpotifyResolver
from library.url_resolver.youtube import YouTubeResolver
from library.url_resolver.direct import DirectUrlResolver

__all__ = [
    "PlatformResolver",
    "PlatformType",
    "ContentType",
    "TrackMeta",
    "ResolvedContent",
    "UniversalUrlDetector",
    "SpotifyResolver",
    "YouTubeResolver",
    "DirectUrlResolver",
]
