#!/usr/bin/env python3
"""
Tamil MP3 Downloader — Textual TUI  (Stage 1)

Layout
------
┌─────────────────────────────────────────────────────────────────┐
│  Header                                                         │
├──────────────────────────────────────────────────────────────── │
│  🔍 Search: [_______________________]                           │
├──────────────┬───────────────────────┬──────────────────────── ┤
│  SOURCES     │  ALBUMS               │  SONGS                  │
│  Isaimini    │  Leo (2023)           │  [✓] Aalporaan 320kbps  │
│  MassTamil.. │  Jailer (2024)        │  [✓] Varisu.zip         │
│  Friends     │  …                    │  [ ] …                  │
├──────────────┴───────────────────────┴─────────────────────────┤
│  ⬇ Download progress / log                                      │
└─────────────────────────────────────────────────────────────────┘

Run:  python tui.py
"""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from time import perf_counter
from typing import Dict, List, Optional, Set, Tuple

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.events import Key
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    LoadingIndicator,
    ProgressBar,
    RichLog,
    Static,
)
from rich.text import Text

from config.settings import settings
from downloaders.http_downloader import HTTPDownloader
from models.song import Album, Song
from scrapers.base import BaseScraper
from scrapers.friendstamilmp3 import FriendsTamilMP3Scraper
from scrapers.isaimini import IsaiminiScraper
from scrapers.masstamilan import MassTamilanScraper

# Import library system (may raise RuntimeError if disabled)
try:
    from library import initialize_library
    _library_available = True
except ImportError:
    _library_available = False

logger = logging.getLogger(__name__)


# ─── Data model ──────────────────────────────────────────────────────────────


@dataclass
class SourceEntry:
    """A selectable row in the Sources panel."""

    label: str           # displayed text
    source_name: str     # "IsaiminiHQ" | "MassTamilan" | "FriendsTamilMP3" | "All Sources"


class TextualLogHandler(logging.Handler):
    """Route stdlib logging records into the TUI RichLog in real time."""

    def __init__(self, app: "TamilMP3TUI") -> None:
        super().__init__()
        self._app = app

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self._app.call_from_thread(self._app._log, f"[dim]{msg}[/dim]")
        except Exception:
            # Logging must never crash the app.
            return


# ─── Fuzzy scoring (same algorithm as main.py) ───────────────────────────────


def _fuzzy_score(keyword: str, candidate: str) -> float:
    kw, text = keyword.strip().lower(), candidate.strip().lower()
    if not kw or not text:
        return 0.0
    if len(kw) <= 2:
        return 1.0 if kw in text else 0.0
    bonus = 0.25 if kw in text else 0.0
    full  = SequenceMatcher(None, kw, text).ratio()
    token = max(
        (SequenceMatcher(None, kw, t).ratio() for t in text.split()), default=0.0
    )
    return min(1.0, max(full, token) + bonus)


# ─── App ─────────────────────────────────────────────────────────────────────


class TamilMP3TUI(App[None]):
    """Tamil MP3 Downloader — Textual TUI."""

    TITLE = "🎵 Tamil MP3 Downloader"
    SUB_TITLE = "TUI · v3.0"

    # ------------------------------------------------------------------
    # CSS
    # ------------------------------------------------------------------

    CSS = """
    /* ── App shell ─────────────────────────────────── */
    TamilMP3TUI {
        layout: vertical;
    }

    /* ── Search bar ─────────────────────────────────── */
    #search-bar {
        height: 3;
        layout: horizontal;
        align: left middle;
        padding: 0 1;
        background: $panel;
        border-bottom: solid $primary-darken-3;
    }
    #search-label {
        width: auto;
        padding: 0 1;
        color: $accent;
        text-style: bold;
    }
    #search-input {
        width: 38;
        margin: 0 1 0 0;
    }
    #search-hint {
        width: 1fr;
        color: $text-muted;
    }

    /* ── Category filter bar ────────────────────────── */
    #category-bar {
        height: 3;
        layout: horizontal;
        align: left middle;
        padding: 0 1;
        background: $panel;
        border-bottom: solid $primary-darken-3;
    }
    #cat-label {
        width: auto;
        padding: 0 1;
        content-align: center middle;
        color: $text-muted;
    }
    .cat-btn {
        min-width: 10;
        margin: 0 1 0 0;
    }
    .cat-btn.active-cat {
        background: $accent;
        color: $background;
        text-style: bold;
    }

    /* ── Main 3-panel row ───────────────────────────── */
    #main-area {
        height: 1fr;
        layout: horizontal;
    }

    /* common panel styles */
    .panel {
        layout: vertical;
        height: 100%;
        border: solid $primary-darken-3;
    }
    #sources-panel { width: 28; }
    #albums-panel  { width: 1fr; }
    #songs-panel   { width: 1fr; }

    .panel-title {
        height: 1;
        background: $primary-darken-2;
        color: $text;
        text-align: center;
        text-style: bold;
        padding: 0 1;
        width: 100%;
    }
    .panel-list {
        height: 1fr;
        overflow-y: auto;
    }

    /* ── Download / log area ────────────────────────── */
    #download-area {
        height: 10;
        layout: vertical;
        border-top: solid $primary-darken-3;
        background: $surface-darken-1;
    }
    #dl-top-row {
        height: 2;
        layout: horizontal;
        align: left middle;
        padding: 0 1;
    }
    #dl-status {
        width: 1fr;
        height: 1;
        color: $text-muted;
    }
    #dl-progress {
        width: 32;
        height: 1;
    }
    #download-log {
        height: 1fr;
        padding: 0 1;
    }

    /* ── Status bar ─────────────────────────────────── */
    #status-bar {
        height: 1;
        padding: 0 1;
        background: $panel;
        color: $text-muted;
        dock: bottom;
    }

    /* ── Loading indicator ──────────────────────────── */
    LoadingIndicator {
        height: 3;
    }
    #songs-status {
        height: 1;
        padding: 0 1;
        color: $accent;
        text-style: italic;
    }
    """

    # ------------------------------------------------------------------
    # Key bindings
    # ------------------------------------------------------------------

    BINDINGS = [
        Binding("d",      "download",      "Download",    show=True),
        Binding("a",      "select_all",    "Select All",  show=True),
        Binding("n",      "deselect_all",  "None",        show=True),
        Binding("l",      "load_more",     "Load More",   show=True),
        Binding("slash",  "focus_search",  "Search /",    show=True),
        Binding("escape", "escape",        "Back",        show=False),
        Binding("r",      "reload",        "Reload",      show=True),
        Binding("q",      "quit",          "Press q to quit", show=True),
    ]

    # ------------------------------------------------------------------
    # Init
    # ------------------------------------------------------------------

    def __init__(self) -> None:
        super().__init__()

        self._source_urls: Dict[str, str] = {
            "IsaiminiHQ": settings.isaimini_url,
            "MassTamilan": settings.get(
                "sources.masstamilan.base_url", "https://www.masstamilan.dev"
            ),
            "FriendsTamilMP3": settings.get(
                "sources.friendstamilmp3.base_url", "https://www.friendstamilmp3.in"
            ),
        }

        # Downloader — tqdm disabled, TUI handles all display
        self._downloader = HTTPDownloader(
            settings.output_dir,
            max_workers=settings.get("download.max_workers", 3),
            show_progress=False,
        )

        self._categories: List[str] = self._resolve_categories()
        self._active_category: str = self._categories[0] if self._categories else "latest"
        self._sources: List[SourceEntry] = self._build_source_entries()

        # Mutable panel state (always modified on main thread via call_from_thread)
        self._albums: List[Album] = []
        self._album_sources: Dict[str, Tuple[str, str]] = {}
        self._songs: List[Song] = []
        self._selected: Set[int] = set()
        self._active_source: Optional[SourceEntry] = None
        self._active_album: Optional[Album] = None
        self._source_pages: Dict[Tuple[str, str], int] = {}
        self._app_start = perf_counter()

        self._log_handler: Optional[TextualLogHandler] = None
        self._file_handler: Optional[logging.FileHandler] = None

        # Concurrency guards
        self._download_lock = threading.Lock()  # sequential per-song downloads

    def _resolve_categories(self) -> List[str]:
        preferred = ["latest", "2026", "2025", "2024", "old", "stars", "singers", "music-directors", "ilaiyaraja", "ar-rahman"]
        found: List[str] = []
        for source_key in ("isaimini", "masstamilan", "friendstamilmp3"):
            raw = settings.get(f"sources.{source_key}.categories", [])
            if isinstance(raw, list):
                for category in raw:
                    cat = str(category).strip().lower()
                    if cat and cat not in found:
                        found.append(cat)

        for cat in preferred:
            if cat not in found:
                found.append(cat)

        ordered = [cat for cat in preferred if cat in found]
        return ordered or preferred

    def _build_source_entries(self) -> List[SourceEntry]:
        return [
            SourceEntry("All Sources",     "All Sources"),
            SourceEntry("IsaiminiHQ",      "IsaiminiHQ"),
            SourceEntry("MassTamilan",     "MassTamilan"),
            SourceEntry("FriendsTamilMP3", "FriendsTamilMP3"),
        ]

    # ------------------------------------------------------------------
    # Compose (layout)
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header()

        # ── search bar ──────────────────────────────────────────────
        with Horizontal(id="search-bar"):
            yield Label("🔍  Search:", id="search-label")
            yield Input(placeholder="Album / movie name…", id="search-input")
            yield Label(
                "Enter to search all sources  •  \\[/] focus  •  [d] download  •  [a] select all",
                id="search-hint",
            )
        # ── category filter bar ──────────────────────────────────────────
        with Horizontal(id="category-bar"):
            yield Label("Filter:", id="cat-label")
            for cat in self._categories:
                _LABELS = {
                    "latest": "Latest", "old": "Old",
                    "stars": "Stars", "singers": "Singers",
                    "music-directors": "MDs",
                    "ilaiyaraja": "Ilaiyaraja", "ar-rahman": "AR Rahman",
                }
                cat_label = _LABELS.get(cat, cat)
                classes = "cat-btn active-cat" if cat == self._active_category else "cat-btn"
                yield Button(cat_label, id=f"cat-{cat}", classes=classes)
        # ── three panels ────────────────────────────────────────────
        with Horizontal(id="main-area"):

            # Left — Sources
            with Vertical(id="sources-panel", classes="panel"):
                yield Label("SOURCES", classes="panel-title")
                yield ListView(id="sources-list", classes="panel-list")

            # Middle — Albums
            with Vertical(id="albums-panel", classes="panel"):
                yield Label("ALBUMS", classes="panel-title")
                yield LoadingIndicator(id="loading-albums")
                yield ListView(id="albums-list", classes="panel-list")

            # Right — Songs
            with Vertical(id="songs-panel", classes="panel"):
                yield Label(
                    "SONGS  [dim](Enter/Space = toggle • [a] all • [d] download)[/dim]",
                    classes="panel-title",
                )
                yield LoadingIndicator(id="loading-songs")
                yield Static("", id="songs-status")
                yield ListView(id="songs-list", classes="panel-list")

        # ── download / log area ──────────────────────────────────────
        with Vertical(id="download-area"):
            with Horizontal(id="dl-top-row"):
                yield Static("", id="dl-status")
                yield ProgressBar(id="dl-progress", show_eta=False, show_percentage=True)
            yield RichLog(id="download-log", highlight=True, markup=True, max_lines=400)

        yield Static("Ready — select a source to browse albums", id="status-bar")
        yield Footer()

    # ------------------------------------------------------------------
    # Mount
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        """Populate sources list and hide transient widgets."""
        lv = self.query_one("#sources-list", ListView)
        for src in self._sources:
            lv.append(ListItem(Label(src.label)))

        self.query_one("#loading-albums").display = False
        self.query_one("#loading-songs").display  = False
        self.query_one("#dl-progress").display    = False

        for src in self._sources:
            for cat in self._categories:
                self._source_pages[(src.source_name, cat)] = 5

        self._attach_log_handler()
        self._setup_file_logging()

        self._log(
            "[bold cyan]🎵 Tamil MP3 Downloader TUI[/bold cyan]  —  "
            "Select a source on the left, then an album, then press [bold]d[/bold] to download. "
            "Press [bold]q[/bold] to quit (Ctrl+C fallback)."
        )

    def on_unmount(self) -> None:
        if self._log_handler is not None:
            root_logger = logging.getLogger()
            try:
                root_logger.removeHandler(self._log_handler)
            except Exception:
                pass
        if self._file_handler is not None:
            root_logger = logging.getLogger()
            try:
                root_logger.removeHandler(self._file_handler)
                self._file_handler.close()
            except Exception:
                pass

    def _setup_file_logging(self) -> None:
        """Open logs/tui.log (append) and attach a FileHandler."""
        try:
            log_dir = Path("logs")
            log_dir.mkdir(parents=True, exist_ok=True)
            log_path = log_dir / "tui.log"
            fh = logging.FileHandler(log_path, mode="a", encoding="utf-8")
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(
                logging.Formatter(
                    "%(asctime)s %(levelname)-8s %(name)s: %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                )
            )
            root_logger = logging.getLogger()
            root_logger.setLevel(logging.DEBUG)
            root_logger.addHandler(fh)
            self._file_handler = fh
            logger.info("=" * 60)
            logger.info("=== TUI session started ===")
            logger.info("Log file: %s", log_path.resolve())
        except Exception as exc:
            self._log(f"[yellow]⚠ Could not open log file: {exc}[/yellow]")

    def _attach_log_handler(self) -> None:
        handler = TextualLogHandler(self)
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        self._log_handler = handler

    # ------------------------------------------------------------------
    # UI helpers (always called on the main thread)
    # ------------------------------------------------------------------

    def _log(self, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.query_one("#download-log", RichLog).write(f"[dim]{ts}[/]  {msg}")

    def _status(self, msg: str) -> None:
        self.query_one("#status-bar", Static).update(msg)

    def _songs_status(self, msg: str) -> None:
        self.query_one("#songs-status", Static).update(msg)

    def _dl_status(self, msg: str) -> None:
        self.query_one("#dl-status", Static).update(msg)

    def _set_loading(self, widget_id: str, show: bool) -> None:
        self.query_one(f"#{widget_id}").display = show

    def _clear_albums(self) -> None:
        self.query_one("#albums-list", ListView).clear()
        self._albums.clear()
        self._album_sources.clear()
        self._active_album = None
        self._clear_songs()

    def _sort_album_rows(self, rows: List[Tuple[Album, str, str]]) -> List[Tuple[Album, str, str]]:
        return sorted(
            rows,
            key=lambda row: (row[0].year or 0, row[0].display_name.lower()),
            reverse=True,
        )

    def _clear_songs(self) -> None:
        self.query_one("#songs-list", ListView).clear()
        self._songs.clear()
        self._selected.clear()

    def _populate_albums(self, rows: List[Tuple[Album, str, str]]) -> None:
        """Fill albums panel from (Album, source_name, category) rows."""
        self._albums = [r[0] for r in rows]
        self._album_sources = {r[0].url: (r[1], r[2]) for r in rows}

        lv = self.query_one("#albums-list", ListView)
        lv.clear()
        for album, _, _ in rows:
            year  = f" [dim]({album.year_str})[/dim]" if album.year else ""
            count = f" [dim cyan]{album.song_count}✦[/dim cyan]" if album.song_count else ""
            lv.append(ListItem(Label(Text.from_markup(f"{album.display_name}{year}{count}"))))

    def _populate_songs(self, songs: List[Song]) -> None:
        """Fill songs panel with MP3-only tracks, selecting all by default."""
        self._songs = [s for s in songs if not s.is_zip]
        self._selected = set(range(len(self._songs)))
        self._render_songs()

    def _create_scraper(self, source_name: str) -> BaseScraper:
        base_url = self._source_urls[source_name]
        if source_name == "IsaiminiHQ":
            return IsaiminiScraper(base_url)
        if source_name == "MassTamilan":
            return MassTamilanScraper(base_url)
        return FriendsTamilMP3Scraper(base_url)

    def _scrape_albums(
        self,
        source_name: str,
        category: str,
        max_pages: int,
        flow_start: float,
    ) -> List[Album]:
        scraper = self._create_scraper(source_name)

        def _progress(page_num: int, total_pages: int) -> None:
            elapsed = perf_counter() - flow_start
            self.call_from_thread(
                self._status,
                (
                    f"Fetching {source_name} {category} "
                    f"page {page_num}/{total_pages} · {elapsed:.1f}s"
                ),
            )
            self.call_from_thread(
                self._log,
                (
                    f"[dim]Fetching page {page_num}/{total_pages} "
                    f"from {source_name} ({category}) · {elapsed:.1f}s[/dim]"
                ),
            )

        try:
            try:
                scraper._init_browser()
            except Exception:
                pass

            return scraper.get_albums(
                category,
                max_pages=max_pages,
                progress_cb=_progress,
            )
        finally:
            try:
                scraper._close_browser()
            except Exception:
                pass

    def _scrape_songs(self, source_name: str, album: Album) -> List[Song]:
        scraper = self._create_scraper(source_name)
        try:
            try:
                scraper._init_browser()
            except Exception:
                pass
            return scraper.get_songs(album)
        finally:
            try:
                scraper._close_browser()
            except Exception:
                pass

    def _render_songs(self, restore_idx: Optional[int] = None) -> None:
        """Rebuild the songs ListView, preserving cursor position."""
        lv = self.query_one("#songs-list", ListView)
        lv.clear()
        for i, song in enumerate(self._songs):
            tick = "✓" if i in self._selected else " "
            if song.is_zip:
                text = Text.from_markup(
                    f"[{tick}] [bold yellow]📦 {song.display_name}[/bold yellow]"
                )
            else:
                qc = "green" if "320" in song.quality else "yellow"
                text = Text.from_markup(
                    f"[{tick}] 🎵 {song.display_name}  "
                    f"[{qc}]{song.quality}[/{qc}]  [dim]{song.size_str}[/dim]"
                )
            lv.append(ListItem(Label(text)))

        target = restore_idx if restore_idx is not None else 0
        if self._songs and 0 <= target < len(self._songs):
            lv.index = target

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        lv_id = event.list_view.id

        if lv_id == "sources-list":
            idx = event.list_view.index
            if idx is None or not (0 <= idx < len(self._sources)):
                return
            entry = self._sources[idx]
            cat_label = {
                "latest": "Latest", "old": "Old",
                "stars": "Stars", "singers": "Singers",
                "music-directors": "MDs",
                "ilaiyaraja": "Ilaiyaraja", "ar-rahman": "AR Rahman",
            }.get(self._active_category, self._active_category)
            logger.info("Source selected: %s | category: %s", entry.source_name, cat_label)
            self._active_source = entry
            self._clear_albums()
            self._fetch_albums(entry)

        elif lv_id == "albums-list":
            idx = event.list_view.index
            if idx is None or not (0 <= idx < len(self._albums)):
                return
            album = self._albums[idx]
            src_info = self._album_sources.get(album.url)
            if src_info is None:
                src_info = ("IsaiminiHQ", "latest")
            logger.info("Album selected: %s | source: %s", album.display_name, src_info[0])
            self._active_album = album
            self._clear_songs()
            self._fetch_songs(album, src_info[0])

        elif lv_id == "songs-list":
            # Enter key — toggle selection of the highlighted song
            self._toggle_song(event.list_view.index)

    def on_key(self, event: Key) -> None:
        """Space bar toggles selection in the songs panel."""
        if event.key == "space":
            focused = self.focused
            if hasattr(focused, "id") and getattr(focused, "id") == "songs-list":
                assert isinstance(focused, ListView)
                self._toggle_song(focused.index)
                event.prevent_default()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        keyword = event.value.strip()
        if keyword:
            self._run_search(keyword)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle category filter button presses."""
        btn_id = event.button.id
        if not (btn_id and btn_id.startswith("cat-")):
            return
        cat = btn_id[4:]  # e.g. "latest", "2026", "2025", "2024"
        if cat == self._active_category:
            event.stop()
            return
        self._active_category = cat
        cat_label = {
            "latest": "Latest", "old": "Old",
            "stars": "Stars", "singers": "Singers",
            "music-directors": "MDs",
            "ilaiyaraja": "Ilaiyaraja", "ar-rahman": "AR Rahman",
        }.get(cat, cat)
        logger.info("Category changed → %s", cat_label)
        self._log(f"[cyan]Category:[/cyan]  {cat_label}")
        # Update visual state for all category buttons
        for btn in self.query(".cat-btn"):
            btn.remove_class("active-cat")
        event.button.add_class("active-cat")
        # Re-fetch albums if a source is already selected
        if self._active_source:
            self._status(f"Category → {cat_label}  |  Reloading {self._active_source.source_name}…")
            self._clear_albums()
            self._fetch_albums(self._active_source)
        else:
            self._status(f"Category → {cat_label}  |  Select a source on the left")
        event.stop()

    def _toggle_song(self, idx: Optional[int]) -> None:
        if idx is None or not (0 <= idx < len(self._songs)):
            return
        if idx in self._selected:
            self._selected.discard(idx)
        else:
            self._selected.add(idx)
        self._render_songs(restore_idx=idx)
        n = len(self._selected)
        self._status(f"{n}/{len(self._songs)} songs selected — press [d] to download")

    # ------------------------------------------------------------------
    # Workers  (run in thread pool; update UI via call_from_thread)
    # ------------------------------------------------------------------

    @work(thread=True)
    def _fetch_albums(self, entry: SourceEntry) -> None:
        """Fetch albums for a source/category in the background."""
        category = self._active_category   # capture current filter at worker start
        label_cat = "Latest" if category == "latest" else category
        started = perf_counter()
        logger.info("Fetch albums start: source=%s category=%s", entry.source_name, label_cat)
        self.call_from_thread(self._set_loading, "loading-albums", True)
        self.call_from_thread(self._log, f"[cyan]Loading albums:[/cyan]  {entry.source_name}  \u00b7  {label_cat}\u2026")
        pages = self._source_pages.get((entry.source_name, category), 5)
        self.call_from_thread(
            self._status,
            f"Fetching {entry.source_name} \u00b7 {label_cat} (pages: {pages})\u2026",
        )

        all_rows: List[Tuple[Album, str, str]] = []
        if entry.source_name == "All Sources":
            _FTP3_ONLY = {"old", "stars", "singers", "music-directors", "ilaiyaraja", "ar-rahman"}
            # These categories only exist on FTP3 — skip Isaimini/MassTamilan.
            # For year categories, FTP3 is stale (newest = 2023) so skip it there.
            if category in _FTP3_ONLY:
                source_names = ["FriendsTamilMP3"]
            else:
                source_names = ["IsaiminiHQ", "MassTamilan"]
            with ThreadPoolExecutor(max_workers=len(source_names)) as pool:
                futures = {
                    pool.submit(self._scrape_albums, src, category, pages, started): src
                    for src in source_names
                }
                for future in as_completed(futures):
                    src = futures[future]
                    try:
                        albums = future.result()
                    except Exception as exc:
                        self.call_from_thread(
                            self._log,
                            f"[red]✗ Album fetch error:[/red] {src}: {exc}",
                        )
                        continue

                    all_rows.extend((a, src, category) for a in albums)
                    sorted_rows = self._sort_album_rows(all_rows)
                    self.call_from_thread(self._populate_albums, sorted_rows)
                    elapsed = perf_counter() - started
                    logger.info("Source %s returned %d albums (cat=%s) in %.1fs",
                                src, len(albums), category, elapsed)
                    self.call_from_thread(
                        self._log,
                        f"[green]✓ {src} finished[/green]: {len(albums)} albums · {elapsed:.1f}s",
                    )
                    self.call_from_thread(
                        self._status,
                        f"Loaded {len(sorted_rows)} albums so far · {elapsed:.1f}s",
                    )
        else:
            try:
                albums = self._scrape_albums(entry.source_name, category, pages, started)
                all_rows = [(a, entry.source_name, category) for a in albums]
            except Exception as exc:
                self.call_from_thread(
                    self._log,
                    f"[red]✗ Album fetch error:[/red]  {exc}",
                )

        self.call_from_thread(self._set_loading, "loading-albums", False)
        elapsed = perf_counter() - started
        total = len(all_rows)
        if total:
            sorted_rows = self._sort_album_rows(all_rows)
            self.call_from_thread(self._populate_albums, sorted_rows)
            self.call_from_thread(
                self._status,
                f"{total} albums loaded · {elapsed:.1f}s elapsed",
            )
            self.call_from_thread(
                self._log,
                f"[green]✓ Album fetch complete[/green] · {total} albums · {elapsed:.1f}s",
            )
            logger.info("Albums found: %d in %.1fs", total, elapsed)
        else:
            self.call_from_thread(
                self._status,
                f"No albums found · {elapsed:.1f}s elapsed",
            )
            self.call_from_thread(
                self._log,
                f"[yellow]⚠ No albums found after {elapsed:.1f}s[/yellow]",
            )
            logger.warning("No albums found for %s / %s in %.1fs", entry.source_name, category, elapsed)

    @work(thread=True)
    def _fetch_songs(self, album: Album, source_name: str) -> None:
        """Fetch songs for a selected album in the background."""
        started = perf_counter()
        logger.info("Fetch songs start: album=%s source=%s", album.display_name, source_name)
        self.call_from_thread(self._set_loading, "loading-songs", True)
        self.call_from_thread(self._songs_status, f"⏳ Loading songs for {album.display_name}…")
        self.call_from_thread(self._log, f"[cyan]Loading songs:[/cyan]  {album.display_name}…")
        self.call_from_thread(self._status, f"Fetching songs for {album.display_name}…")

        songs: List[Song] = []
        try:
            songs = self._scrape_songs(source_name, album)
        except Exception as exc:
            self.call_from_thread(self._log, f"[red]✗ Song fetch error:[/red]  {exc}")
            logger.exception("Song fetch error: album=%s", album.display_name)
        finally:
            self.call_from_thread(self._set_loading, "loading-songs", False)
            self.call_from_thread(self._songs_status, "")

        elapsed = perf_counter() - started
        zip_count = sum(1 for s in songs if s.is_zip)
        mp3_count = len(songs) - zip_count
        logger.info("Songs found: %d MP3, %d ZIP for %s in %.1fs",
                    mp3_count, zip_count, album.display_name, elapsed)
        if songs:
            self.call_from_thread(self._populate_songs, songs)
            self.call_from_thread(
                self._log,
                f"[green]\u2713 {mp3_count} MP3 songs[/green] loaded for {album.display_name} \u00b7 {elapsed:.1f}s",
            )
            if zip_count:
                self.call_from_thread(
                    self._log,
                    f"[dim]Skipped {zip_count} ZIP entries (MP3-only mode)[/dim]",
                )
            self.call_from_thread(
                self._status,
                f"{album.display_name}  \u2014  {mp3_count} MP3 songs \u00b7 {elapsed:.1f}s  "
                "[dim](Space/Enter = toggle \u00b7 [d] download \u00b7 [a] all)[/dim]",
            )
        else:
            self.call_from_thread(
                self._log,
                f"[yellow]⚠ No songs found for this album · {elapsed:.1f}s[/yellow]",
            )

    @work(thread=True)
    def _run_search(self, keyword: str) -> None:
        """Search all sources for matching albums in the background."""
        started = perf_counter()
        self.call_from_thread(self._clear_albums)
        self.call_from_thread(self._log, f"[cyan]Searching:[/cyan]  '{keyword}' across all sources…")
        self.call_from_thread(self._status, f"Searching '{keyword}'…")

        src_list: List[Tuple[str, str, int]] = [
            ("IsaiminiHQ", "latest", 8),
            ("MassTamilan", "latest", 8),
            ("FriendsTamilMP3", "latest", 8),
        ]

        hits:  List[Tuple[Album, str, str, float]] = []
        seen:  Set[Tuple[str, str]] = set()

        with ThreadPoolExecutor(max_workers=len(src_list)) as pool:
            futures = {
                pool.submit(self._scrape_albums, src_name, cat, pages, started): (src_name, cat)
                for src_name, cat, pages in src_list
            }

            for future in as_completed(futures):
                src_name, cat = futures[future]
                try:
                    albums = future.result()
                except Exception as exc:
                    self.call_from_thread(
                        self._log,
                        f"[yellow]⚠ {src_name}: {exc}[/yellow]",
                    )
                    continue

                for album in albums:
                    key = (src_name, album.url)
                    if key in seen:
                        continue
                    seen.add(key)
                    score = _fuzzy_score(keyword, album.display_name)
                    if score >= 0.45:
                        hits.append((album, src_name, cat, score))

                elapsed = perf_counter() - started
                self.call_from_thread(
                    self._log,
                    f"[dim]{src_name} search done · {len(albums)} albums scanned · {elapsed:.1f}s[/dim]",
                )

        hits.sort(key=lambda x: (x[3], x[0].year or 0), reverse=True)

        if not hits:
            self.call_from_thread(
                self._log, "[yellow]⚠ No matches found — try a broader keyword[/yellow]"
            )
            elapsed = perf_counter() - started
            self.call_from_thread(
                self._status,
                f"No results for '{keyword}' · {elapsed:.1f}s",
            )
            return

        def _show_hits() -> None:
            self._albums = [h[0] for h in hits]
            self._album_sources = {h[0].url: (h[1], h[2]) for h in hits}
            lv = self.query_one("#albums-list", ListView)
            lv.clear()
            for album, src_name, _, score in hits:
                pct  = int(score * 100)
                text = Text.from_markup(
                    f"{album.display_name}  [dim]({album.year_str})[/dim]"
                    f"  [bold cyan][{src_name}][/bold cyan]"
                    f"  [green]{pct}%[/green]"
                )
                lv.append(ListItem(Label(text)))

        self.call_from_thread(_show_hits)
        self.call_from_thread(
            self._log,
            f"[green]✓ {len(hits)} matches[/green] for '{keyword}' · {perf_counter() - started:.1f}s",
        )
        self.call_from_thread(
            self._status,
            f"Search: {len(hits)} results for '{keyword}' · {perf_counter() - started:.1f}s",
        )

    @work(thread=True)
    def _do_download(self, songs: List[Song], album: Album) -> None:
        """Download selected songs sequentially with per-song progress reporting."""
        started = perf_counter()
        mp3_songs = [s for s in songs if not s.is_zip]
        skipped_zip = len(songs) - len(mp3_songs)
        if skipped_zip:
            self.call_from_thread(
                self._log,
                f"[dim]Skipped {skipped_zip} ZIP entries (MP3-only mode)[/dim]",
            )

        songs = mp3_songs
        if not songs:
            self.call_from_thread(self._log, "[yellow]\u26a0 Nothing selected to download[/yellow]")
            return

        logger.info("Download started: %s — %d song(s)", album.display_name, len(songs))

        # Show download queue upfront
        def _show_queue(current: int) -> None:
            lines: List[str] = [f"[bold]Queue  \u2014  {album.display_name}:[/bold]"]
            for qi, qs in enumerate(songs):
                if qi < current:
                    status = "[green]\u2713 done[/green]"
                elif qi == current:
                    status = "[cyan]\u2b07 downloading\u2026[/cyan]"
                else:
                    status = "[dim]waiting[/dim]"
                lines.append(f"  {qi + 1:>2}. {qs.display_name[:50]}  {status}")
            self._log("\n".join(lines))

        self.call_from_thread(
            self._log,
            f"[bold cyan]\u2b07 Download started:[/bold cyan]  {album.display_name}  \u2014  {len(songs)} file(s)",
        )
        self.call_from_thread(self._status, f"Downloading {album.display_name}\u2026")

        # Show progress bar
        def _init_pb() -> None:
            pb = self.query_one("#dl-progress", ProgressBar)
            pb.display = True
            pb.update(total=len(songs), progress=0)

        self.call_from_thread(_init_pb)
        self.call_from_thread(_show_queue, 0)

        # Attach ID3 / path metadata to each song
        mp3_n = 0
        for s in songs:
            s.album_name  = album.safe_dirname
            s.album_title = album.display_name
            s.year        = album.year
            s.artist      = s.artist or "Unknown Artist"
            if s.is_zip:
                s.track_number = None
            else:
                mp3_n += 1
                s.track_number = mp3_n

        self._downloader.output_dir = settings.output_dir
        ok_count   = 0
        fail_count = 0

        for i, song in enumerate(songs):
            item_started = perf_counter()
            label = f"{song.display_name[:50]}"
            self.call_from_thread(self._dl_status, f"  \u2b07  {i + 1}/{len(songs)}  {label}\u2026")
            self.call_from_thread(_show_queue, i)
            logger.info("Downloading [%d/%d]: %s", i + 1, len(songs), song.display_name)

            with self._download_lock:
                result = self._downloader.download_song(song)

            if result.success:
                ok_count += 1
                mb = result.size_downloaded / (1024 * 1024)
                item_elapsed = perf_counter() - item_started
                if result.size_downloaded == 0:
                    # File already existed (duplicate skip)
                    self.call_from_thread(
                        self._log,
                        f"  [dim]\u2713 skipped (already downloaded):[/dim]  {song.display_name[:55]}",
                    )
                    logger.info("  Skipped (exists): %s", song.display_name)
                else:
                    self.call_from_thread(
                        self._log,
                        f"  [green]\u2713[/green]  {song.display_name[:55]}  [dim]{mb:.1f} MB \u00b7 {item_elapsed:.1f}s[/dim]",
                    )
                    logger.info("  Done: %s  (%.1f MB, %.1fs)", song.display_name, mb, item_elapsed)
            else:
                fail_count += 1
                item_elapsed = perf_counter() - item_started
                self.call_from_thread(
                    self._log,
                    f"  [red]\u2717[/red]  {song.display_name[:55]}  "
                    f"[dim red]{result.error_message} \u00b7 {item_elapsed:.1f}s[/dim red]",
                )
                logger.error("  Failed: %s — %s", song.display_name, result.error_message)

            self.call_from_thread(
                lambda: self.query_one("#dl-progress", ProgressBar).advance(1)
            )

        # Finish
        def _finish() -> None:
            self.query_one("#dl-progress", ProgressBar).display = False
            self.query_one("#dl-status", Static).update("")
            summary = f"[bold green]\u2713 {ok_count} downloaded[/bold green]"
            if fail_count:
                summary += f"  [bold red]\u2717 {fail_count} failed[/bold red]"
            total_elapsed = perf_counter() - started
            self._log(
                f"[bold]Download complete![/bold]  {summary}  [dim]({total_elapsed:.1f}s total)[/dim]"
            )
            # Compute organized output path
            year = album.year
            if year:
                out_path = settings.output_dir / str(year) / album.safe_dirname
            else:
                out_path = settings.output_dir / album.safe_dirname
            self._log(f"[dim]\ud83d\udcc1  Saved to:  {out_path}[/dim]")
            self._status(
                f"Done \u2014 {ok_count} downloaded"
                + (f", {fail_count} failed" if fail_count else "")
                + f" \u00b7 {total_elapsed:.1f}s"
            )
            logger.info(
                "Download complete: %s — %d ok, %d failed, %.1fs",
                album.display_name, ok_count, fail_count, total_elapsed,
            )

        self.call_from_thread(_finish)

    # ------------------------------------------------------------------
    # Actions (triggered by key bindings)
    # ------------------------------------------------------------------

    def action_download(self) -> None:
        if not self._songs:
            self._log("[yellow]⚠ No songs loaded — select an album first[/yellow]")
            return
        if not self._selected:
            self._log(
                "[yellow]⚠ No songs selected — press [bold]a[/bold] to select all, "
                "or Space/Enter to toggle individual tracks[/yellow]"
            )
            return
        if not self._active_album:
            self._log("[yellow]⚠ No album is active[/yellow]")
            return
        selection = [self._songs[i] for i in sorted(self._selected)]
        self._do_download(selection, self._active_album)

    def action_select_all(self) -> None:
        if self._songs:
            self._selected = set(range(len(self._songs)))
            self._render_songs()
            self._status(f"All {len(self._songs)} songs selected — press [d] to download")

    def action_deselect_all(self) -> None:
        self._selected.clear()
        self._render_songs()
        self._status("All songs deselected")

    def action_focus_search(self) -> None:
        self.query_one("#search-input", Input).focus()

    def action_escape(self) -> None:
        inp = self.query_one("#search-input", Input)
        if inp.value:
            inp.value = ""
        else:
            self.query_one("#sources-list", ListView).focus()

    def action_reload(self) -> None:
        if self._active_source:
            self._clear_albums()
            self._fetch_albums(self._active_source)
        else:
            self._log("[yellow]⚠ No source selected — choose one from the left panel[/yellow]")

    def action_load_more(self) -> None:
        if not self._active_source:
            self._log("[yellow]⚠ Select a source first[/yellow]")
            return
        key = (self._active_source.source_name, self._active_category)
        current = self._source_pages.get(key, 5)
        self._source_pages[key] = current + 5
        self._log(
            f"[cyan]Load more:[/cyan] pages {current} -> {self._source_pages[key]}"
        )
        self._clear_albums()
        self._fetch_albums(self._active_source)


# ─── Entry point ─────────────────────────────────────────────────────────────


if __name__ == "__main__":
    # Initialize library system if available
    if _library_available:
        try:
            initialize_library()
        except Exception as e:
            logging.warning(f"Library initialization failed: {e}")
            # Continue without library system

    TamilMP3TUI().run()
