"""FriendsTamilMP3 scraper implementation.

This scraper targets the query-parameter based pages used by friendstamilmp3.in
and extracts:
- Album listings from `spage=` links on category pages
- Song links from album pages that expose direct audio URLs
"""

import logging
import re
from typing import Dict, List, Optional, Set
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from models.song import Album, Song
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class FriendsTamilMP3Scraper(BaseScraper):
    """Scraper for FriendsTamilMP3."""

    _AUDIO_EXTENSIONS = (".mp3", ".zip", ".m4a", ".aac", ".wav", ".flac")
    _ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    def __init__(self, base_url: str = "https://www.friendstamilmp3.in") -> None:
        super().__init__(base_url)
        self._session: requests.Session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.9",
            }
        )

    # Compatibility hooks: current CLI calls these lifecycle methods on all scrapers.
    def _init_browser(self) -> None:
        """No-op for this HTTP scraper."""
        return

    def _close_browser(self) -> None:
        """No-op for this HTTP scraper."""
        return

    def __enter__(self) -> "FriendsTamilMP3Scraper":
        return self

    def __exit__(self, *_: object) -> None:
        return

    def test_connection(self) -> bool:
        try:
            resp = self._session.get(self.base_url, timeout=20)
            return resp.status_code == 200
        except Exception as exc:
            logger.warning("FriendsTamilMP3 connection test failed: %s", exc)
            return False

    def get_albums(self, category: str = "latest", max_pages: int = 3) -> List[Album]:
        """Get albums for a category.

        Categories supported:
        - latest: New releases page
        - 2026 / 2025: A-Z pages filtered by year from title
        - old: old collections pages
        """
        pages = self._category_pages(category=category, max_pages=max_pages)
        albums: List[Album] = []
        seen_urls: Set[str] = set()

        for page_url in pages:
            html = self._fetch_html(page_url)
            if not html:
                continue

            page_albums = self._extract_albums_from_page(html=html, category=category)
            for album in page_albums:
                if album.url in seen_urls:
                    continue
                seen_urls.add(album.url)
                albums.append(album)

        return albums

    def get_songs(self, album: Album) -> List[Song]:
        """Extract song links from an album page."""
        html = self._fetch_html(album.url)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        songs: List[Song] = []
        seen_urls: Set[str] = set()

        for anchor in soup.find_all("a", href=True):
            href = anchor.get("href", "").strip()
            if not href:
                continue
            absolute_url = urljoin(self.base_url + "/", href)
            lower_href = absolute_url.lower()
            if not lower_href.endswith(self._AUDIO_EXTENSIONS):
                continue
            if absolute_url in seen_urls:
                continue
            seen_urls.add(absolute_url)

            name = self._song_name_from_anchor(anchor_text=anchor.get_text(" ", strip=True), url=absolute_url)
            quality = "320kbps" if "320" in lower_href else "unknown"
            songs.append(
                Song(
                    name=name,
                    url=absolute_url,
                    size_mb=None,
                    quality=quality,
                    album_name=album.display_name,
                )
            )

        return songs

    def _fetch_html(self, url: str) -> Optional[str]:
        try:
            resp = self._session.get(url, timeout=30)
            if resp.status_code != 200:
                logger.warning("FriendsTamilMP3 returned %s for %s", resp.status_code, url)
                return None
            return resp.text
        except Exception as exc:
            logger.warning("FriendsTamilMP3 request failed for %s: %s", url, exc)
            return None

    def _category_pages(self, category: str, max_pages: int) -> List[str]:
        max_pages = max(1, int(max_pages))
        cat = (category or "latest").strip().lower()
        pages: List[str] = []

        if cat == "latest":
            pages.append(self._build_page_url({"page": "New Releases"}))
            return pages

        if cat in {"2025", "2026"}:
            letters = self._ALPHABET[:max_pages]
            for letter in letters:
                pages.append(self._build_page_url({"page": "A-Z Movie Songs", "cpage": letter}))
            return pages

        if cat == "old":
            old_pages = [
                {"page": "Old Collections"},
                {"page": "Old Hits (Singers)"},
            ]
            for item in old_pages[:max_pages]:
                pages.append(self._build_page_url(item))
            return pages

        pages.append(self._build_page_url({"page": "A-Z Movie Songs", "cpage": "A"}))
        return pages

    def _build_page_url(self, query: Dict[str, str]) -> str:
        query_string = "&".join(
            f"{key}={requests.utils.quote(value, safe='()')}" for key, value in query.items()
        )
        return f"{self.base_url}/index.php?{query_string}"

    def _extract_albums_from_page(self, html: str, category: str) -> List[Album]:
        soup = BeautifulSoup(html, "html.parser")
        albums: List[Album] = []

        for anchor in soup.find_all("a", href=True):
            href = anchor.get("href", "").strip()
            if not href:
                continue
            if "spage=" not in href and "songs2/" not in href.lower():
                continue

            absolute_url = urljoin(self.base_url + "/", href)
            name = self._album_name_from_anchor(anchor.get_text(" ", strip=True), absolute_url)
            if not name:
                continue

            year = self._extract_year(name)
            if category in {"2025", "2026"} and year != int(category):
                continue

            if self._is_non_album_link(name=name):
                continue

            albums.append(
                Album(
                    name=name,
                    url=absolute_url,
                    year=year,
                    song_count=None,
                    source="friendstamilmp3",
                )
            )

        return albums

    @staticmethod
    def _extract_year(text: str) -> Optional[int]:
        match = re.search(r"\b(20\d{2})\b", text)
        if not match:
            return None
        return int(match.group(1))

    @staticmethod
    def _album_name_from_anchor(anchor_text: str, absolute_url: str) -> str:
        text = (anchor_text or "").strip()
        if text:
            return re.sub(r"\s+", " ", text)

        parsed = urlparse(absolute_url)
        query = parse_qs(parsed.query)
        spage = query.get("spage", [])
        if spage:
            return re.sub(r"\s+", " ", unquote(spage[0]).strip())

        path_tail = unquote(parsed.path.rstrip("/").split("/")[-1]).strip()
        return re.sub(r"\s+", " ", path_tail)

    @staticmethod
    def _song_name_from_anchor(anchor_text: str, url: str) -> str:
        text = (anchor_text or "").strip()
        if text:
            return re.sub(r"\s+", " ", text)

        filename = unquote(urlparse(url).path.split("/")[-1]).strip()
        if not filename:
            return "Unknown Song"
        name = re.sub(r"\.(mp3|zip|m4a|aac|wav|flac)$", "", filename, flags=re.IGNORECASE).strip()
        return re.sub(r"\s+", " ", name) or "Unknown Song"

    @staticmethod
    def _is_non_album_link(name: str) -> bool:
        n = name.strip().lower()
        if not n:
            return True
        ignore_names = {
            "home",
            "chat",
            "forum",
            "fm",
            "comments",
            "new releases",
            "a-z movie songs",
            "old collections",
            "old hits (singers)",
            "star hits",
            "music director hits",
            "singer hits",
        }
        return n in ignore_names
