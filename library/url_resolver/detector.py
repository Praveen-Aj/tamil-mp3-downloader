"""
Universal URL detector and resolver dispatcher.
"""

import logging
from typing import Optional, List

from library.url_resolver.base import (
    PlatformResolver, PlatformType, ContentType, ResolvedContent
)
from library.url_resolver.spotify import SpotifyResolver
from library.url_resolver.youtube import YouTubeResolver
from library.url_resolver.direct import DirectUrlResolver

logger = logging.getLogger(__name__)


class UniversalUrlDetector:
    """
    Detects the platform of an input music URL and delegates metadata resolution
    to the appropriate PlatformResolver.
    """

    def __init__(self):
        self.resolvers: List[PlatformResolver] = [
            SpotifyResolver(),
            YouTubeResolver(),
            DirectUrlResolver(),
        ]

    def detect_platform(self, url: str) -> PlatformType:
        """Identify platform type without full resolution."""
        if not url or not isinstance(url, str):
            return PlatformType.UNKNOWN

        clean = url.strip()
        for r in self.resolvers:
            if r.can_handle(clean):
                return r.platform

        return PlatformType.UNKNOWN

    def resolve(self, url: str) -> ResolvedContent:
        """Route URL to corresponding resolver and return ResolvedContent."""
        if not url or not isinstance(url, str) or not url.strip():
            return ResolvedContent(
                platform=PlatformType.UNKNOWN,
                content_type=ContentType.TRACK,
                title="Invalid URL",
                raw_url=url or "",
                error_message="Please paste a valid URL.",
            )

        clean = url.strip()
        if not (clean.startswith("http://") or clean.startswith("https://")):
            return ResolvedContent(
                platform=PlatformType.UNKNOWN,
                content_type=ContentType.TRACK,
                title="Malformed URL",
                raw_url=clean,
                error_message="URL must start with http:// or https://",
            )

        for r in self.resolvers:
            if r.can_handle(clean):
                try:
                    return r.resolve(clean)
                except Exception as e:
                    logger.error(f"Resolver {r.platform.value} failed on URL: {e}", exc_info=True)
                    return ResolvedContent(
                        platform=r.platform,
                        content_type=ContentType.TRACK,
                        title="Analysis Failed",
                        raw_url=clean,
                        error_message=f"Platform resolver error: {e}",
                    )

        return ResolvedContent(
            platform=PlatformType.UNKNOWN,
            content_type=ContentType.TRACK,
            title="Unsupported Platform",
            raw_url=clean,
            error_message=(
                "This URL is not supported. Supported platforms include: "
                "Spotify, YouTube, YouTube Music, TamilMP3/MassTamilan, and direct audio streams."
            ),
        )
