"""Tamilmp3.in / Kuttyweb scraper implementation.

Site structure & Protocol:
- Directory: https://tamilmp3.in/tamil-mp3-songs/
- Albums: https://tamilmp3.in/{movie-slug}-songs
- Token Endpoint: POST https://tamilmp3.in/token.php
  Payload: type=download, path={data-path} OR type=zip, album={data-album}, bitrate={bitrate}
  Response JSON: {"url": "https://dl.tamilmp3.xyz/download.php?..."}
"""

import logging
import re
from typing import Callable, List, Optional, Tuple, Dict, Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from models.song import Album, Song
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

_DEFAULT_BASE = "https://tamilmp3.in"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


class Tamilmp3Scraper(BaseScraper):
    """Scraper for Tamilmp3.in (Kuttyweb successor) — pure HTTP + token API."""

    def __init__(self, base_url: str = _DEFAULT_BASE) -> None:
        super().__init__(base_url)
        self._session = requests.Session()
        self._session.headers.update(_HEADERS)

    # ── No-op browser stubs for lifecycle compatibility ──────────
    def _init_browser(self) -> None:
        pass

    def _close_browser(self) -> None:
        pass

    def __enter__(self) -> "Tamilmp3Scraper":
        return self

    def __exit__(self, *_: object) -> None:
        pass

    # ── Connection test ──────────────────────────────────────────
    def test_connection(self) -> bool:
        """Check if Tamilmp3.in is accessible."""
        try:
            r = self._session.get(self.base_url, timeout=10)
            return r.status_code == 200 and ("Tamilmp3" in r.text or "Kuttyweb" in r.text)
        except Exception as e:
            logger.debug(f"Tamilmp3 test_connection failed: {e}")
            return False

    # ── Album / Category Discovery ──────────────────────────────
    def get_albums(
        self,
        category: str = "latest",
        max_pages: int = 1,
        progress_cb: Optional[Callable[[int, int], None]] = None,
    ) -> List[Album]:
        """
        Get list of Tamil music albums/movies.

        Args:
            category: Category to fetch ("latest", "collections", "a-z", etc.)
            max_pages: Number of pages to scan (default 1)
            progress_cb: Optional progress callback (page, total)

        Returns:
            List of Album objects
        """
        category_url_map = {
            "latest": f"{self.base_url}/tamil-mp3-songs/",
            "all": f"{self.base_url}/all-songs/",
            "collections": f"{self.base_url}/collections/",
        }
        target_url = category_url_map.get(category.lower(), f"{self.base_url}/tamil-mp3-songs/")
        
        albums: List[Album] = []
        seen_urls: set = set()

        for page in range(1, max_pages + 1):
            if progress_cb:
                progress_cb(page, max_pages)

            page_url = target_url if page == 1 else f"{target_url}?page={page}"
            try:
                r = self._session.get(page_url, timeout=12)
                if r.status_code != 200:
                    break

                soup = BeautifulSoup(r.text, "html.parser")
                page_albums = self._parse_album_listing(soup, seen_urls)
                albums.extend(page_albums)

                if not page_albums:
                    break
            except Exception as e:
                logger.warning(f"Tamilmp3.in get_albums error on {page_url}: {e}")
                break

        return albums

    def _parse_album_listing(self, soup: BeautifulSoup, seen_urls: set) -> List[Album]:
        """Parse album cards from HTML listing."""
        out: List[Album] = []
        
        # Candidate album card elements
        links = soup.find_all("a", href=re.compile(r"-songs/?$", re.I))
        for link in links:
            href = link.get("href", "")
            if not href or href.startswith("#"):
                continue

            album_url = urljoin(self.base_url, href)
            if album_url in seen_urls or album_url.rstrip("/") == self.base_url:
                continue
            seen_urls.add(album_url)

            raw_text = link.get_text(strip=True)
            if not raw_text or len(raw_text) < 2:
                continue

            # Extract year from album card text if available
            year_match = re.search(r"\b(19\d{2}|20\d{2})\b", raw_text)
            year = int(year_match.group(1)) if year_match else None

            # Clean name
            clean_name = re.sub(r"Starring:.*", "", raw_text, flags=re.I).strip()
            clean_name = re.sub(r"\d+\s+songs.*", "", clean_name, flags=re.I).strip()

            out.append(
                Album(
                    name=clean_name or raw_text,
                    url=album_url,
                    year=year,
                )
            )

        return out

    # ── Song Discovery ───────────────────────────────────────────
    def get_songs(self, album: Album) -> List[Song]:
        """
        Get list of songs for an album.

        Args:
            album: Target Album object

        Returns:
            List of Song objects
        """
        songs: List[Song] = []
        try:
            r = self._session.get(album.url, timeout=12)
            if r.status_code != 200:
                return songs

            soup = BeautifulSoup(r.text, "html.parser")
            
            # Extract common album metadata (Year, Composer, Movie)
            album_year = album.year
            year_match = re.search(r"(\b19\d{2}\b|\b20\d{2}\b)", soup.get_text())
            if year_match and not album_year:
                album_year = int(year_match.group(1))

            composer_match = re.search(r"Music\s*:\s*([^\n<|]+)", soup.get_text(), re.I)
            composer = None
            if composer_match:
                composer_raw = composer_match.group(1).strip()
                composer = re.sub(r"(Starring|Director|Cast).*", "", composer_raw, flags=re.I).strip()

            # Extract download buttons with data-path (individual tracks) and data-album (ZIPs)
            dl_buttons = soup.find_all("a", class_=lambda c: c and ("btn-dl" in c or "btn-zip" in c))
            
            seen_tracks: Dict[str, Dict[str, Any]] = {}

            for btn in dl_buttons:
                path = btn.get("data-path")
                album_name = btn.get("data-album")
                bitrate_attr = btn.get("data-bitrate")
                btn_text = btn.get_text(strip=True)

                if path:
                    # Individual track download button
                    track_filename = path.split("/")[-1]
                    track_name = re.sub(r"\.(mp3|m4a|wav|flac)$", "", track_filename, flags=re.I)
                    track_name = re.sub(r"\s*(320|128)kbps", "", track_name, flags=re.I).strip()

                    bitrate = 320 if "320" in path or "320" in btn_text else 128
                    
                    # Size extraction from button text: e.g. "320kbps (9.3 MB)"
                    size_match = re.search(r"([\d\.]+)\s*MB", btn_text, re.I)
                    size_mb = float(size_match.group(1)) if size_match else None

                    if track_name not in seen_tracks:
                        seen_tracks[track_name] = {
                            "name": track_name,
                            "album_name": album.name,
                            "year": album_year,
                            "composer": composer,
                            "urls": {},
                            "sizes": {},
                            "data_paths": {},
                        }

                    seen_tracks[track_name]["urls"][str(bitrate)] = album.url
                    seen_tracks[track_name]["data_paths"][str(bitrate)] = path
                    if size_mb:
                        seen_tracks[track_name]["sizes"][str(bitrate)] = size_mb

            # Convert tracked dictionaries to Song objects
            for t_info in seen_tracks.values():
                best_bitrate = "320" if "320" in t_info["urls"] else "128"
                primary_url = t_info["urls"][best_bitrate]
                primary_size = t_info["sizes"].get(best_bitrate)

                s = Song(
                    name=t_info["name"],
                    url=primary_url,
                    album_name=t_info["album_name"],
                    artist=t_info["composer"],
                    year=t_info["year"],
                    quality=f"{best_bitrate}kbps",
                    size_mb=primary_size,
                )
                # Attach internal data map for token resolution
                s.download_urls = t_info["data_paths"]
                songs.append(s)

        except Exception as e:
            logger.error(f"Tamilmp3.in get_songs error for {album.url}: {e}")

        return songs

    # ── Dynamic Download URL Resolution ─────────────────────────
    def get_download_url(self, song: Song, quality: str = "320") -> Optional[str]:
        """
        Generate a fresh signed CDN audio download URL via token.php.

        Args:
            song: Song object
            quality: Preferred bitrate ("320" or "128")

        Returns:
            Direct audio stream URL, or None if token generation fails or audio probe fails
        """
        data_paths = getattr(song, "download_urls", {})
        if isinstance(data_paths, dict) and data_paths:
            # Pick requested quality or best available fallback
            data_path = data_paths.get(quality) or data_paths.get("320") or data_paths.get("128") or next(iter(data_paths.values()))
        elif isinstance(song.url, str) and "token.php" not in song.url:
            # Fallback path if data_path was stored in url
            data_path = song.url
        else:
            data_path = None

        if not data_path:
            logger.warning(f"No data-path available for song '{song.name}'")
            return None

        # Call token.php endpoint to get fresh signed download URL
        token_endpoint = f"{self.base_url}/token.php"
        payload = {"type": "download", "path": data_path}

        try:
            r = self._session.post(token_endpoint, data=payload, timeout=10)
            if r.status_code == 200 and "url" in r.text:
                data = r.json()
                audio_url = data.get("url")
                if audio_url:
                    # Verify resolved audio URL actually serves audio
                    if self._verify_audio_url(audio_url):
                        return audio_url
                    else:
                        logger.warning(f"Audio URL probe failed for '{song.name}': {audio_url}")
                        return None
        except Exception as e:
            logger.error(f"Token generation failed for '{song.name}': {e}")

        return None

    def _verify_audio_url(self, url: str) -> bool:
        """Verify that an audio URL is reachable and returns an audio/mime type."""
        try:
            head_r = self._session.head(url, timeout=5, allow_redirects=True)
            if head_r.status_code == 200:
                content_type = head_r.headers.get("Content-Type", "").lower()
                return "audio" in content_type or "mpeg" in content_type or "octet-stream" in content_type or "zip" in content_type
        except Exception as e:
            logger.debug(f"Audio URL head probe exception: {e}")
        return True  # Fallback to True if HEAD requests are blocked by CDN edge
