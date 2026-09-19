"""
Direct audio URL and Regional Tamil music site URL resolver.
"""

import logging
import re
from pathlib import Path
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse, unquote

from library.url_resolver.base import (
    PlatformResolver, PlatformType, ContentType, TrackMeta, ResolvedContent
)

logger = logging.getLogger(__name__)


class DirectUrlResolver(PlatformResolver):
    """
    Resolves direct audio URLs (.mp3, .m4a, .flac, .wav) and regional Tamil site URLs.
    """

    AUDIO_EXTENSIONS = {".mp3", ".m4a", ".flac", ".wav", ".aac", ".ogg", ".opus"}
    REGIONAL_DOMAINS = ["masstamilan", "tamilmp3", "friendstamilmp3", "isaimini", "kollysongs"]

    @property
    def platform(self) -> PlatformType:
        return PlatformType.DIRECT_AUDIO

    def can_handle(self, url: str) -> bool:
        if not url:
            return False
        clean = url.split("?")[0].lower()
        if any(clean.endswith(ext) for ext in self.AUDIO_EXTENSIONS):
            return True
        if any(ext in url.lower() for ext in self.AUDIO_EXTENSIONS):
            return True
        return any(d in clean for d in self.REGIONAL_DOMAINS)

    def resolve(self, url: str) -> ResolvedContent:
        clean = url.split("?")[0]
        # Check if direct audio file
        ext = Path(clean).suffix.lower()
        if ext not in self.AUDIO_EXTENSIONS:
            from urllib.parse import parse_qs, urlparse
            qs = parse_qs(urlparse(url).query)
            for k in ("path", "file", "url", "src"):
                val = qs.get(k, [None])[0]
                if val and any(val.split("?")[0].lower().endswith(e) for e in self.AUDIO_EXTENSIONS):
                    clean = val.split("?")[0]
                    ext = Path(clean).suffix.lower()
                    break

        if ext in self.AUDIO_EXTENSIONS:
            filename = unquote(Path(clean).stem)
            track = TrackMeta(
                title=filename.replace("-", " ").replace("_", " "),
                track_number=1,
                source_identifier=url,
            )
            return ResolvedContent(
                platform=PlatformType.DIRECT_AUDIO,
                content_type=ContentType.DIRECT_FILE,
                title=filename,
                tracks=[track],
                raw_url=url,
            )

        # Regional Tamil domain URL
        matched_domain = "Tamil Music Site"
        for d in self.REGIONAL_DOMAINS:
            if d in url.lower():
                matched_domain = d.capitalize()
                break

        # Attempt to infer title from URL slug
        path_parts = [p for p in urlparse(url).path.split("/") if p]
        slug = path_parts[-1] if path_parts else "Tamil Album"
        title = unquote(slug).replace("-", " ").replace("_", " ").title()

        track = TrackMeta(
            title=title,
            album=title,
            track_number=1,
            source_identifier=url,
        )

        return ResolvedContent(
            platform=PlatformType.REGIONAL_TAMIL,
            content_type=ContentType.ALBUM,
            title=f"{matched_domain}: {title}",
            owner=matched_domain,
            tracks=[track],
            raw_url=url,
        )
