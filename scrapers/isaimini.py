"""
IsaiminiHQ scraper using Playwright.

Improvements over v1:
- Multi-page album discovery (get 2025-2026 content from multiple pages)
- Quality detection per song (320 vs 128 kbps)
- Size extraction from page text
- 320kbps links are prioritised; 128kbps kept as fallback
- ZIP archive listed first so users can grab everything in one shot
- Deduplication of albums and songs
"""

import re
import time
from typing import List, Optional
from urllib.parse import urljoin

from playwright.sync_api import Page, sync_playwright

from models.song import Album, Song
from scrapers.base import BaseScraper


# ---------------------------------------------------------------------------
# JS helpers (injected into the browser)
# ---------------------------------------------------------------------------

_JS_GET_ALBUMS = """
() => {
    const seen = new Set();
    const items = [];

    // Most Tamil music sites use an article/li/div grid for albums
    const candidates = document.querySelectorAll(
        '.album-item, .movie-item, .post-item, article, ' +
        '.entry-title a, .album-title a, ' +
        'a[href*="-songs"], a[href*="-mp3"], a[href*="songs/"]'
    );

    candidates.forEach(el => {
        const link = el.tagName === 'A' ? el : el.querySelector('a');
        if (!link) return;

        const url = link.href || '';
        const href = link.getAttribute('href') || '';

        if (!url || seen.has(url)) return;
        if (href.startsWith('#') || href.startsWith('javascript:')) return;
        // must look like an album/song-list page
        if (!(href.includes('songs') || href.includes('mp3') || href.includes('album'))) return;
        // skip category/tag pages
        if (href.includes('/tag/') || href.includes('/category/') || href.includes('page/')) return;

        const name = (link.textContent || '').trim();
        if (!name || name.length < 2) return;

        seen.add(url);
        items.push({ name, url });
    });

    return items;
}
"""

_JS_GET_SONGS = r"""
() => {
    const seen = new Set();
    const items = [];

    // Detect page-wide quality from ZIP URL (if present) as fallback for MP3s
    let pageQuality = 'unknown';
    document.querySelectorAll('a[href]').forEach(a => {
        const u = (a.href || '').toLowerCase();
        if (u.includes('.zip') || u.includes('download.isai')) {
            if (u.includes('320')) pageQuality = '320kbps';
            else if (u.includes('128')) pageQuality = '128kbps';
        }
    });

    document.querySelectorAll('a[href]').forEach(link => {
        const url  = link.href  || '';
        const href = link.getAttribute('href') || '';

        if (!url || seen.has(url)) return;
        if (href.includes('#') || href.includes('javascript:')) return;

        const lhref = url.toLowerCase();
        const isFile = lhref.includes('.mp3') || lhref.includes('.zip') ||
                       lhref.includes('/download/') || lhref.includes('download.isai');
        if (!isFile) return;
        seen.add(url);

        const container = link.closest('tr, li, .song-row, .track-row, .button-container, .downloadinfo') ||
                          link.parentElement;

        // ---- Name extraction (priority order) ----
        let name = '';

        // 1. link's own title attr: "Download Vroom Vroom Song" → strip prefix/suffix
        const linkTitle = (link.getAttribute('title') || '').trim();
        if (linkTitle) {
            name = linkTitle.replace(/^download\s+/i, '').replace(/\s+songs?$/i, '').trim();
        }

        // 2. sibling button's data-title: <button data-title="Vroom Vroom">
        if (!name && container) {
            const btn = container.querySelector('button[data-title]');
            if (btn) name = (btn.getAttribute('data-title') || '').trim();
        }

        // 3. sibling button's aria-label: "Play Vroom Vroom song" → strip
        if (!name && container) {
            const btn = container.querySelector('button[aria-label]');
            if (btn) {
                name = (btn.getAttribute('aria-label') || '')
                    .replace(/^play\s+/i, '').replace(/\s+songs?$/i, '').trim();
            }
        }

        // 4. Text-node walker fallback
        if (!name && container) {
            const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null);
            const frags = [];
            while (walker.nextNode()) {
                if (!link.contains(walker.currentNode)) {
                    const t = (walker.currentNode.textContent || '').trim();
                    if (t.length >= 3) frags.push(t);
                }
            }
            const genericBtn = /^(download|play|stream|share|free|get|click|listen|zip|mp3)$/i;
            const good = frags.filter(t => {
                if (/^\d+$/.test(t))                           return false;
                if (genericBtn.test(t))                         return false;
                if (/^\d+\.?\d*\s*(kbps|mb|kb|gb)?$/i.test(t)) return false;
                if (/^\d+:\d+$/.test(t))                       return false;
                if (/^[|,.\-\/]+$/.test(t))                    return false;
                return true;
            });
            if (good.length) name = good[0];
        }

        // 5. Absolute fallback
        if (!name) name = (link.textContent || '').trim() || 'Unknown';

        // ---- Quality detection ----
        const ctxText = container ? (container.textContent || '').replace(/\s+/g, ' ') : '';
        const combined = (name + ' ' + ctxText + ' ' + url).replace(/\s+/g, ' ');
        let quality = 'unknown';
        if (/320/i.test(combined))      quality = '320kbps';
        else if (/128/i.test(combined)) quality = '128kbps';
        else if (lhref.includes('.mp3') || lhref.includes('/download/')) quality = pageQuality;

        // ---- Size extraction ----
        const szMatch = ctxText.match(/(\d+\.?\d*)\s*MB/i);
        const size_text = szMatch ? szMatch[1] : '';

        items.push({ name, url, quality, size_text });
    });

    return items;
}
"""


class IsaiminiScraper(BaseScraper):
    """Playwright-based scraper for IsaiminiHQ."""

    def __init__(self, base_url: str = "https://www.isaiminihq.com"):
        super().__init__(base_url)
        self._pw = None
        self._browser = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _init_browser(self):
        if self._browser:
            return
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=True)

    def _close_browser(self):
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()
        self._browser = None
        self._pw = None

    def __enter__(self):
        self._init_browser()
        return self

    def __exit__(self, *_):
        self._close_browser()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def test_connection(self) -> bool:
        self._init_browser()
        page = self._browser.new_page()
        try:
            page.goto(self.base_url, timeout=15000)
            return bool(page.title())
        except Exception:
            return False
        finally:
            page.close()

    def get_albums(self, category: str = "latest", max_pages: int = 3) -> List[Album]:
        """
        Return albums scraped from up to *max_pages* pages.

        Pages are fetched newest-first so page-1 always has the latest
        2025-2026 releases.
        """
        self._init_browser()
        all_albums: List[Album] = []
        seen_urls: set = set()

        for page_num in range(1, max_pages + 1):
            page_url = self._category_url(category, page_num)
            page_albums = self._get_albums_from_page(page_url)
            if not page_albums:
                break  # no more content
            for a in page_albums:
                if a.url not in seen_urls:
                    seen_urls.add(a.url)
                    all_albums.append(a)

        return all_albums

    def get_songs(self, album: Album) -> List[Song]:
        """
        Return songs for *album*, with ZIPs listed first and 320 kbps
        prioritised over 128 kbps when both are present for a track.
        """
        self._init_browser()
        page = self._browser.new_page()
        raw: List[Song] = []

        try:
            page.goto(album.url, wait_until="networkidle", timeout=30000)
            self._wait_for_content(page)
            raw = self._parse_songs(page, album.display_name)
        except Exception as e:
            pass  # caller handles empty list
        finally:
            page.close()

        return self._prioritise(raw)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _category_url(self, category: str, page_num: int) -> str:
        # Homepage is newest-first on WordPress Tamil music sites
        # Year-specific pages filter by year explicitly
        if category == "latest":
            if page_num == 1:
                return self.base_url + "/"
            return self.base_url + f"/page/{page_num}/"

        # Year-specific & other categories
        paths = {
            "2026": "/2026-tamil-mp3-songs/",
            "2025": "/2025-tamil-mp3-songs/",
            "old":  "/tamil-songs-1980/",
        }
        base_path = paths.get(category, "/tamil-mp3-songs/")
        if page_num == 1:
            return urljoin(self.base_url, base_path)
        return urljoin(self.base_url, f"{base_path}page/{page_num}/")

    def _get_albums_from_page(self, url: str) -> List[Album]:
        page = self._browser.new_page()
        albums: List[Album] = []
        try:
            resp = page.goto(url, wait_until="networkidle", timeout=30000)
            if resp and resp.status == 404:
                return []

            # Try the targeted selector first, fall back to generic JS
            try:
                page.wait_for_selector(
                    ".album-item, .movie-item, a[href*='-songs'], article",
                    timeout=8000
                )
            except Exception:
                pass

            data = page.evaluate(_JS_GET_ALBUMS)

            # Also try to extract post dates from the page for year info
            date_map: dict = {}
            try:
                date_data = page.evaluate(r"""
                    () => {
                        const result = {};
                        document.querySelectorAll('article').forEach(article => {
                            const link = article.querySelector('a[href]');
                            const time  = article.querySelector('time[datetime]');
                            if (link && time) {
                                const dt = time.getAttribute('datetime') || '';
                                const yr = dt.match(/^(\d{4})/);
                                if (yr) result[link.href] = parseInt(yr[1], 10);
                            }
                        });
                        return result;
                    }
                """)
                date_map = date_data or {}
            except Exception:
                pass

            for item in data:
                name = item.get("name", "").strip()
                item_url = item.get("url", "").strip()
                if not name or not item_url:
                    continue
                # Skip generic category/year listing pages
                if self._is_category_page(name, item_url):
                    continue
                # Year: from post date map → from name/URL text
                year = date_map.get(item_url) or self._extract_year(name + " " + item_url)
                albums.append(Album(name=name, url=item_url, year=year, source="isaimini"))

        except Exception:
            pass
        finally:
            page.close()

        return albums

    def _wait_for_content(self, page: Page):
        selectors = [
            "a[href*='.mp3']",
            "a[href*='.zip']",
            "a[href*='download']",
            ".download-link",
            ".song-item",
        ]
        for sel in selectors:
            try:
                page.wait_for_selector(sel, timeout=8000)
                time.sleep(1)   # let lazy-loads settle
                return
            except Exception:
                continue
        time.sleep(3)   # fallback wait

    def _parse_songs(self, page: Page, album_name: str) -> List[Song]:
        data = page.evaluate(_JS_GET_SONGS)
        songs: List[Song] = []

        for item in data:
            raw_name  = (item.get("name")    or "").strip()
            url       = (item.get("url")     or "").strip()
            quality   = (item.get("quality") or "unknown")
            size_text = (item.get("size_text") or "")

            if not url:
                continue

            name, size_mb = self._clean_name_size(raw_name, url, size_text)

            # If quality still unknown, default to 320kbps for ZIP, else unknown
            if quality == "unknown":
                quality = "320kbps" if ".zip" in url.lower() else "unknown"

            songs.append(Song(
                name=name,
                url=url,
                quality=quality,
                size_mb=size_mb,
                album_name=album_name,
            ))

        return songs

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_category_page(name: str, url: str) -> bool:
        """Return True for year/category listing pages (not actual movie albums)."""
        n = name.lower()
        u = url.lower()
        # Generic year/category name patterns
        generic = [
            r"^tamil \d{4} songs?$",
            r"^tamil songs? \d{4}$",
            r"^tamil yearly songs?",
            r"^tamil devotional",
            r"^old tamil songs?$",
            r"^new tamil songs?$",
            r"^tamil mp3 songs?$",
            r"^tamil \w+ songs?$",   # "Tamil Melody Songs" etc.
        ]
        for pattern in generic:
            if re.search(pattern, n):
                return True
        # Category-like URL patterns
        if re.search(r"/\d{4}-tamil", u):
            return True
        if any(x in u for x in ("/category/", "/tag/", "/genre/", "/type/")):
            return True
        return False

    @staticmethod
    def _extract_year(text: str) -> Optional[int]:
        # Accept 2020–2030 range so we catch recent years reliably
        m = re.search(r"\b(202[0-9]|2030)\b", text)
        return int(m.group(1)) if m else None

    @staticmethod
    def _clean_name_size(
        raw_name: str, url: str, size_text: str
    ):
        """Return (clean_name, size_mb)."""
        is_zip = ".zip" in url.lower()

        # Parse size
        size_mb: Optional[float] = None
        if size_text:
            try:
                size_mb = float(size_text)
            except ValueError:
                pass
        if size_mb is None:
            m = re.search(r"([\d.]+)\s*MB", raw_name, re.IGNORECASE)
            if m:
                try:
                    size_mb = float(m.group(1))
                except ValueError:
                    pass

        if is_zip:
            return "All Songs (ZIP)", size_mb

        # Pull the first non-empty line as the song title
        lines = [l.strip() for l in raw_name.splitlines() if l.strip()]
        name = lines[0] if lines else raw_name
        # Strip trailing quality/size noise: "Song Name  320 Kbps | 4.2 MB"
        name = re.split(r"\s+\d{3}\s*[Kk]bps", name)[0].strip()
        name = re.split(r"\s+\d+\.\d+\s*MB", name, flags=re.IGNORECASE)[0].strip()
        return name or "Unknown Song", size_mb

    @staticmethod
    def _prioritise(songs: List[Song]) -> List[Song]:
        """
        Sort order:
          1. ZIP files (one-click full album download)
          2. 320 kbps MP3s
          3. Everything else
        """
        def key(s: Song):
            if s.is_zip:
                return 0
            if "320" in s.quality:
                return 1
            return 2

        return sorted(songs, key=key)
