"""FriendsTamilMP3 scraper implementation.

This scraper targets the query-parameter based pages used by friendstamilmp3.in
and extracts:
- Album listings from `spage=` links on category pages
- Song links from album pages that expose direct audio URLs
"""

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Dict, List, Optional, Set
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

    def get_albums(
        self,
        category: str = "latest",
        max_pages: int = 3,
        progress_cb: Optional[Callable[[int, int], None]] = None,
    ) -> List[Album]:
        """Get albums for a category.

        Categories supported:
        - latest: New releases page
        - 2026 / 2025: A-Z pages filtered by year from title
        - old: old collections pages
        """
        pages = self._category_pages(category=category, max_pages=max_pages)
        albums: List[Album] = []
        seen_urls: Set[str] = set()

        cat = (category or "").strip()
        # Use parallel fetching when many pages exist (year A-Z scan, Ilaiyaraja A-Z)
        if len(pages) > 6:
            completed = 0
            if progress_cb is not None:
                progress_cb(0, len(pages))

            def _fetch_one(page_url: str) -> List[Album]:
                html = self._fetch_html(page_url)
                if not html:
                    return []
                return self._extract_albums_from_page(html=html, category=category)

            with ThreadPoolExecutor(max_workers=8) as pool:
                futures = {pool.submit(_fetch_one, url): url for url in pages}
                for future in as_completed(futures):
                    completed += 1
                    if progress_cb is not None:
                        progress_cb(completed, len(pages))
                    for album in future.result():
                        if album.url not in seen_urls:
                            seen_urls.add(album.url)
                            albums.append(album)
        else:
            for page_num, page_url in enumerate(pages, start=1):
                if progress_cb is not None:
                    progress_cb(page_num, len(pages))
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

        if cat.isdigit() and len(cat) == 4:
            # For year-specific queries we must scan all 26 A-Z pages because
            # albums are sorted alphabetically, not by year. Limiting to the
            # first N letters would miss every album starting from F onwards.
            for letter in self._ALPHABET:
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

        if cat == "stars":
            pages.append(self._build_page_url({"page": "Star Hits"}))
            return pages

        if cat == "singers":
            pages.append(self._build_page_url({"page": "Singer Hits"}))
            return pages

        if cat == "music-directors":
            pages.append(self._build_page_url({"page": "Music Director Hits"}))
            return pages

        if cat == "ilaiyaraja":
            for letter in self._ALPHABET:
                pages.append(self._build_page_url({"page": "ILaiyaraja Hits", "cpage": letter}))
            return pages

        if cat == "ar-rahman":
            pages.append(self._build_page_url({"page": "A R Rahman Hits"}))
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
        cat = (category or "").strip()
        year_filter = int(cat) if cat.isdigit() and len(cat) == 4 else None
        total_spage = 0
        skipped_year = 0
        skipped_nav = 0

        for anchor in soup.find_all("a", href=True):
            href = anchor.get("href", "").strip()
            if not href:
                continue
            if "spage=" not in href and "songs2/" not in href.lower():
                continue
            total_spage += 1

            absolute_url = urljoin(self.base_url + "/", href)
            name = self._album_name_from_anchor(anchor.get_text(" ", strip=True), absolute_url)
            if not name:
                continue

            # Extract year from album name first, then from the spage= URL
            # (spage often encodes year like "Leo+(2026)").
            year = self._extract_year(name) or self._extract_year(absolute_url)
            # Strict year filter: only include albums whose year is confirmed to match.
            if year_filter is not None and year != year_filter:
                logger.debug("FTP3 skip year: %r  url_year=%s  filter=%s",
                             name[:50], year, year_filter)
                skipped_year += 1
                continue

            if self._is_non_album_link(name=name):
                skipped_nav += 1
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

        logger.debug(
            "FTP3 _extract page: spage_links=%d  skipped_year=%d  skipped_nav=%d  passed=%d  cat=%s",
            total_spage, skipped_year, skipped_nav, len(albums), cat,
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
        # Bare 4-digit year labels (navigation sidebar)
        if re.fullmatch(r"\d{4}", n):
            return True
        # Single letter A-Z or "0-9" range (alphabet navigation)
        if re.fullmatch(r"[a-z]", n) or n in ("0-9", "a-z", "#"):
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
            "search",
            "contact",
            "about",
            "privacy policy",
            "disclaimer",
            "sitemap",
            "latest songs",
            "all songs",
            "tamil songs",
            "new songs",
            "top songs",
        }
        return n in ignore_names
