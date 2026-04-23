"""MassTamilan scraper module.

This scraper tries multiple strategies to retrieve latest Tamil songs from
Masstamilan (including Cloudflare bypass via cloudscraper and browser rendering).
"""

import logging
import re
from typing import Callable, Optional, List
from urllib.parse import urljoin

import cloudscraper
from bs4 import BeautifulSoup
from playwright.sync_api import Page, sync_playwright

from models.song import Album, Song
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class MassTamilanScraper(BaseScraper):
    """Scraper for MassTamilan.dev (or masstamilan.in)."""

    def __init__(self, base_url: str = "https://www.masstamilan.dev") -> None:
        super().__init__(base_url)
        self._session = cloudscraper.create_scraper()
        self._pw: Optional[object] = None
        self._browser: Optional[object] = None

    def _init_browser(self) -> None:
        if self._browser:
            return
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=True)

    def _close_browser(self) -> None:
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()
        self._browser = None
        self._pw = None

    def __enter__(self) -> "MassTamilanScraper":
        self._init_browser()
        return self

    def __exit__(self, *_: object) -> None:
        self._close_browser()

    def _is_cloudflare_challenge(self, html: str) -> bool:
        tokens = ["Just a moment", "Checking your browser before accessing", "cf-browser-verification"]
        return any(token in html for token in tokens)

    def test_connection(self) -> bool:
        try:
            r = self._session.get(self.base_url, timeout=20)
            if r.status_code == 200 and r.text and self._is_cloudflare_challenge(r.text):
                logger.warning("Masstamilan: Cloudflare challenge detected on connection test")
                return False
            return r.status_code == 200
        except Exception:
            return False

    def _fetch_page(self, url: str) -> Optional[str]:
        try:
            r = self._session.get(url, timeout=25)
            if r.status_code == 200 and r.text:
                if self._is_cloudflare_challenge(r.text):
                    logger.warning("Masstamilan: Cloudflare challenge page received for %s", url)
                    return None
                return r.text
        except Exception:
            pass
        return None

    def _render_page(self, url: str) -> Optional[str]:
        # Playwright sync may fail when called inside existing async event loops
        # (e.g. some IDE / plugin environments). If it fails, fallback gracefully.
        try:
            self._init_browser()
            page: Page = self._browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(5000)
            html = page.content()
            page.close()
            if html and self._is_cloudflare_challenge(html):
                logger.warning("Masstamilan: Cloudflare challenge page rendered for %s", url)
                return None
            return html
        except Exception as e:
            logger.warning("Masstamilan _render_page failed, skipping Playwright: %s", e)
            return None

    def get_albums(
        self,
        category: str = "latest",
        max_pages: int = 3,
        progress_cb: Optional[Callable[[int, int], None]] = None,
    ) -> List[Album]:
        albums: List[Album] = []
        seen: set[str] = set()
        year_filter: Optional[int] = None
        if category.isdigit() and len(category) == 4:
            year_filter = int(category)

        logger.debug("MassTamilan.get_albums: category=%s year_filter=%s pages=%d",
                     category, year_filter, max_pages)

        # Category is not strictly required: masstamilan uses /tamil-songs?page=N
        for page_num in range(1, max_pages + 1):
            if progress_cb is not None:
                progress_cb(page_num, max_pages)
            page_url = f"{self.base_url}/tamil-songs" + (f"?page={page_num}" if page_num > 1 else "")
            html = self._fetch_page(page_url) or self._render_page(page_url)
            if not html:
                logger.debug("MassTamilan: no HTML for page %d", page_num)
                continue

            page_albums = self._parse_album_page(html)
            passed = 0
            skipped = 0
            for album in page_albums:
                # Strict year filter: album must have a confirmed matching year.
                # Albums with no detectable year are excluded from year-specific queries.
                if year_filter is not None and album.year != year_filter:
                    logger.debug("  MassTamilan skip: %r  url=%s  year=%s",
                                 album.name[:50], album.url[-60:], album.year)
                    skipped += 1
                    continue
                if album.url not in seen:
                    seen.add(album.url)
                    albums.append(album)
                    passed += 1
            logger.debug("MassTamilan page %d: raw=%d passed=%d skipped=%d",
                         page_num, len(page_albums), passed, skipped)

        return albums

    def _parse_album_page(self, html: str) -> List[Album]:
        soup = BeautifulSoup(html, "html.parser")
        albums: List[Album] = []
        seen: set[str] = set()

        # Use href-pattern matching (CSS class selectors don't match masstamilan.dev).
        # Album pages consistently end in «-songs» or «-songs/» in their slug.
        for link in soup.find_all("a", href=re.compile(r"-songs", re.I)):
            href = (link.get("href") or "").strip()
            raw_text = link.get_text(" ", strip=True)
            # Strip "Starring: ..." and "Music: ..." boilerplate appended in card text
            text = re.split(r"\s+Starring\s*:", raw_text, maxsplit=1)[0].strip()
            text = re.split(r"\s+Music\s*:", text, maxsplit=1)[0].strip()
            if not href or not text:
                continue
            if self._is_nav_entry(text, href):
                continue
            if href.startswith("/"):
                href = urljoin(self.base_url, href)
            if href in seen:
                continue
            seen.add(href)
            # Year: from anchor text first, then from the URL slug
            # (e.g. /karuppu-2026-songs/ → 2026 even if title says "Karuppu")
            year = self._extract_year_from_title(text) or self._extract_year_from_title(href)
            albums.append(Album(name=text, url=href, year=year, song_count=None, source="masstamilan"))

        logger.debug("MassTamilan _parse_album_page: found %d albums", len(albums))
        return albums

    @staticmethod
    def _is_nav_entry(text: str, href: str) -> bool:
        """Return True for navigation/category links that are not movie albums."""
        n = text.strip().lower()
        u = href.lower()
        # Bare 4-digit year
        if re.fullmatch(r"\d{4}", n):
            return True
        # Single letter or 0-9 range (A-Z navigation)
        if re.fullmatch(r"[a-z]", n) or n in ("0-9", "a-z", "#"):
            return True
        # Generic nav/UI text
        nav_words = {
            "home", "search", "contact", "about", "login", "register",
            "privacy policy", "disclaimer", "sitemap", "copyright",
            "latest songs", "new songs", "all songs", "tamil songs",
            "new releases", "top songs", "popular", "trending",
        }
        if n in nav_words:
            return True
        # Generic category names
        if re.search(r"^tamil \d{4}", n) or re.search(r"^\d{4} tamil", n):
            return True
        # Category URL patterns
        if any(x in u for x in ("/category/", "/tag/", "/genre/",
                                  "/page/", "?page=", "?cat=")):
            return True
        return False

    @staticmethod
    def _extract_year_from_title(title: str) -> Optional[int]:
        m = re.search(r"(20\d{2})", title)
        if m:
            return int(m.group(1))
        return None

    def get_songs(self, album: Album) -> List[Song]:
        html = self._fetch_page(album.url) or self._render_page(album.url)
        songs: List[Song] = []
        if not html:
            return songs

        soup = BeautifulSoup(html, "html.parser")
        for link in soup.select("a[href*='download'], a[href*='d320'], a[href*='d128'], a[href*='zip']"):
            href = link.get("href", "").strip()
            if not href:
                continue
            if href.startswith("/"):
                href = urljoin(self.base_url, href)
            name = (link.get("title") or link.text or album.name).strip()
            score = "320kbps" if "320" in href or "320" in name else "128kbps" if "128" in href or "128" in name else "unknown"
            songs.append(Song(name=name, url=href, size_mb=None, quality=score, album_name=album.name))

        # if none, check for explicit mp3 lines
        if not songs:
            for link in soup.select("a[href*='mp3']"):
                href = link.get("href", "").strip()
                if not href:
                    continue
                if href.startswith("/"):
                    href = urljoin(self.base_url, href)
                songs.append(Song(name=(link.text or album.name).strip() or "Unknown", url=href, size_mb=None, quality="unknown", album_name=album.name))

        return songs
