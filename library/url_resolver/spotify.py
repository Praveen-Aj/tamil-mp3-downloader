"""
Spotify metadata resolver for tracks, albums, and playlists.
Extracts rich canonical metadata using public web embed data and oEmbed without API keys.
"""

import html
import json
import logging
import re
from typing import Optional, List, Dict, Any
import requests

from library.url_resolver.base import (
    PlatformResolver, PlatformType, ContentType, TrackMeta, ResolvedContent
)

logger = logging.getLogger(__name__)


class SpotifyResolver(PlatformResolver):
    """
    Resolves Spotify Track, Album, and Playlist URLs into structured TrackMeta.
    Does NOT require Spotify Developer credentials.
    """

    TRACK_REGEX = re.compile(r"open\.spotify\.com/(?:intl-[a-z]+/)?track/([a-zA-Z0-9]+)", re.I)
    ALBUM_REGEX = re.compile(r"open\.spotify\.com/(?:intl-[a-z]+/)?album/([a-zA-Z0-9]+)", re.I)
    PLAYLIST_REGEX = re.compile(r"open\.spotify\.com/(?:intl-[a-z]+/)?playlist/([a-zA-Z0-9]+)", re.I)

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    @property
    def platform(self) -> PlatformType:
        return PlatformType.SPOTIFY

    def can_handle(self, url: str) -> bool:
        if not url:
            return False
        return bool(
            self.TRACK_REGEX.search(url)
            or self.ALBUM_REGEX.search(url)
            or self.PLAYLIST_REGEX.search(url)
        )

    def resolve(self, url: str) -> ResolvedContent:
        """Analyze Spotify URL and return structured content."""
        clean_url = url.split("?")[0].strip()

        # 1. Track
        m_track = self.TRACK_REGEX.search(clean_url)
        if m_track:
            track_id = m_track.group(1)
            return self._resolve_track(track_id, clean_url)

        # 2. Album
        m_album = self.ALBUM_REGEX.search(clean_url)
        if m_album:
            album_id = m_album.group(1)
            return self._resolve_collection(album_id, clean_url, ContentType.ALBUM)

        # 3. Playlist
        m_pl = self.PLAYLIST_REGEX.search(clean_url)
        if m_pl:
            pl_id = m_pl.group(1)
            return self._resolve_collection(pl_id, clean_url, ContentType.PLAYLIST)

        return ResolvedContent(
            platform=self.platform,
            content_type=ContentType.TRACK,
            title="Unsupported Spotify URL",
            raw_url=url,
            error_message="Could not parse Spotify track, album, or playlist ID.",
        )

    def _resolve_track(self, track_id: str, url: str) -> ResolvedContent:
        """Extract metadata for a single Spotify track."""
        # Query oEmbed API first for basic title and thumbnail
        oembed_url = f"https://open.spotify.com/oembed?url=https://open.spotify.com/track/{track_id}"
        title = "Spotify Track"
        artist = ""
        artwork_url = None

        try:
            resp = requests.get(oembed_url, headers=self.HEADERS, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                title = data.get("title", title)
                artwork_url = data.get("thumbnail_url")
        except Exception as e:
            logger.debug(f"oEmbed fetch failed for track {track_id}: {e}")

        # Fetch embed page for precise duration and artist details
        embed_url = f"https://open.spotify.com/embed/track/{track_id}"
        duration_sec = None
        album_name = None

        try:
            resp = requests.get(embed_url, headers=self.HEADERS, timeout=10)
            if resp.status_code == 200:
                html_text = resp.text
                extracted = self._extract_json_from_html(html_text)
                if extracted:
                    entity = extracted.get("entity", {}) or extracted
                    if "name" in entity:
                        title = entity["name"]
                    artists = entity.get("artists") or []
                    if artists and isinstance(artists, list):
                        artist = ", ".join(a.get("name", "") for a in artists if isinstance(a, dict))
                    album_obj = entity.get("album") or {}
                    album_name = album_obj.get("name")
                    duration_ms = entity.get("duration_ms") or entity.get("duration")
                    if duration_ms:
                        duration_sec = int(duration_ms) // 1000
                    if not artwork_url:
                        images = album_obj.get("images") or entity.get("images") or []
                        if images and isinstance(images, list):
                            artwork_url = images[0].get("url")
        except Exception as e:
            logger.debug(f"Embed scrape error for track {track_id}: {e}")

        track = TrackMeta(
            title=title,
            artist=artist,
            album=album_name,
            duration_seconds=duration_sec,
            track_number=1,
            artwork_url=artwork_url,
            source_identifier=track_id,
        )

        return ResolvedContent(
            platform=self.platform,
            content_type=ContentType.TRACK,
            title=title,
            owner=artist,
            tracks=[track],
            artwork_url=artwork_url,
            raw_url=url,
        )

    def _resolve_collection(
        self,
        collection_id: str,
        url: str,
        content_type: ContentType,
    ) -> ResolvedContent:
        """Resolve an album or playlist collection into a list of TrackMeta."""
        kind_str = "album" if content_type == ContentType.ALBUM else "playlist"
        embed_url = f"https://open.spotify.com/embed/{kind_str}/{collection_id}"

        try:
            resp = requests.get(embed_url, headers=self.HEADERS, timeout=15)
            if resp.status_code == 404:
                return ResolvedContent(
                    platform=self.platform,
                    content_type=content_type,
                    title="Playlist Not Found",
                    raw_url=url,
                    error_message="The requested Spotify playlist or album could not be found (404).",
                )
            elif resp.status_code in [401, 403]:
                return ResolvedContent(
                    platform=self.platform,
                    content_type=content_type,
                    title="Private Playlist",
                    raw_url=url,
                    auth_required=True,
                    error_message="This Spotify playlist is private or requires authentication.",
                )

            html_text = resp.text
            extracted = self._extract_json_from_html(html_text)
            if not extracted:
                # Fallback to regex track extraction from HTML
                return self._fallback_html_collection(html_text, collection_id, url, content_type)

            entity = extracted.get("entity", {}) or extracted
            collection_title = entity.get("name") or entity.get("title") or f"Spotify {kind_str.title()}"
            owner_name = ""
            artists = entity.get("artists") or []
            if artists:
                owner_name = ", ".join(a.get("name", "") for a in artists if isinstance(a, dict))
            elif "owner" in entity and isinstance(entity["owner"], dict):
                owner_name = entity["owner"].get("name", "")

            artwork_url = None
            images = entity.get("images") or []
            if images and isinstance(images, list):
                artwork_url = images[0].get("url")

            # Extract tracklist
            raw_tracks = []
            if "trackList" in entity and isinstance(entity["trackList"], list):
                raw_tracks = entity["trackList"]
            elif "tracks" in entity:
                t_obj = entity["tracks"]
                if isinstance(t_obj, list):
                    raw_tracks = t_obj
                elif isinstance(t_obj, dict) and "items" in t_obj:
                    raw_tracks = t_obj["items"]

            tracks: List[TrackMeta] = []
            for idx, item in enumerate(raw_tracks, start=1):
                t = item.get("track") if "track" in item and isinstance(item["track"], dict) else item
                t_title = t.get("name") or t.get("title") or f"Track {idx}"
                t_artist = ""
                if "artists" in t and isinstance(t["artists"], list):
                    t_artist = ", ".join(a.get("name", "") for a in t["artists"] if isinstance(a, dict))
                elif "artist" in t:
                    t_artist = str(t["artist"])
                elif not t_artist:
                    t_artist = owner_name

                t_duration = t.get("duration") or t.get("duration_ms")
                dur_sec = int(t_duration) // 1000 if t_duration else None

                t_meta = TrackMeta(
                    title=html.unescape(t_title),
                    artist=html.unescape(t_artist) if t_artist else None,
                    album=collection_title if content_type == ContentType.ALBUM else None,
                    duration_seconds=dur_sec,
                    track_number=idx,
                    artwork_url=artwork_url,
                    source_identifier=t.get("id") or t.get("uri"),
                )
                tracks.append(t_meta)

            if not tracks:
                return self._fallback_html_collection(html_text, collection_id, url, content_type)

            return ResolvedContent(
                platform=self.platform,
                content_type=content_type,
                title=collection_title,
                owner=owner_name,
                tracks=tracks,
                artwork_url=artwork_url,
                raw_url=url,
            )

        except Exception as e:
            logger.error(f"Error resolving Spotify collection {collection_id}: {e}", exc_info=True)
            return ResolvedContent(
                platform=self.platform,
                content_type=content_type,
                title="Error Analyzing Spotify Link",
                raw_url=url,
                error_message=f"Failed to fetch Spotify metadata: {e}",
            )

    def _extract_json_from_html(self, html_text: str) -> Optional[Dict[str, Any]]:
        """Search HTML for embedded state JSON in <script id="__NEXT_DATA__"> or similar."""
        # 1. Check __NEXT_DATA__
        m_next = re.search(r'<script\s+id="__NEXT_DATA__"\s+type="application/json">(.*?)</script>', html_text, re.S)
        if m_next:
            try:
                data = json.loads(m_next.group(1))
                props = data.get("props", {}).get("pageProps", {})
                state = props.get("state", {}).get("data", {})
                if state:
                    return state
                return props
            except Exception:
                pass

        # 2. Check Spotify resource script tags
        m_resource = re.search(r'<script\s+id="initial-state"\s+type="text/plain">(.*?)</script>', html_text, re.S)
        if m_resource:
            try:
                import base64
                decoded = base64.b64decode(m_resource.group(1)).decode("utf-8")
                return json.loads(decoded)
            except Exception:
                pass

        return None

    def _fallback_html_collection(
        self,
        html_text: str,
        collection_id: str,
        url: str,
        content_type: ContentType,
    ) -> ResolvedContent:
        """Regex fallback to extract track titles from embed HTML."""
        track_matches = re.findall(r'<span[^>]*class="[^"]*track-title[^"]*"[^>]*>(.*?)</span>', html_text, re.I)
        tracks = []
        for idx, title_match in enumerate(track_matches, start=1):
            clean = html.unescape(re.sub(r"<.*?>", "", title_match).strip())
            if clean:
                tracks.append(TrackMeta(title=clean, track_number=idx))

        title = f"Spotify {content_type.value} ({collection_id})"
        return ResolvedContent(
            platform=self.platform,
            content_type=content_type,
            title=title,
            tracks=tracks,
            raw_url=url,
            error_message=None if tracks else "Could not enumerate tracks from Spotify collection page.",
        )
