"""MassTamilan scraper module.

This scraper tries multiple strategies to retrieve latest Tamil songs from
Masstamilan (including Cloudflare bypass via cloudscraper and browser rendering).
"""

import logging
import re
from typing import Optional, List
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

    def get_albums(self, category: str = "latest", max_pages: int = 3) -> List[Album]:
        albums: List[Album] = []
        seen: set[str] = set()

        # Category is not strictly required: masstamilan uses /tamil-songs?page=N
        for page_num in range(1, max_pages + 1):
            page_url = f"{self.base_url}/tamil-songs" + (f"?page={page_num}" if page_num > 1 else "")
            html = self._fetch_page(page_url) or self._render_page(page_url)
            if not html:
                continue

            page_albums = self._parse_album_page(html)
            for album in page_albums:
                if album.url not in seen:
                    seen.add(album.url)
                    albums.append(album)

        return albums

    def _parse_album_page(self, html: str) -> List[Album]:
        soup = BeautifulSoup(html, "html.parser")
        albums: List[Album] = []

        # Try common card selector
        for link in soup.select("div.listing-page .list_item a, .list_item a, .album a"):  # fallback selectors
            href = link.get("href") or ""
            text = (link.text or "").strip()
            if not href or not text:
                continue
            if href.startswith("/"):
                href = urljoin(self.base_url, href)
            if "/movie" in href or "/song" in href or href.endswith("-songs/"):
                year = self._extract_year_from_title(text)
                albums.append(Album(name=text, url=href, year=year, song_count=None, source="masstamilan"))

        # Last fallback: pick all page links to song pages (not robust)
        if not albums:
            for link in soup.select("a[href]"):
                href = link.get("href", "")
                if href.startswith("/download/") or "/song/" in href:
                    href = urljoin(self.base_url, href)
                    text = (link.text or "Download").strip() or "Unknown"
                    year = self._extract_year_from_title(text)
                    albums.append(Album(name=text, url=href, year=year, song_count=None, source="masstamilan"))

        return albums

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
