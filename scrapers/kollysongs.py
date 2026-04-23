"""KollySongs scraper — requests + BeautifulSoup.

Site structure (verified 2026-04-04):
    Album listing  : https://www.kollysongs.com/tamil-songs-{year}/?page=N
    Latest / 2026  : resolved to highest available yearly collection
                                 : (e.g. /tamil-songs-2025/) because home pagination repeats
  Album detail   : https://www.kollysongs.com/{movie-slug}-songs-download/
  Song download  : https://www.kollysongs.com/download/hash/{id}/1/
                   → HTTP-redirects to direct CDN MP3 (audio/mpeg)

HTML selectors (verified):
  Album card  : div.album-details  >  h2.album-title  >  a[href]
  Music dir   : div.album-details  >  p.album-musician
  Song row    : div.song-list  (one per song)
  Song name   : leading text of div.song-list,  strip "N " prefix & "Mp3 Song" suffix
  Song size   : inside div.song-details  text  "( N.NN MB"
  Download    : a.downloadbutton[href]
  Year (detail): a[href~=/tamil-songs-YYYY/]
  Pagination  : text  "Pages: X Of Y"  +  next-link href "?page=N"
"""

from __future__ import annotations

import logging
import re
from typing import Callable, List, Optional, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from models.song import Album, Song
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

_DEFAULT_BASE = "https://www.kollysongs.com"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


class KollySongsScraper(BaseScraper):
    """Scraper for KollySongs.com — no Playwright required."""

    def __init__(self, base_url: str = _DEFAULT_BASE) -> None:
        super().__init__(base_url)
        self._session = requests.Session()
        self._session.headers.update(_HEADERS)
        self._latest_year_cache: Optional[int] = None
        self._md_paths_cache: Optional[List[str]] = None

    # ── No-op browser stubs (called by gui.py in try/except) ──────────
    def _init_browser(self) -> None:  # noqa: D401
        pass

    def _close_browser(self) -> None:
        pass

    def __enter__(self) -> "KollySongsScraper":
        return self

    def __exit__(self, *_: object) -> None:
        pass

    # ── Connection test ────────────────────────────────────────────────

    def test_connection(self) -> bool:
        try:
            r = self._session.get(self.base_url, timeout=15)
            return r.status_code == 200
        except Exception:
            return False

    # ── Internal helpers ───────────────────────────────────────────────

    def _fetch(self, url: str) -> Optional[str]:
        try:
            r = self._session.get(url, timeout=25)
            if r.status_code == 200:
                return r.text
        except Exception as exc:
            logger.debug("KollySongs fetch error [%s]: %s", url, exc)
        return None

    def _discover_latest_year(self) -> Optional[int]:
        """Find highest year available in KollySongs yearly collections."""
        if self._latest_year_cache is not None:
            return self._latest_year_cache

        html = self._fetch(f"{self.base_url}/yearly-tamil-songs/")
        if not html:
            return None

        years = sorted({int(y) for y in re.findall(r"/tamil-songs-(\d{4})/?", html)}, reverse=True)
        for y in years:
            probe_html = self._fetch(f"{self.base_url}/tamil-songs-{y}/")
            if probe_html and "album-details" in probe_html:
                self._latest_year_cache = y
                break
        else:
            self._latest_year_cache = None
        return self._latest_year_cache

    def _discover_md_paths(self) -> List[str]:
        """Discover music-director collection URLs from KollySongs."""
        if self._md_paths_cache is not None:
            return self._md_paths_cache

        html = self._fetch(f"{self.base_url}/tamil-music-directors-discography/")
        if not html:
            self._md_paths_cache = []
            return self._md_paths_cache

        paths = re.findall(r'href=["\'](/music/[^"\']+-songs/?)["\']', html, flags=re.I)
        # Preserve order, remove duplicates
        dedup: List[str] = []
        seen: set[str] = set()
        for p in paths:
            if p not in seen:
                seen.add(p)
                dedup.append(p)
        self._md_paths_cache = dedup
        return self._md_paths_cache

    def _extract_album_cards(
        self,
        soup: BeautifulSoup,
        seen: set[str],
        year_hint: Optional[int],
    ) -> Tuple[List[Album], int]:
        """Parse album cards from a listing page, returning (new_albums, added_count)."""
        out: List[Album] = []
        cards = soup.find_all("div", class_="album-details")
        added = 0
        for card in cards:
            link = card.find("a", href=re.compile(r"-songs-download/?", re.I))
            if not link:
                continue
            href = link.get("href", "")
            album_url = urljoin(self.base_url, href)
            if album_url in seen:
                continue
            seen.add(album_url)

            raw_name = link.get_text(strip=True)
            name = self._clean_album_name(raw_name)
            if not name:
                continue

            out.append(
                Album(
                    name=name,
                    url=album_url,
                    year=year_hint,
                    source="kollysongs",
                )
            )
            added += 1
        return out, added

    def _page_url(self, category: str, page: int) -> tuple[Optional[str], Optional[int]]:
        """Build listing URL and inferred album year for the given category/page."""
        base: Optional[str] = None
        year_hint: Optional[int] = None

        if category == "latest":
            latest_year = self._discover_latest_year()
            if latest_year:
                base = f"{self.base_url}/tamil-songs-{latest_year}/"
                year_hint = latest_year
            else:
                base = self.base_url + "/"
        elif category == "2026":
            # KollySongs currently has no /tamil-songs-2026/ page.
            # Use latest available year page for broader coverage.
            latest_year = self._discover_latest_year()
            if latest_year:
                base = f"{self.base_url}/tamil-songs-{latest_year}/"
                # Do not force a wrong year label in the UI.
                year_hint = None
            else:
                base = self.base_url + "/"
        elif category.isdigit() and len(category) == 4:
            base = f"{self.base_url}/tamil-songs-{category}/"
            year_hint = int(category)
        else:
            return None, None

        return (base if page == 1 else f"{base}?page={page}"), year_hint

    def _parse_year_from_url(self, url: str) -> Optional[int]:
        m = re.search(r"/tamil-songs-(\d{4})/?", url)
        return int(m.group(1)) if m else None

    @staticmethod
    def _clean_album_name(raw: str) -> str:
        name = re.sub(r"\s+Tamil Songs$", "", raw, flags=re.I)
        name = re.sub(r"\s+Songs$", "", name, flags=re.I)
        return name.strip()

    @staticmethod
    def _clean_song_name(raw: str) -> str:
        # Strip leading track number: "1 ", "12 ", "3. "
        name = re.sub(r"^\d+[\s.]+", "", raw).strip()
        # Strip trailing quality/format markers (strip first so $ anchors correctly)
        name = re.sub(r"\s+Mp3 Songs?$", "", name, flags=re.I).strip()
        name = re.sub(r"\s+320kbps$", "", name, flags=re.I).strip()
        return name

    # ── Album listing ──────────────────────────────────────────────────

    def get_albums(
        self,
        category: str = "latest",
        max_pages: int = 3,
        progress_cb: Optional[Callable[[int, int], None]] = None,
    ) -> List[Album]:
        albums: List[Album] = []
        seen: set[str] = set()

        if category == "music-directors":
            md_paths = self._discover_md_paths()
            total = min(max_pages, len(md_paths))
            for i, md_path in enumerate(md_paths[:total], start=1):
                if progress_cb is not None:
                    progress_cb(i, max(total, 1))
                url = urljoin(self.base_url, md_path)
                html = self._fetch(url)
                if not html:
                    continue
                soup = BeautifulSoup(html, "html.parser")
                new_albums, added = self._extract_album_cards(soup, seen, None)
                albums.extend(new_albums)
                logger.debug(
                    "KollySongs MD page %d: +%d albums (total %d, url=%s)",
                    i, added, len(albums), url,
                )
            return albums

        for page_num in range(1, max_pages + 1):
            if progress_cb is not None:
                progress_cb(page_num, max_pages)

            url, year_hint = self._page_url(category, page_num)
            if url is None:
                logger.debug("KollySongs: unsupported category '%s'", category)
                break

            html = self._fetch(url)
            if not html:
                logger.debug("KollySongs: no HTML for page %d (%s)", page_num, url)
                break

            soup = BeautifulSoup(html, "html.parser")
            new_albums, added = self._extract_album_cards(soup, seen, year_hint)
            albums.extend(new_albums)

            logger.debug(
                "KollySongs page %d: +%d albums (total %d, url=%s)",
                page_num, added, len(albums), url,
            )

            if added == 0:
                break  # no new content on this page — stop early

        return albums

    # ── Song listing ───────────────────────────────────────────────────

    def get_songs(self, album: Album) -> List[Song]:
        html = self._fetch(album.url)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        songs: List[Song] = []
        seen: set[str] = set()

        # Determine year (album may not have it if loaded from "latest")
        alb_year: Optional[int] = album.year
        if not alb_year:
            yr_link = soup.find(
                "a", href=re.compile(r"/tamil-songs-\d{4}/?$", re.I)
            )
            if yr_link:
                alb_year = self._parse_year_from_url(yr_link.get("href", ""))

        # Each song is inside a div.song-list
        for song_div in soup.find_all("div", class_="song-list"):
            dl_link = song_div.find(
                "a", class_="downloadbutton",
                href=re.compile(r"/download/hash/", re.I),
            )
            if not dl_link:
                # Fallback: any href with /download/hash/
                dl_link = song_div.find(
                    "a", href=re.compile(r"/download/hash/", re.I)
                )
            if not dl_link:
                continue

            dl_url = urljoin(self.base_url, dl_link.get("href", ""))
            if dl_url in seen:
                continue
            seen.add(dl_url)

            # ── Song name ──────────────────────────────────────────────
            # Leading NavigableString of song-list: "1 Song Name Mp3 Song"
            raw_name = ""
            for child in song_div.children:
                if hasattr(child, "get_text"):
                    break  # reached a child tag — stop
                text = str(child).strip()
                if text:
                    raw_name = text
                    break
            # If no direct text, grab text up to first child
            if not raw_name:
                full = song_div.get_text(" ", strip=True)
                raw_name = re.split(r"Singer|Duration|Download|Play", full)[0]

            name = self._clean_song_name(raw_name)
            if not name:
                name = album.display_name

            # ── Size ───────────────────────────────────────────────────
            size_mb: Optional[float] = None
            details_div = song_div.find("div", class_="song-details")
            if details_div:
                m = re.search(r"\(\s*(\d+\.?\d*)\s*MB", details_div.get_text())
                if m:
                    try:
                        size_mb = float(m.group(1))
                    except ValueError:
                        pass

            songs.append(
                Song(
                    name=name,
                    url=dl_url,
                    size_mb=size_mb,
                    quality="320kbps",
                    album_name=album.safe_dirname,
                    year=alb_year,
                )
            )

        logger.debug(
            "KollySongs get_songs: %d songs from '%s'", len(songs), album.display_name
        )
        return songs
