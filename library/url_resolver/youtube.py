"""
YouTube and YouTube Music URL resolver.
Enumerates tracks and playlists using yt-dlp flat extraction.
"""

import logging
import re
from typing import Optional, List, Dict, Any

from library.url_resolver.base import (
    PlatformResolver, PlatformType, ContentType, TrackMeta, ResolvedContent
)

logger = logging.getLogger(__name__)


class YouTubeResolver(PlatformResolver):
    """
    Resolves YouTube & YouTube Music video and playlist URLs into TrackMeta.
    """

    YT_WATCH_REGEX = re.compile(r"(?:youtube\.com/watch\?v=|youtu\.be/|music\.youtube\.com/watch\?v=)([a-zA-Z0-9_-]{11})", re.I)
    YT_PLAYLIST_REGEX = re.compile(r"[?&]list=([a-zA-Z0-9_-]+)", re.I)

    @property
    def platform(self) -> PlatformType:
        return PlatformType.YOUTUBE

    def can_handle(self, url: str) -> bool:
        if not url:
            return False
        return "youtube.com" in url.lower() or "youtu.be" in url.lower()

    def resolve(self, url: str) -> ResolvedContent:
        """Resolve YouTube URL using yt-dlp flat inspection."""
        try:
            import yt_dlp
        except ImportError:
            return ResolvedContent(
                platform=self.platform,
                content_type=ContentType.TRACK,
                title="YouTube Link",
                raw_url=url,
                error_message="yt-dlp is required to analyze YouTube URLs.",
            )

        is_playlist = bool(self.YT_PLAYLIST_REGEX.search(url))
        content_type = ContentType.PLAYLIST if is_playlist else ContentType.TRACK

        ydl_opts = {
            "extract_flat": True,
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    return ResolvedContent(
                        platform=self.platform,
                        content_type=content_type,
                        title="Unavailable Content",
                        raw_url=url,
                        error_message="YouTube returned empty metadata (video/playlist may be private or deleted).",
                    )

                # Determine if yt-dlp treated it as a playlist
                entries = info.get("entries")
                if entries is not None:
                    # Playlist
                    pl_title = info.get("title") or "YouTube Playlist"
                    uploader = info.get("uploader") or info.get("channel")
                    tracks: List[TrackMeta] = []
                    artwork = None

                    for idx, e in enumerate(entries, start=1):
                        if not e:
                            continue
                        e_id = e.get("id")
                        e_title = e.get("title") or f"Track {idx}"
                        e_dur = int(e.get("duration") or 0) or None
                        e_artist = e.get("uploader") or e.get("channel") or uploader
                        e_thumb = e.get("thumbnail")
                        if not artwork and e_thumb:
                            artwork = e_thumb

                        tm = TrackMeta(
                            title=e_title,
                            artist=e_artist,
                            duration_seconds=e_dur,
                            track_number=idx,
                            artwork_url=e_thumb,
                            source_identifier=e_id,
                            raw_info=e,
                        )
                        tracks.append(tm)

                    return ResolvedContent(
                        platform=self.platform,
                        content_type=ContentType.PLAYLIST,
                        title=pl_title,
                        owner=uploader,
                        tracks=tracks,
                        artwork_url=artwork,
                        raw_url=url,
                    )
                else:
                    # Single video
                    v_title = info.get("title") or "YouTube Track"
                    uploader = info.get("uploader") or info.get("channel")
                    duration = int(info.get("duration") or 0) or None
                    artwork = info.get("thumbnail")

                    track = TrackMeta(
                        title=v_title,
                        artist=uploader,
                        duration_seconds=duration,
                        track_number=1,
                        artwork_url=artwork,
                        source_identifier=info.get("id"),
                        raw_info=info,
                    )

                    return ResolvedContent(
                        platform=self.platform,
                        content_type=ContentType.TRACK,
                        title=v_title,
                        owner=uploader,
                        tracks=[track],
                        artwork_url=artwork,
                        raw_url=url,
                    )

        except Exception as e:
            err_msg = str(e)
            if "Private video" in err_msg or "Sign in" in err_msg:
                return ResolvedContent(
                    platform=self.platform,
                    content_type=content_type,
                    title="Private Video / Playlist",
                    raw_url=url,
                    auth_required=True,
                    error_message="This YouTube video or playlist requires authentication or is set to private.",
                )
            return ResolvedContent(
                platform=self.platform,
                content_type=content_type,
                title="Error Analyzing YouTube Link",
                raw_url=url,
                error_message=f"YouTube error: {err_msg}",
            )
