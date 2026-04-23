#!/usr/bin/env python3
"""
Tamil MP3 Downloader — CustomTkinter GUI

Layout
------
┌──────────────────────────────────────────────────────────────────────┐
│  🔍 [Search input                              ] [Search]            │
├──────────────────────────────────────────────────────────────────────│
│  Filter: [Latest][2026][2025][2024][Old][Stars][Singers][MDs]        │
│          [Ilaiyaraja][AR Rahman]                                      │
├──────────────┬───────────────────────────┬───────────────────────── ┤
│  SOURCES     │  ALBUMS                   │  SONGS                   │
│  All Sources │  Meesaya Murukku 2  2026  │  ☑ Song 1  320kbps      │
│  IsaiminiHQ  │  Maragatha Malai    2026  │  ☑ Song 2  128kbps      │
│  MassTamilan │  Happy Raj          2025  │  ☐ Song 3                │
│  FriendsTMP3 │                           │                          │
├──────────────┴───────────────────────────┴─────────────────────────-┤
│  [⬇ Download] [Select All] [Clear] [Load More]   Status…  ████░░   │
├──────────────────────────────────────────────────────────────────────│
│  Log output (scrolling)                                              │
└──────────────────────────────────────────────────────────────────────┘

Run: python gui.py
"""

from __future__ import annotations

import logging
import json
import re
import shutil
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from time import perf_counter
from typing import Dict, List, Optional, Set, Tuple

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

from config.settings import settings
from downloaders.http_downloader import HTTPDownloader
from models.song import Album, Song
from scrapers.base import BaseScraper
from scrapers.friendstamilmp3 import FriendsTamilMP3Scraper
from scrapers.isaimini import IsaiminiScraper
from scrapers.kollysongs import KollySongsScraper
from scrapers.masstamilan import MassTamilanScraper

logger = logging.getLogger(__name__)


# ─── Appearance ───────────────────────────────────────────────────────────────

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# ─── Constants ────────────────────────────────────────────────────────────────

_CAT_LABELS: Dict[str, str] = {
    "latest": "Latest",
    "2026": "2026",
    "2025": "2025",
    "2024": "2024",
    "old": "Old",
    "stars": "Stars",
    "singers": "Singers",
    "music-directors": "MDs (Music Directors)",
    "ilaiyaraja": "Ilaiyaraja",
    "ar-rahman": "AR Rahman",
}

_ALL_CATS: List[str] = [
    "latest", "2026", "2025", "2024",
    "old", "stars", "singers", "music-directors",
]

# Max lines kept in the GUI log panel (ring buffer)
_MAX_LOG_LINES = 500

# These categories are reliable only on FriendsTamilMP3.
# (MD and Old are now expanded with safe multi-source fallbacks.)
_FTP3_ONLY: Set[str] = {"stars", "singers", "ilaiyaraja", "ar-rahman"}

# ── Top Songs feature ──────────────────────────────────────────────
_TOP_CAT_LABELS: Dict[str, str] = {
    "top-songs":     "Top Songs",
    "top-2026":      "Top 2026",
    "top-2025":      "Top 2025",
    "top-2024":      "Top 2024",
    "top-2010-2015": "2010–2015",
    "top-2015-2020": "2015–2020",
}
_TOP_CATS_LIST: List[str] = list(_TOP_CAT_LABELS.keys())

# (year_min, year_max) — both None means no year filter
_TOP_CAT_YEAR_RANGE: Dict[str, Tuple[Optional[int], Optional[int]]] = {
    "top-songs":     (None, None),
    "top-2026":      (2026, 2026),
    "top-2025":      (2025, 2025),
    "top-2024":      (2024, 2024),
    "top-2010-2015": (2010, 2015),
    "top-2015-2020": (2015, 2020),
}


# ─── Data model ───────────────────────────────────────────────────────────────

@dataclass
class SourceEntry:
    """A selectable entry in the Sources panel."""
    label: str
    source_name: str


# ─── Fuzzy scoring ────────────────────────────────────────────────────────────

def _fuzzy_score(keyword: str, candidate: str) -> float:
    kw, text = keyword.strip().lower(), candidate.strip().lower()
    if not kw or not text:
        return 0.0
    if len(kw) <= 2:
        return 1.0 if kw in text else 0.0
    bonus = 0.25 if kw in text else 0.0
    full = SequenceMatcher(None, kw, text).ratio()
    token = max(
        (SequenceMatcher(None, kw, t).ratio() for t in text.split()),
        default=0.0,
    )
    return min(1.0, max(full, token) + bonus)


def _search_score(keyword: str, candidate: str) -> float:
    """
    Score an album name against a search keyword using word-boundary matching.
    This avoids false positives like "raya" matching "Raja" or "Aaranya".

    Priority:
      1.0  — album name starts with keyword     (e.g. "raya" → "Rayaan (2024)")
      0.85 — any word in title starts with kw   (word-boundary prefix match)
      0.55 — keyword appears anywhere as substr
      0.50 — very high fuzzy similarity on a single token (≥5-char queries only)
      0.0  — no meaningful match
    """
    kw = keyword.strip().lower()
    text = candidate.strip().lower()
    if not kw or not text:
        return 0.0
    kw_esc = re.escape(kw)

    if text.startswith(kw):
        return 1.0

    # Word-boundary prefix: a word in the title must START with the keyword
    # re.search(r"\bdhanush", "Dhanush Hits") → match
    # re.search(r"\braya",   "Raja Songs")   → no match  ✓
    if re.search(rf"\b{kw_esc}", text):
        return 0.85

    if kw in text:
        return 0.55

    # Fuzzy only for longer queries (≥ 5 chars) at very high similarity
    if len(kw) >= 5:
        token_score = max(
            (SequenceMatcher(None, kw, t).ratio() for t in text.split()),
            default=0.0,
        )
        if token_score >= 0.85:
            return 0.50

    return 0.0


def _dedup_songs(songs: List[Song], strategy: str = "first") -> List[Song]:
    """Deduplicate by normalized display name using first or smaller-size strategy."""
    strategy = (strategy or "first").strip().lower()
    picked: Dict[str, Song] = {}
    order: List[str] = []

    def _size_value(song: Song) -> float:
        if song.size_mb is None:
            return float("inf")
        return float(song.size_mb)

    for s in songs:
        key = re.sub(r"[^a-z0-9]", "", s.display_name.lower())
        if not key:
            continue
        if key not in picked:
            picked[key] = s
            order.append(key)
            continue
        if strategy == "smaller-size" and _size_value(s) < _size_value(picked[key]):
            picked[key] = s
    return [picked[k] for k in order]


# ─── Log handler ──────────────────────────────────────────────────────────────

class GUILogHandler(logging.Handler):
    """Route stdlib logging records into the GUI log panel."""

    def __init__(self, app: "TamilMP3GUI") -> None:
        super().__init__()
        self._app = app

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self._app.after(0, lambda m=msg: self._app._append_log(m))
        except Exception:
            pass


# ─── Main application ─────────────────────────────────────────────────────────

class TamilMP3GUI(ctk.CTk):
    """Tamil MP3 Downloader — CustomTkinter GUI."""

    # ------------------------------------------------------------------
    # Init
    # ------------------------------------------------------------------

    def __init__(self) -> None:
        super().__init__()

        self.title("🎵 Tamil MP3 Downloader")
        self.geometry("1400x900")
        self.minsize(1100, 720)

        # ── Set window icon for taskbar (Windows-specific) ────────────
        try:
            from ctypes import windll
            icon_path = Path(__file__).parent / "Icons" / "Tamil_mp3_downloader.ico"
            if icon_path.exists():
                # Try tkinter's iconbitmap first
                self.iconbitmap(str(icon_path))
                # Also try to set via Windows API for better taskbar support
                try:
                    windll.shell32.SetCurrentProcessExplicitAppUserModelID("TamilMP3Downloader")
                except Exception:
                    pass
        except Exception:
            pass  # Icon optional; continue without it

        # ── Business state ────────────────────────────────────────────
        self._source_urls: Dict[str, str] = {
            "IsaiminiHQ": settings.isaimini_url,
            "MassTamilan": settings.get(
                "sources.masstamilan.base_url", "https://www.masstamilan.dev"
            ),
            "FriendsTamilMP3": settings.get(
                "sources.friendstamilmp3.base_url", "https://www.friendstamilmp3.in"
            ),
            "KollySongs": settings.get(
                "sources.kollysongs.base_url", "https://www.kollysongs.com"
            ),
        }

        self._downloader = HTTPDownloader(
            settings.output_dir,
            max_workers=settings.get("download.max_workers", 3),
            show_progress=False,
        )

        self._categories: List[str] = _ALL_CATS
        self._active_category: str = "latest"
        self._sources: List[SourceEntry] = [
            SourceEntry("All Sources",     "All Sources"),
            SourceEntry("IsaiminiHQ",      "IsaiminiHQ"),
            SourceEntry("MassTamilan",     "MassTamilan"),
            SourceEntry("FriendsTamilMP3", "FriendsTamilMP3"),
            SourceEntry("KollySongs",      "KollySongs"),
        ]

        self._albums: List[Album] = []
        self._album_sources: Dict[str, Tuple[str, str]] = {}  # url → (source_name, category)
        self._songs: List[Song] = []
        self._song_vars: List[tk.BooleanVar] = []
        self._selected: Set[int] = set()
        self._active_source: Optional[SourceEntry] = None
        self._active_album: Optional[Album] = None
        self._source_pages: Dict[Tuple[str, str], int] = {}
        self._download_lock = threading.Lock()
        self._is_top_mode: bool = False  # True when a top-songs category is active
        self._load_token: int = 0        # Incremented to invalidate stale workers
        self._cache_dir: Path = Path("cache")
        self._cache_dir.mkdir(exist_ok=True)
        self._cache_enabled: bool = bool(settings.get("ui.cache.enabled", True))
        self._cache_ttl: int = int(settings.get("ui.cache.ttl_seconds", 21600))
        self._cache_live_year: str = str(datetime.now().year)
        self._cache_hits: int = 0
        self._cache_misses: int = 0
        self._cache_bypasses: int = 0
        self._cache_expired: int = 0
        self._cache_errors: int = 0
        self._top_adaptive_enabled: bool = bool(
            settings.get("ui.top_loading.adaptive_enabled", True)
        )
        self._top_adaptive_min_albums: int = int(
            settings.get("ui.top_loading.min_albums", 24)
        )
        self._top_adaptive_large_cutoff: int = int(
            settings.get("ui.top_loading.large_cutoff", 40)
        )
        self._top_adaptive_window_small: int = int(
            settings.get("ui.top_loading.window_small", 6)
        )
        self._top_adaptive_window_large: int = int(
            settings.get("ui.top_loading.window_large", 10)
        )
        self._top_adaptive_plateau_growth: int = int(
            settings.get("ui.top_loading.plateau_growth", 1)
        )
        self._top_adaptive_plateau_streak: int = int(
            settings.get("ui.top_loading.plateau_streak", 2)
        )
        self._dedupe_strategy: str = str(
            settings.get("ui.dedupe.strategy", "smaller-size")
        )
        self._queue_lines: List[str] = []
        self._cancel_download_requested: bool = False
        self._is_downloading: bool = False
        self._last_failed_songs: List[Song] = []

        # ── UI references (built in _build_ui) ───────────────────────
        self._cat_buttons: Dict[str, ctk.CTkButton] = {}
        self._top_cat_buttons: Dict[str, ctk.CTkButton] = {}
        self._source_buttons: List[ctk.CTkButton] = []
        self._song_frame: Optional[ctk.CTkScrollableFrame] = None
        self._albums_lb: Optional[tk.Listbox] = None
        self._loading_label: Optional[ctk.CTkLabel] = None
        self._search_var: Optional[tk.StringVar] = None
        self._status_var: Optional[tk.StringVar] = None
        self._cache_stats_var: Optional[tk.StringVar] = None
        self._song_preview_var: Optional[tk.StringVar] = None
        self._log_box: Optional[ctk.CTkTextbox] = None
        self._queue_box: Optional[ctk.CTkTextbox] = None
        self._progress_bar: Optional[ctk.CTkProgressBar] = None
        self._log_handler: Optional[GUILogHandler] = None
        self._file_handler: Optional[logging.FileHandler] = None

        # ── Build ─────────────────────────────────────────────────────
        self._build_ui()
        self._setup_logging()
        self._log("🎵 Tamil MP3 Downloader ready.  Select a source on the left to begin.")

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Build the complete UI layout using CTk widgets."""
        self.grid_rowconfigure(3, weight=1)  # main area grows
        self.grid_columnconfigure(0, weight=1)

        # ── Row 0: Search bar ─────────────────────────────────────────
        search_frame = ctk.CTkFrame(self, height=48, corner_radius=0)
        search_frame.grid(row=0, column=0, sticky="ew")
        search_frame.grid_columnconfigure(1, weight=1)
        search_frame.grid_propagate(False)

        ctk.CTkLabel(
            search_frame, text="🔍  Search:", font=ctk.CTkFont(size=13, weight="bold")
        ).grid(row=0, column=0, padx=(12, 6), pady=10)

        self._search_var = tk.StringVar()
        search_entry = ctk.CTkEntry(
            search_frame,
            textvariable=self._search_var,
            placeholder_text="Album / movie name…",
            height=32,
        )
        search_entry.grid(row=0, column=1, padx=6, pady=8, sticky="ew")
        search_entry.bind("<Return>", lambda _e: self._on_search())

        ctk.CTkButton(
            search_frame, text="Search", width=100, height=32,
            command=self._on_search,
        ).grid(row=0, column=2, padx=(6, 12), pady=8)

        # ── Row 1: Category bar ───────────────────────────────────────
        cat_frame = ctk.CTkFrame(self, height=48, corner_radius=0)
        cat_frame.grid(row=1, column=0, sticky="ew")
        cat_frame.grid_propagate(False)

        ctk.CTkLabel(
            cat_frame, text="Filter:", text_color="gray",
            font=ctk.CTkFont(size=12)
        ).pack(side="left", padx=(12, 4))

        for cat in self._categories:
            is_active = cat == self._active_category
            btn = ctk.CTkButton(
                cat_frame,
                text=_CAT_LABELS.get(cat, cat),
                width=82,
                height=30,
                corner_radius=6,
                fg_color="#1f538d" if is_active else "transparent",
                hover_color="#2a6abf",
                border_width=1,
                border_color="#444",
                text_color="white" if is_active else "#aaa",
                font=ctk.CTkFont(size=12),
                command=lambda c=cat: self._on_category(c),
            )
            btn.pack(side="left", padx=3, pady=9)
            self._cat_buttons[cat] = btn

        # ── Row 2: Top Songs bar ──────────────────────────────────────
        top_frame = ctk.CTkFrame(self, height=44, corner_radius=0)
        top_frame.grid(row=2, column=0, sticky="ew")
        top_frame.grid_propagate(False)

        ctk.CTkLabel(
            top_frame, text="🎯 Top:", text_color="#e8a020",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(side="left", padx=(12, 4))

        for cat in _TOP_CATS_LIST:
            btn = ctk.CTkButton(
                top_frame,
                text=_TOP_CAT_LABELS[cat],
                width=90,
                height=30,
                corner_radius=6,
                fg_color="transparent",
                hover_color="#4a2800",
                border_width=1,
                border_color="#555",
                text_color="#999",
                font=ctk.CTkFont(size=12),
                command=lambda c=cat: self._on_category(c),
            )
            btn.pack(side="left", padx=3, pady=7)
            self._top_cat_buttons[cat] = btn

        # ── Row 3: Main 3-panel area ──────────────────────────────────
        main_frame = ctk.CTkFrame(self, corner_radius=0)
        main_frame.grid(row=3, column=0, sticky="nsew")
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_columnconfigure(0, weight=1, minsize=190)
        main_frame.grid_columnconfigure(1, weight=3)
        main_frame.grid_columnconfigure(2, weight=2)

        # ── Left: Sources ─────────────────────────────────────────────
        sources_outer = ctk.CTkFrame(main_frame, corner_radius=6)
        sources_outer.grid(row=0, column=0, sticky="nsew", padx=(4, 2), pady=4)
        sources_outer.grid_rowconfigure(1, weight=1)
        sources_outer.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            sources_outer, text="SOURCES",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#aaaacc",
        ).grid(row=0, column=0, sticky="ew", padx=4, pady=(6, 2))

        sources_scroll = ctk.CTkScrollableFrame(sources_outer, corner_radius=0)
        sources_scroll.grid(row=1, column=0, sticky="nsew", padx=2, pady=(2, 4))

        for entry in self._sources:
            btn = ctk.CTkButton(
                sources_scroll,
                text=entry.label,
                anchor="w",
                height=36,
                font=ctk.CTkFont(size=12),
                fg_color="transparent",
                hover_color="#2a3a5a",
                corner_radius=4,
                command=lambda e=entry: self._on_source_click(e),
            )
            btn.pack(fill="x", padx=2, pady=2)
            self._source_buttons.append(btn)

        # ── Middle: Albums ────────────────────────────────────────────
        albums_outer = ctk.CTkFrame(main_frame, corner_radius=6)
        albums_outer.grid(row=0, column=1, sticky="nsew", padx=2, pady=4)
        albums_outer.grid_rowconfigure(2, weight=1)
        albums_outer.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            albums_outer, text="ALBUMS",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#aaaacc",
        ).grid(row=0, column=0, sticky="ew", padx=4, pady=(6, 2))

        self._loading_label = ctk.CTkLabel(
            albums_outer, text="⏳  Loading albums…",
            text_color="#888",
            font=ctk.CTkFont(size=12),
        )
        self._loading_label.grid(row=1, column=0, padx=4, pady=2, sticky="w")
        self._loading_label.grid_remove()  # hidden until fetch starts

        albums_list_frame = tk.Frame(albums_outer, bg="#1c1c2e")
        albums_list_frame.grid(row=2, column=0, sticky="nsew", padx=4, pady=(0, 4))
        albums_list_frame.grid_rowconfigure(0, weight=1)
        albums_list_frame.grid_columnconfigure(0, weight=1)

        self._albums_lb = tk.Listbox(
            albums_list_frame,
            bg="#1c1c2e",
            fg="#e0e0e0",
            selectbackground="#1f538d",
            selectforeground="white",
            activestyle="none",
            font=("Consolas", 11),
            borderwidth=0,
            highlightthickness=0,
            relief="flat",
        )
        self._albums_lb.grid(row=0, column=0, sticky="nsew")
        self._albums_lb.bind("<<ListboxSelect>>", self._on_album_select)

        albums_vsb = ttk.Scrollbar(
            albums_list_frame, orient="vertical", command=self._albums_lb.yview
        )
        albums_vsb.grid(row=0, column=1, sticky="ns")
        self._albums_lb.configure(yscrollcommand=albums_vsb.set)

        # ── Right: Songs ──────────────────────────────────────────────
        songs_outer = ctk.CTkFrame(main_frame, corner_radius=6)
        songs_outer.grid(row=0, column=2, sticky="nsew", padx=(2, 4), pady=4)
        songs_outer.grid_rowconfigure(1, weight=1)
        songs_outer.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            songs_outer, text="SONGS  (Space/click = toggle • all by default)",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#aaaacc",
        ).grid(row=0, column=0, sticky="ew", padx=4, pady=(6, 2))

        self._song_frame = ctk.CTkScrollableFrame(songs_outer, corner_radius=0)
        self._song_frame.grid(row=1, column=0, sticky="nsew", padx=2, pady=(0, 4))

        # ── Row 3: Controls ───────────────────────────────────────────
        ctrl_frame = ctk.CTkFrame(self, height=54, corner_radius=0)
        ctrl_frame.grid(row=4, column=0, sticky="ew")
        ctrl_frame.grid_propagate(False)
        ctrl_frame.grid_columnconfigure(9, weight=1)

        ctk.CTkButton(
            ctrl_frame, text="⬇  Download", width=130, height=34,
            fg_color="#1a6b3c", hover_color="#236b4a",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._on_download,
        ).grid(row=0, column=0, padx=(10, 4), pady=10)

        ctk.CTkButton(
            ctrl_frame, text="Select All", width=100, height=34,
            command=self._on_select_all,
        ).grid(row=0, column=1, padx=4, pady=10)

        ctk.CTkButton(
            ctrl_frame, text="Clear", width=80, height=34,
            command=self._on_clear_selection,
        ).grid(row=0, column=2, padx=4, pady=10)

        ctk.CTkButton(
            ctrl_frame, text="Load More", width=100, height=34,
            command=self._on_load_more,
        ).grid(row=0, column=3, padx=4, pady=10)

        ctk.CTkButton(
            ctrl_frame, text="Reload", width=80, height=34,
            command=self._on_reload,
        ).grid(row=0, column=4, padx=4, pady=10)

        ctk.CTkButton(
            ctrl_frame, text="Cancel", width=78, height=34,
            fg_color="#7a2a2a", hover_color="#8d3434",
            command=self._on_cancel_download,
        ).grid(row=0, column=5, padx=4, pady=10)

        ctk.CTkButton(
            ctrl_frame, text="Retry Failed", width=110, height=34,
            command=self._on_retry_failed,
        ).grid(row=0, column=6, padx=4, pady=10)

        ctk.CTkButton(
            ctrl_frame, text="Clear Cache", width=100, height=34,
            command=self._on_clear_cache,
        ).grid(row=0, column=7, padx=4, pady=10)

        ctk.CTkButton(
            ctrl_frame, text="Settings", width=86, height=34,
            command=self._on_open_settings,
        ).grid(row=0, column=8, padx=4, pady=10)

        self._status_var = tk.StringVar(value="Ready — select a source to begin")
        ctk.CTkLabel(
            ctrl_frame, textvariable=self._status_var,
            text_color="gray", anchor="w",
            font=ctk.CTkFont(size=11),
        ).grid(row=0, column=9, padx=(8, 4), pady=10, sticky="ew")

        self._progress_bar = ctk.CTkProgressBar(ctrl_frame, width=180, height=14)
        self._progress_bar.set(0)
        self._progress_bar.grid(row=0, column=10, padx=(4, 10), pady=10)
        self._progress_bar.grid_remove()  # hidden until download starts

        # ── Row 4: Log panel ──────────────────────────────────────────
        log_frame = ctk.CTkFrame(self, corner_radius=0)
        log_frame.grid(row=5, column=0, sticky="ew")
        log_frame.grid_columnconfigure(0, weight=1)

        self._log_box = ctk.CTkTextbox(
            log_frame,
            height=160,
            font=ctk.CTkFont(family="Consolas", size=11),
            state="disabled",
            wrap="word",
        )
        self._log_box.grid(row=0, column=0, sticky="ew", padx=4, pady=(4, 4))

        self._cache_stats_var = tk.StringVar(value=f"Cache: {self._cache_stats_text()}")
        ctk.CTkLabel(
            log_frame,
            textvariable=self._cache_stats_var,
            font=ctk.CTkFont(size=10),
            text_color="#8ba7b7",
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 2))

        # Keyboard shortcuts for faster workflow
        self.bind_all("<Control-a>", lambda _e: self._on_select_all())
        self.bind_all("<Control-d>", lambda _e: self._on_clear_selection())
        self.bind_all("<Control-Return>", lambda _e: self._on_download())

        # Scrollbar style fix for tk.Listbox
        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "Vertical.TScrollbar",
            background="#2b2b2b",
            troughcolor="#1c1c2e",
            bordercolor="#1c1c2e",
            arrowcolor="#aaa",
        )

    # ------------------------------------------------------------------
    # Logging setup
    # ------------------------------------------------------------------

    def _setup_logging(self) -> None:
        log_dir = Path(__file__).parent / "logs"
        log_dir.mkdir(exist_ok=True)

        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)

        fmt_full = logging.Formatter("%(asctime)s  %(levelname)-8s  %(name)s: %(message)s")
        fmt_short = logging.Formatter("%(levelname)s  %(name)s: %(message)s")

        # GUI log — overwrite each run
        try:
            gui_fh = logging.FileHandler(
                log_dir / "gui.log", encoding="utf-8", mode="w"
            )
            gui_fh.setLevel(logging.INFO)
            gui_fh.setFormatter(fmt_full)
            root_logger.addHandler(gui_fh)
            self._file_handler = gui_fh
        except Exception:
            pass

        # Scraper log — overwrite each run, captures DEBUG from all scrapers
        try:
            scraper_fh = logging.FileHandler(
                log_dir / "scraper.log", encoding="utf-8", mode="w"
            )
            scraper_fh.setLevel(logging.DEBUG)
            scraper_fh.setFormatter(fmt_full)
            for name in ("scrapers", "scrapers.isaimini", "scrapers.masstamilan",
                         "scrapers.friendstamilmp3"):
                logging.getLogger(name).addHandler(scraper_fh)
        except Exception:
            pass

        # GUI panel — shows INFO+ in the on-screen log box
        self._log_handler = GUILogHandler(self)
        self._log_handler.setLevel(logging.INFO)
        self._log_handler.setFormatter(fmt_short)
        root_logger.addHandler(self._log_handler)

    # ------------------------------------------------------------------
    # Log helpers  (safe to call from any thread)
    # ------------------------------------------------------------------

    def _append_log(self, msg: str) -> None:
        """Append text to the log panel (main thread only). Ring buffer: keeps last 500 lines."""
        self._log_box.configure(state="normal")
        self._log_box.insert("end", msg + "\n")
        # Trim oldest lines when over limit
        line_count = int(self._log_box.index("end-1c").split(".")[0])
        if line_count > _MAX_LOG_LINES:
            self._log_box.delete("1.0", f"{line_count - _MAX_LOG_LINES}.0")
        self._log_box.configure(state="disabled")
        self._log_box.see("end")

    def _log(self, msg: str) -> None:
        """Thread-safe log append."""
        self.after(0, lambda m=msg: self._append_log(m))

    def _set_status(self, msg: str) -> None:
        """Thread-safe status bar update."""
        self.after(0, lambda m=msg: self._status_var.set(m))

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_key_part(v: str) -> str:
        return re.sub(r"[^a-zA-Z0-9_.-]+", "_", str(v)).strip("_")

    def _cache_path(self, prefix: str, *parts: str) -> Path:
        key = "__".join([self._safe_key_part(prefix)] + [self._safe_key_part(p) for p in parts])
        return self._cache_dir / f"{key}.json"

    def _cache_allowed(self, kind: str, category: str) -> bool:
        """Bypass cache for live/current-year categories so new releases appear immediately."""
        category = str(category)
        live_top = f"top-{self._cache_live_year}"
        if kind in {"albums", "top"} and category in {self._cache_live_year, live_top}:
            return False
        return True

    def _cache_get(self, path: Path) -> Optional[dict]:
        if not self._cache_enabled:
            return None
        if not path.exists():
            self._cache_misses += 1
            self._schedule_cache_stats_refresh()
            return None
        try:
            age = max(0.0, datetime.now().timestamp() - path.stat().st_mtime)
            if self._cache_ttl > 0 and age > self._cache_ttl:
                self._cache_misses += 1
                self._cache_expired += 1
                self._schedule_cache_stats_refresh()
                return None
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                self._cache_hits += 1
                self._schedule_cache_stats_refresh()
                return data
            self._cache_misses += 1
            self._schedule_cache_stats_refresh()
            return None
        except Exception:
            self._cache_misses += 1
            self._cache_errors += 1
            self._schedule_cache_stats_refresh()
            return None

    def _cache_set(self, path: Path, payload: dict) -> None:
        if not self._cache_enabled:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False)
        except Exception:
            pass

    def _cache_mark_bypass(self) -> None:
        self._cache_bypasses += 1
        self._schedule_cache_stats_refresh()

    def _cache_stats_text(self) -> str:
        return (
            f"cache h/m/b={self._cache_hits}/{self._cache_misses}/{self._cache_bypasses}"
            f" (exp={self._cache_expired}, err={self._cache_errors})"
        )

    def _refresh_cache_stats(self) -> None:
        if self._cache_stats_var is not None:
            self._cache_stats_var.set(f"Cache: {self._cache_stats_text()}")

    def _schedule_cache_stats_refresh(self) -> None:
        try:
            self.after(0, self._refresh_cache_stats)
        except Exception:
            pass

    @staticmethod
    def _album_to_dict(a: Album) -> dict:
        return {
            "name": a.name,
            "url": a.url,
            "year": a.year,
            "song_count": a.song_count,
            "source": a.source,
        }

    @staticmethod
    def _album_from_dict(d: dict) -> Album:
        return Album(
            name=d.get("name", ""),
            url=d.get("url", ""),
            year=d.get("year"),
            song_count=d.get("song_count"),
            source=d.get("source", "isaimini"),
        )

    @staticmethod
    def _song_to_dict(s: Song) -> dict:
        return {
            "name": s.name,
            "url": s.url,
            "size_mb": s.size_mb,
            "quality": s.quality,
            "album_name": s.album_name,
            "artist": s.artist,
            "album_title": s.album_title,
            "year": s.year,
            "track_number": s.track_number,
            "cover_art_url": s.cover_art_url,
        }

    @staticmethod
    def _song_from_dict(d: dict) -> Song:
        return Song(
            name=d.get("name", ""),
            url=d.get("url", ""),
            size_mb=d.get("size_mb"),
            quality=d.get("quality", "320kbps"),
            album_name=d.get("album_name", ""),
            artist=d.get("artist"),
            album_title=d.get("album_title"),
            year=d.get("year"),
            track_number=d.get("track_number"),
            cover_art_url=d.get("cover_art_url"),
        )

    # ------------------------------------------------------------------
    # Queue helpers
    # ------------------------------------------------------------------

    def _queue_add(self, line: str) -> None:
        if self._queue_box is None:
            return
        self._queue_lines.append(line)
        if len(self._queue_lines) > 150:
            self._queue_lines = self._queue_lines[-150:]
        self._queue_box.configure(state="normal")
        self._queue_box.delete("1.0", "end")
        self._queue_box.insert("end", "\n".join(self._queue_lines[-8:]))
        self._queue_box.configure(state="disabled")
        self._queue_box.see("end")

    def _ordered_sources(self, source_names: List[str]) -> List[str]:
        preferred = str(settings.get("ui.preferred_source", "")).strip()
        if preferred and preferred in source_names:
            return [preferred] + [s for s in source_names if s != preferred]
        return source_names

    @staticmethod
    def _norm_name(value: str) -> str:
        return re.sub(r"[^a-z0-9]", "", value.lower())

    def _find_existing_in_dir(self, song: Song, out_dir: Path) -> Optional[Path]:
        target = self._norm_name(song.display_name)
        if not target or not out_dir.exists():
            return None
        for p in out_dir.glob("*.mp3"):
            try:
                if p.is_file() and p.stat().st_size > 0 and self._norm_name(p.stem) == target:
                    return p
            except Exception:
                continue
        return None

    def _aria2_executable(self) -> Optional[str]:
        if not bool(settings.get("download.external_downloader.enabled", False)):
            return None
        configured = str(settings.get("download.external_downloader.aria2_path", "aria2c.exe")).strip()
        if configured and Path(configured).exists():
            return configured
        found = shutil.which(configured or "aria2c")
        return found

    def _song_output_dir(self, song: Song, album: Album, is_top: bool, year: Optional[int]) -> Path:
        if is_top:
            return settings.output_dir / song.album_name if song.album_name else settings.output_dir
        if year:
            return settings.output_dir / str(year) / album.safe_dirname
        return settings.output_dir / album.safe_dirname

    def _launch_aria2_song(self, aria2_exe: str, song: Song, out_dir: Path) -> bool:
        out_dir.mkdir(parents=True, exist_ok=True)
        out_name = song.safe_filename
        out_path = out_dir / out_name
        if out_path.exists() and out_path.stat().st_size > 0:
            return True

        flags = 0
        if bool(settings.get("download.external_downloader.detached", True)):
            flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)

        cmd = [
            aria2_exe,
            "--continue=true",
            "--summary-interval=0",
            "--console-log-level=warn",
            "-d", str(out_dir),
            "-o", out_name,
            song.url,
        ]
        subprocess.Popen(cmd, creationflags=flags)
        return True

    def _build_aria2_queue_file(self, entries: List[Tuple[Song, Path]]) -> Path:
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        queue_file = self._cache_dir / f"aria2_queue_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        lines: List[str] = []
        for s, out_dir in entries:
            lines.append(s.url)
            lines.append(f"  dir={str(out_dir)}")
            lines.append(f"  out={s.safe_filename}")
            lines.append("  continue=true")
            lines.append("")
        with open(queue_file, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
        return queue_file

    def _launch_aria2_batch(self, aria2_exe: str, queue_file: Path) -> bool:
        flags = 0
        if bool(settings.get("download.external_downloader.detached", True)):
            flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)

        max_c = int(settings.get("download.external_downloader.max_concurrent", 3))
        cmd = [
            aria2_exe,
            "--continue=true",
            "--summary-interval=0",
            "--console-log-level=warn",
            "--max-concurrent-downloads", str(max(1, max_c)),
            "-i", str(queue_file),
        ]
        subprocess.Popen(cmd, creationflags=flags)
        return True

    def _update_song_preview(self, song: Optional[Song], source_name: str = "—") -> None:
        if self._song_preview_var is None:
            return
        if song is None:
            self._song_preview_var.set("Song: —\nMovie: —\nComposer: —\nYear: —\nSize: —\nSource: —")
            return
        movie = song.album_title or song.album_name or "—"
        artist = song.artist or "—"
        year = str(song.year) if song.year else "—"
        size = song.size_str or "—"
        self._song_preview_var.set(
            f"Song: {song.display_name}\n"
            f"Movie: {movie}\n"
            f"Composer: {artist}\n"
            f"Year: {year}\n"
            f"Size: {size}\n"
            f"Source: {source_name}"
        )

    def _set_loading(self, visible: bool, text: str = "⏳  Loading albums…") -> None:
        """Show/hide the albums loading indicator (main thread only)."""
        if self._loading_label is None:
            return
        if visible:
            self._loading_label.configure(text=text)
            self._loading_label.grid()
        else:
            self._loading_label.grid_remove()

    def _set_activity_progress(self, visible: bool, current: int = 0, total: int = 1) -> None:
        if self._progress_bar is None or self._is_downloading:
            return
        if visible:
            self._progress_bar.grid()
            denom = max(1, total)
            self._progress_bar.set(max(0.0, min(1.0, current / denom)))
        else:
            self._progress_bar.grid_remove()

    def _next_load_token(self) -> int:
        """Invalidate previous album/search/top workers and return the active token."""
        self._load_token += 1
        return self._load_token

    def _is_load_active(self, token: int) -> bool:
        return token == self._load_token

    # ------------------------------------------------------------------
    # Category / Source selection
    # ------------------------------------------------------------------

    def _on_category(self, cat: str) -> None:
        if cat == self._active_category:
            return
        self._active_category = cat
        is_top = cat in _TOP_CAT_YEAR_RANGE
        self._is_top_mode = is_top

        # Update visual state — regular buttons
        for c, btn in self._cat_buttons.items():
            btn.configure(
                fg_color="#1f538d" if (not is_top and c == cat) else "transparent",
                text_color="white" if (not is_top and c == cat) else "#aaa",
            )
        # top-songs buttons
        for c, btn in self._top_cat_buttons.items():
            btn.configure(
                fg_color="#6b4500" if (is_top and c == cat) else "transparent",
                text_color="white" if (is_top and c == cat) else "#999",
            )

        label = _TOP_CAT_LABELS.get(cat) or _CAT_LABELS.get(cat, cat)
        logger.info("Category changed → %s", label)
        self._log(f"Category: {label}")

        if cat == "music-directors":
            self._log("ℹ️  MD = Music Directors")
        if cat in {"stars", "singers"}:
            self._log("ℹ️  Stars/Singers are currently reliable from FriendsTamilMP3. Other sources are noisy for these categories.")

        if is_top:
            self._clear_albums()
            self._start_fetch_top_songs(cat)
        elif self._active_source:
            self._set_status(f"Category → {label}  |  Reloading {self._active_source.source_name}…")
            self._clear_albums()
            self._start_fetch_albums(self._active_source)
        else:
            self._clear_songs()
            self._active_album = None
            self._set_status(f"Category → {label}  |  Select a source on the left")

    def _on_source_click(self, entry: SourceEntry) -> None:
        self._active_source = entry

        for src, btn in zip(self._sources, self._source_buttons):
            if src.source_name == entry.source_name:
                btn.configure(fg_color="#1f538d")
            else:
                btn.configure(fg_color="transparent")

        cat_label = (_TOP_CAT_LABELS.get(self._active_category)
                     or _CAT_LABELS.get(self._active_category, self._active_category))
        logger.info("Source selected: %s | category: %s", entry.source_name, cat_label)
        self._clear_albums()
        if self._is_top_mode:
            self._start_fetch_top_songs(self._active_category)
        else:
            self._start_fetch_albums(entry)

    # ------------------------------------------------------------------
    # Albums panel
    # ------------------------------------------------------------------

    def _clear_albums(self) -> None:
        self._albums.clear()
        self._album_sources.clear()
        self._albums_lb.delete(0, tk.END)
        self._clear_songs()
        self._active_album = None
        self._update_song_preview(None)

    def _populate_albums(self, rows: List[Tuple[Album, str, str]]) -> None:
        """Rebuild album listbox (must run on main thread)."""
        self._albums = [r[0] for r in rows]
        self._album_sources = {r[0].url: (r[1], r[2]) for r in rows}

        self._albums_lb.delete(0, tk.END)
        for album, src, _ in rows:
            year = album.year_str or "—"
            # Truncate name so columns stay aligned
            name = album.display_name
            if len(name) > 44:
                name = name[:42] + "…"
            text = f"{name:<44}  {year:>4}   [{src[:13]}]"
            self._albums_lb.insert(tk.END, text)

    def _on_album_select(self, _event=None) -> None:
        sel = self._albums_lb.curselection()
        if not sel:
            return
        idx = sel[0]
        if not (0 <= idx < len(self._albums)):
            return
        album = self._albums[idx]
        src_info = self._album_sources.get(album.url, ("IsaiminiHQ", "latest"))
        logger.info("Album selected: %s | source: %s", album.display_name, src_info[0])
        self._active_album = album
        self._clear_songs()
        self._update_song_preview(None)
        self._set_status(f"Loading songs for {album.display_name}…")
        threading.Thread(
            target=self._fetch_songs_worker,
            args=(album, src_info[0]),
            daemon=True,
        ).start()

    # ------------------------------------------------------------------
    # Songs panel
    # ------------------------------------------------------------------

    def _clear_songs(self) -> None:
        self._songs.clear()
        self._song_vars.clear()
        self._selected.clear()
        if self._song_frame:
            for w in self._song_frame.winfo_children():
                w.destroy()
        self._update_song_preview(None)

    def _populate_songs(self, songs: List[Song]) -> None:
        """Rebuild the songs panel (must run on main thread)."""
        self._songs = songs
        self._song_vars = [tk.BooleanVar(value=True) for _ in songs]
        self._selected = set(range(len(songs)))  # all selected by default

        for w in self._song_frame.winfo_children():
            w.destroy()

        for i, song in enumerate(songs):
            if song.is_zip:
                label = f"📦  {song.display_name}"
                color = "#f0c040"
            else:
                size_str = song.size_str or "?"
                album_part = (song.album_title or song.album_name or "—")[:22]
                artist_part = (song.artist or "—")[:18]
                year_part = str(song.year) if song.year else "—"
                label = (
                    f"🎵  {song.display_name[:26]:<26}  "
                    f"{album_part:<22}  {artist_part:<18}  {year_part:<4}  "
                    f"[{song.quality}] {size_str}"
                )
                color = "#e0e0e0"

            cb = ctk.CTkCheckBox(
                self._song_frame,
                text=label,
                variable=self._song_vars[i],
                command=lambda j=i: self._on_song_toggle(j),
                text_color=color,
                font=ctk.CTkFont(family="Consolas", size=11),
                checkbox_height=18,
                checkbox_width=18,
            )
            cb.pack(anchor="w", pady=2, padx=6)
            cb.bind("<Enter>", lambda _e, w=cb: w.configure(fg_color="#2f3d5f"))
            cb.bind("<Leave>", lambda _e, w=cb: w.configure(fg_color="#1f538d"))

        if songs:
            src = self._album_sources.get(self._active_album.url, ("—", "—"))[0] if self._active_album else "—"
            self._update_song_preview(songs[0], src)

    def _on_song_toggle(self, idx: int) -> None:
        if self._song_vars[idx].get():
            self._selected.add(idx)
        else:
            self._selected.discard(idx)
        n = len(self._selected)
        self._set_status(f"{n}/{len(self._songs)} songs selected")
        if 0 <= idx < len(self._songs):
            src = self._album_sources.get(self._active_album.url, ("—", "—"))[0] if self._active_album else "—"
            self._update_song_preview(self._songs[idx], src)

    # ------------------------------------------------------------------
    # Control button handlers
    # ------------------------------------------------------------------

    def _on_select_all(self) -> None:
        if not self._songs:
            return
        self._selected = set(range(len(self._songs)))
        for var in self._song_vars:
            var.set(True)
        self._set_status(f"All {len(self._songs)} songs selected")

    def _on_clear_selection(self) -> None:
        self._selected.clear()
        for var in self._song_vars:
            var.set(False)
        self._set_status("All songs deselected")

    def _on_open_settings(self) -> None:
        win = ctk.CTkToplevel(self)
        win.title("Settings")
        win.geometry("560x360")
        win.grab_set()
        win.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(win, text="Download Folder").grid(row=0, column=0, padx=10, pady=(14, 6), sticky="w")
        out_var = tk.StringVar(value=str(settings.get("download.output_dir", "output")))
        ctk.CTkEntry(win, textvariable=out_var).grid(row=0, column=1, padx=8, pady=(14, 6), sticky="ew")
        ctk.CTkButton(
            win,
            text="Browse",
            width=80,
            command=lambda: out_var.set(filedialog.askdirectory() or out_var.get()),
        ).grid(row=0, column=2, padx=10, pady=(14, 6))

        ctk.CTkLabel(win, text="Max Parallel Downloads").grid(row=1, column=0, padx=10, pady=6, sticky="w")
        workers_var = tk.StringVar(value=str(settings.get("download.max_workers", 3)))
        ctk.CTkEntry(win, textvariable=workers_var).grid(row=1, column=1, padx=8, pady=6, sticky="ew")

        ctk.CTkLabel(win, text="Preferred Source").grid(row=2, column=0, padx=10, pady=6, sticky="w")
        pref_sources = ["", "IsaiminiHQ", "MassTamilan", "FriendsTamilMP3", "KollySongs"]
        pref_var = tk.StringVar(value=str(settings.get("ui.preferred_source", "")))
        ctk.CTkOptionMenu(win, values=pref_sources, variable=pref_var).grid(row=2, column=1, padx=8, pady=6, sticky="ew")

        cache_var = tk.BooleanVar(value=bool(settings.get("ui.cache.enabled", True)))
        ctk.CTkCheckBox(win, text="Enable Cache", variable=cache_var).grid(row=3, column=1, padx=8, pady=6, sticky="w")

        ext_queue_var = tk.BooleanVar(value=bool(settings.get("download.external_downloader.queue_mode", True)))
        ctk.CTkCheckBox(win, text="External Downloader Queue Mode", variable=ext_queue_var).grid(row=4, column=1, padx=8, pady=6, sticky="w")

        dedupe_var = tk.StringVar(value=str(settings.get("ui.dedupe.strategy", "smaller-size")))
        ctk.CTkLabel(win, text="Duplicate Strategy").grid(row=5, column=0, padx=10, pady=6, sticky="w")
        ctk.CTkOptionMenu(win, values=["first", "smaller-size"], variable=dedupe_var).grid(row=5, column=1, padx=8, pady=6, sticky="ew")

        def _save() -> None:
            try:
                settings.set("download.output_dir", out_var.get().strip() or "output")
                settings.set("download.max_workers", max(1, int(workers_var.get().strip() or "3")))
                settings.set("ui.preferred_source", pref_var.get().strip())
                settings.set("ui.cache.enabled", bool(cache_var.get()))
                settings.set("download.external_downloader.queue_mode", bool(ext_queue_var.get()))
                settings.set("ui.dedupe.strategy", dedupe_var.get().strip())

                self._cache_enabled = bool(settings.get("ui.cache.enabled", True))
                self._dedupe_strategy = str(settings.get("ui.dedupe.strategy", "smaller-size"))
                self._downloader.max_workers = int(settings.get("download.max_workers", 3))
                self._log("✓  Settings saved")
                win.destroy()
            except Exception as exc:
                messagebox.showerror("Settings", f"Failed to save settings:\n{exc}")

        ctk.CTkButton(win, text="Save", command=_save).grid(row=6, column=1, padx=8, pady=(12, 10), sticky="e")
        ctk.CTkButton(win, text="Cancel", command=win.destroy).grid(row=6, column=2, padx=10, pady=(12, 10), sticky="e")

    def _on_load_more(self) -> None:
        if self._is_top_mode:
            self._log("ℹ️  Re-running aggregation with same settings…")
            self._clear_albums()
            self._start_fetch_top_songs(self._active_category)
            return
        if not self._active_source:
            self._log("⚠  Select a source first")
            return
        key = (self._active_source.source_name, self._active_category)
        current = self._source_pages.get(key, 5)
        self._source_pages[key] = current + 5
        self._log(f"Load more: now fetching {self._source_pages[key]} pages…")
        self._clear_albums()
        self._start_fetch_albums(self._active_source)

    def _on_reload(self) -> None:
        if self._is_top_mode:
            self._clear_albums()
            self._start_fetch_top_songs(self._active_category)
            return
        if not self._active_source:
            self._log("⚠  Select a source first")
            return
        self._clear_albums()
        self._start_fetch_albums(self._active_source)

    def _on_search(self) -> None:
        keyword = self._search_var.get().strip()
        if not keyword:
            return
        # Clear stale songs immediately so the right panel never shows old data
        token = self._next_load_token()
        self._clear_albums()
        self._clear_songs()
        self._active_album = None
        self._log(f"Searching for: '{keyword}'…")
        threading.Thread(
            target=self._search_worker, args=(keyword, token), daemon=True
        ).start()

    def _on_download(self) -> None:
        if not self._songs:
            self._log("⚠  No songs loaded — select an album first")
            return
        if self._is_downloading:
            self._log("⚠  Download already running")
            return
        if not self._selected:
            self._log("⚠  No songs selected — click 'Select All' or toggle individual tracks")
            return
        if not self._active_album:
            self._log("⚠  No album active")
            return
        self._cancel_download_requested = False
        selection = [self._songs[i] for i in sorted(self._selected)]
        threading.Thread(
            target=self._download_worker,
            args=(selection, self._active_album),
            daemon=True,
        ).start()

    def _on_cancel_download(self) -> None:
        if not self._is_downloading:
            self._log("ℹ  No active download to cancel")
            return
        self._cancel_download_requested = True
        self._log("⏹  Cancel requested. Stopping after current file…")
        self._queue_add("⏹ cancel requested")

    def _on_retry_failed(self) -> None:
        if self._is_downloading:
            self._log("⚠  Wait for current download to finish")
            return
        if not self._last_failed_songs:
            self._log("ℹ  No failed songs to retry")
            return
        if not self._active_album:
            self._log("⚠  No active album for retry")
            return
        self._cancel_download_requested = False
        retry_list = list(self._last_failed_songs)
        self._log(f"↻  Retrying {len(retry_list)} failed song(s)…")
        threading.Thread(
            target=self._download_worker,
            args=(retry_list, self._active_album),
            daemon=True,
        ).start()

    def _on_clear_cache(self) -> None:
        try:
            if self._cache_dir.exists():
                removed = 0
                for p in self._cache_dir.glob("*.json"):
                    p.unlink(missing_ok=True)
                    removed += 1
                self._log(f"🧹  Cache cleared ({removed} file(s))")
            else:
                self._log("ℹ  Cache directory not found")
            self._cache_hits = 0
            self._cache_misses = 0
            self._cache_bypasses = 0
            self._cache_expired = 0
            self._cache_errors = 0
            self._refresh_cache_stats()
        except Exception as exc:
            self._log(f"✗  Failed to clear cache: {exc}")

    # ------------------------------------------------------------------
    # Scraper helpers
    # ------------------------------------------------------------------

    def _create_scraper(self, source_name: str) -> BaseScraper:
        url = self._source_urls.get(source_name, "")
        if source_name == "IsaiminiHQ":
            return IsaiminiScraper(url)
        elif source_name == "MassTamilan":
            return MassTamilanScraper(url)
        elif source_name == "KollySongs":
            return KollySongsScraper(url)
        else:
            return FriendsTamilMP3Scraper(url)

    def _scrape_albums(
        self,
        source_name: str,
        category: str,
        max_pages: int,
        flow_start: float,
    ) -> List[Album]:
        scraper = self._create_scraper(source_name)
        try:
            try:
                scraper._init_browser()
            except Exception:
                pass

            def progress_cb(current_page: int, total_pages: int) -> None:
                elapsed = perf_counter() - flow_start
                self.after(
                    0,
                    lambda cp=current_page, tp=total_pages, t=elapsed: (
                        self._set_status(
                            f"{source_name}  page {cp}/{tp}  ·  {t:.1f}s"
                        )
                    ),
                )

            return scraper.get_albums(
                category=category,
                max_pages=max_pages,
                progress_cb=progress_cb,
            )
        finally:
            try:
                scraper._close_browser()
            except Exception:
                pass

    @staticmethod
    def _sort_album_rows(
        rows: List[Tuple[Album, str, str]]
    ) -> List[Tuple[Album, str, str]]:
        return sorted(
            rows,
            key=lambda r: (r[0].year or 0, r[0].display_name.lower()),
            reverse=True,
        )

    # ------------------------------------------------------------------
    # Worker threads
    # ------------------------------------------------------------------

    def _start_fetch_albums(self, entry: SourceEntry) -> None:
        """Launch album-fetch worker thread."""
        category = self._active_category
        pages = self._source_pages.get((entry.source_name, category), 5)
        token = self._next_load_token()
        threading.Thread(
            target=self._fetch_albums_worker,
            args=(entry, category, pages, token),
            daemon=True,
        ).start()

    def _fetch_albums_worker(
        self, entry: SourceEntry, category: str, pages: int, token: int
    ) -> None:
        if not self._is_load_active(token):
            return
        started = perf_counter()
        label_cat = _CAT_LABELS.get(category, category)
        cache_file = self._cache_path("albums", entry.source_name, category, str(pages))
        allow_cache = self._cache_allowed("albums", category)
        if not allow_cache:
            self._cache_mark_bypass()

        cached = self._cache_get(cache_file) if allow_cache else None
        if cached and self._is_load_active(token):
            try:
                rows_payload = cached.get("rows", [])
                rows: List[Tuple[Album, str, str]] = []
                for item in rows_payload:
                    rows.append((self._album_from_dict(item[0]), item[1], item[2]))
                self.after(0, lambda r=rows: self._populate_albums(r))
                self.after(0, lambda n=len(rows): self._set_status(f"{n} albums (cache)  ·  {self._cache_stats_text()}"))
                self.after(0, lambda: self._set_loading(False))
                self.after(0, lambda: self._log(f"⚡ Loaded {len(rows)} albums from cache  ·  {self._cache_stats_text()}"))
                return
            except Exception:
                pass
        logger.info(
            "Fetch albums: source=%s category=%s pages=%d",
            entry.source_name, label_cat, pages,
        )
        self.after(0, lambda: self._set_loading(True))
        self.after(
            0,
            lambda: self._log(f"Loading albums:  {entry.source_name}  ·  {label_cat}…"),
        )

        all_rows: List[Tuple[Album, str, str]] = []

        if entry.source_name == "All Sources":
            # Route to the correct subset of sources
            if category in _FTP3_ONLY:
                source_names = ["FriendsTamilMP3"]
            elif category == "music-directors":
                source_names = ["FriendsTamilMP3", "KollySongs"]
            elif category == "old":
                # Old = FTP3 old collections + year-based pull from Isaimini/KollySongs.
                # `pages` acts as the depth budget for how many years to scan.
                years = [str(y) for y in range(2020, 2004, -1)]
                years_to_scan = years[:max(3, min(pages, len(years)))]

                old_rows: List[Tuple[Album, str, str]] = []

                # 1) Native FTP3 old collections
                try:
                    ftp3_albums = self._scrape_albums("FriendsTamilMP3", "old", pages, started)
                    old_rows.extend((a, "FriendsTamilMP3", category) for a in ftp3_albums)
                    self.after(0, lambda n=len(ftp3_albums): self._log(f"✓  FriendsTamilMP3(old): {n} albums"))
                except Exception as exc:
                    self.after(0, lambda e=exc: self._log(f"✗  FriendsTamilMP3(old): {e}"))

                # 2) Year-mapped old albums from Isaimini + KollySongs
                for src in ("IsaiminiHQ", "KollySongs"):
                    src_count = 0
                    for y in years_to_scan:
                        try:
                            y_albums = self._scrape_albums(src, y, 1, started)
                            src_count += len(y_albums)
                            old_rows.extend((a, src, category) for a in y_albums)
                        except Exception:
                            continue
                    self.after(0, lambda s=src, n=src_count, ys=years_to_scan:
                               self._log(f"✓  {s}(old via years {ys[-1]}-{ys[0]}): {n} albums"))

                # Deduplicate by album URL
                dedup: Dict[str, Tuple[Album, str, str]] = {}
                for row in old_rows:
                    dedup[row[0].url] = row
                all_rows = list(dedup.values())
                sorted_rows = self._sort_album_rows(all_rows)
                elapsed = perf_counter() - started
                if self._is_load_active(token):
                    self.after(0, lambda r=sorted_rows: self._populate_albums(r))
                self.after(0, lambda: self._set_loading(False))
                self.after(0, lambda n=len(sorted_rows), t=elapsed:
                           self._set_status(f"{n} albums loaded  ·  {t:.1f}s"))
                if allow_cache:
                    self._cache_set(
                        cache_file,
                        {
                            "rows": [
                                [self._album_to_dict(a), s, c]
                                for (a, s, c) in sorted_rows
                            ]
                        },
                    )
                return
            else:
                source_names = self._ordered_sources(["IsaiminiHQ", "MassTamilan", "KollySongs"])

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
                        self.after(
                            0,
                            lambda s=src, e=exc: self._log(f"✗  {s}: {e}"),
                        )
                        continue

                    all_rows.extend((a, src, category) for a in albums)
                    sorted_rows = self._sort_album_rows(all_rows)
                    elapsed = perf_counter() - started

                    if self._is_load_active(token):
                        self.after(0, lambda r=sorted_rows: self._populate_albums(r))
                    self.after(
                        0,
                        lambda s=src, n=len(albums), t=elapsed: (
                            self._log(f"✓  {s}: {n} albums  ·  {t:.1f}s")
                        ),
                    )
                    self.after(
                        0,
                        lambda n=len(sorted_rows), t=elapsed: (
                            self._set_status(f"Loaded {n} albums so far  ·  {t:.1f}s")
                        ),
                    )

            elapsed = perf_counter() - started
            n_total = len(all_rows)
            if self._is_load_active(token):
                self.after(0, lambda: self._set_loading(False))
                self.after(
                    0,
                    lambda n=n_total, t=elapsed: (
                        self._set_status(f"{n} albums total  ·  {t:.1f}s")
                    ),
                )
            if allow_cache:
                self._cache_set(
                    cache_file,
                    {
                        "rows": [
                            [self._album_to_dict(a), s, c]
                            for (a, s, c) in self._sort_album_rows(all_rows)
                        ]
                    },
                )

        else:
            # Single source
            try:
                if category == "old" and entry.source_name in {"IsaiminiHQ", "KollySongs"}:
                    years = [str(y) for y in range(2020, 2004, -1)]
                    years_to_scan = years[:max(3, min(pages, len(years)))]
                    albums = []
                    seen_urls: Set[str] = set()
                    for y in years_to_scan:
                        y_albums = self._scrape_albums(entry.source_name, y, 1, started)
                        for a in y_albums:
                            if a.url not in seen_urls:
                                seen_urls.add(a.url)
                                albums.append(a)
                else:
                    albums = self._scrape_albums(
                        entry.source_name, category, pages, started
                    )
                all_rows = [(a, entry.source_name, category) for a in albums]
            except Exception as exc:
                elapsed = perf_counter() - started
                self.after(0, lambda e=exc: self._log(f"✗  Error loading albums: {e}"))
                self.after(0, lambda: self._set_status("Error loading albums"))
                self.after(0, lambda: self._set_loading(False))
                return

            elapsed = perf_counter() - started
            sorted_rows = self._sort_album_rows(all_rows)
            if self._is_load_active(token):
                self.after(0, lambda r=sorted_rows: self._populate_albums(r))
            self.after(
                0,
                lambda n=len(sorted_rows), s=entry.source_name, t=elapsed: (
                    self._log(f"✓  {s}: {n} albums  ·  {t:.1f}s")
                ),
            )
            if self._is_load_active(token):
                self.after(
                    0,
                    lambda n=len(sorted_rows), t=elapsed: (
                        self._set_status(f"{n} albums loaded  ·  {t:.1f}s")
                    ),
                )
                self.after(0, lambda: self._set_loading(False))
            if allow_cache:
                self._cache_set(
                    cache_file,
                    {
                        "rows": [
                            [self._album_to_dict(a), s, c]
                            for (a, s, c) in sorted_rows
                        ]
                    },
                )

    def _fetch_songs_worker(self, album: Album, source_name: str) -> None:
        started = perf_counter()
        logger.info("Fetch songs: album=%s source=%s", album.display_name, source_name)
        cache_file = self._cache_path("songs", source_name, album.url)
        cached = self._cache_get(cache_file)
        if cached:
            try:
                songs = [self._song_from_dict(x) for x in cached.get("songs", [])]
                if songs:
                    elapsed = perf_counter() - started
                    self.after(0, lambda s=songs: self._populate_songs(s))
                    self.after(0, lambda n=len(songs), t=elapsed: self._set_status(f"{n} songs (cache) · {t:.1f}s  ·  {self._cache_stats_text()}"))
                    self.after(0, lambda n=len(songs): self._log(f"⚡ {album.display_name}: {n} song(s) loaded from cache  ·  {self._cache_stats_text()}"))
                    return
            except Exception:
                pass
        scraper = self._create_scraper(source_name)
        try:
            try:
                scraper._init_browser()
            except Exception:
                pass
            songs = scraper.get_songs(album)
        except Exception as exc:
            self.after(0, lambda e=exc: self._log(f"✗  Error loading songs: {e}"))
            self.after(0, lambda: self._set_status("Error loading songs"))
            return
        finally:
            try:
                scraper._close_browser()
            except Exception:
                pass

        elapsed = perf_counter() - started
        logger.info("Songs loaded: %d songs · %.1fs", len(songs), elapsed)

        mp3_count = sum(1 for s in songs if not s.is_zip)
        zip_count = sum(1 for s in songs if s.is_zip)

        self.after(0, lambda s=songs: self._populate_songs(s))
        self.after(
            0,
            lambda n=mp3_count, z=zip_count, t=elapsed, nm=album.display_name: (
                self._log(
                    f"✓  {nm}:  {n} song(s)"
                    + (f"  +  {z} zip" if z else "")
                    + f"  ·  {t:.1f}s"
                )
            ),
        )
        self.after(
            0,
            lambda n=len(songs), t=elapsed: (
                self._set_status(f"{n} songs loaded  ·  {t:.1f}s")
            ),
        )
        if songs:
            self._cache_set(
                cache_file,
                {"songs": [self._song_to_dict(s) for s in songs]},
            )

    # ------------------------------------------------------------------
    # Top Songs  (aggregated from hits collections)
    # ------------------------------------------------------------------

    def _show_top_albums_entry(self, text: str) -> None:
        """Fill the albums listbox with a single informational line (top-songs mode)."""
        self._albums_lb.delete(0, tk.END)
        self._albums_lb.insert(tk.END, text)

    def _start_fetch_top_songs(self, category: str) -> None:
        """Launch the top-songs aggregator in a daemon thread."""
        token = self._next_load_token()
        self._set_status(
            f"Aggregating {_TOP_CAT_LABELS.get(category, category)}…"
        )
        threading.Thread(
            target=self._fetch_top_songs_worker,
            args=(category, token),
            daemon=True,
        ).start()

    def _fetch_top_songs_worker(self, category: str, token: int) -> None:
        """Collect hit songs from multiple sources, dedup, then populate songs panel."""
        if not self._is_load_active(token):
            return
        started = perf_counter()
        label = _TOP_CAT_LABELS.get(category, category)
        year_min, year_max = _TOP_CAT_YEAR_RANGE.get(category, (None, None))
        cache_file = self._cache_path("top", category)
        allow_cache = self._cache_allowed("top", category)
        if not allow_cache:
            self._cache_mark_bypass()

        cached = self._cache_get(cache_file) if allow_cache else None
        if cached and self._is_load_active(token):
            try:
                cached_songs = [self._song_from_dict(x) for x in cached.get("songs", [])]
                cached_n_albums = int(cached.get("albums", 0))
                self._active_album = Album(
                    name=f"{label} — {len(cached_songs)} songs from {cached_n_albums} albums",
                    url=f"top-songs-synthetic:{category}",
                )
                self.after(0, lambda s=cached_songs: self._populate_songs(s))
                self.after(0, lambda n=len(cached_songs), a=cached_n_albums: self._show_top_albums_entry(f"⚡  {label} — {n} songs / {a} albums (cache)"))
                self.after(0, lambda n=len(cached_songs), a=cached_n_albums: self._set_status(f"{n} songs · {a} albums (cache)  ·  {self._cache_stats_text()}"))
                self.after(0, lambda lb=label: self._log(f"⚡  {lb} loaded from cache  ·  {self._cache_stats_text()}"))
                self.after(0, lambda: self._set_loading(False))
                return
            except Exception:
                pass

        self.after(0, lambda lb=label: self._set_loading(True, f"⏳  {lb}: collecting albums…"))
        self.after(0, lambda lb=label: self._log(f"🎯  Aggregating {lb}…"))
        self.after(0, lambda: self._set_activity_progress(True, 0, 1))

        # ── Step 1: collect (album, source_name) pairs ────────────────
        album_src_pairs: List[Tuple[Album, str]] = []
        album_contrib: Dict[str, int] = {}
        song_contrib: Dict[str, int] = {}
        failed_parts: List[str] = []
        succeeded_parts: Set[str] = set()

        if category == "top-songs":
            # All-time hits: FTP3 singer / MD / star collections
            for ftp3_cat in ("singers", "music-directors", "stars"):
                try:
                    albums = self._scrape_albums("FriendsTamilMP3", ftp3_cat, 5, started)
                    album_src_pairs.extend((a, "FriendsTamilMP3") for a in albums)
                    album_contrib["FriendsTamilMP3"] = album_contrib.get("FriendsTamilMP3", 0) + len(albums)
                    succeeded_parts.add(f"FriendsTamilMP3/{ftp3_cat}")
                    elapsed = perf_counter() - started
                    self.after(0, lambda n=len(albums), c=ftp3_cat, t=elapsed:
                               self._log(f"  {c}: {n} albums  ·  {t:.1f}s"))
                except Exception as exc:
                    logger.warning("Top songs: load error [%s]: %s", ftp3_cat, exc)
                    failed_parts.append(f"FriendsTamilMP3/{ftp3_cat}: {exc}")

        elif year_min is not None and year_min == year_max:
            # Single year: recent era from Isaimini + MassTamilan + KollySongs
            # Keep a higher cap so top-year lists are meaningfully broad.
            year_cat = str(year_min)
            for src in ("IsaiminiHQ", "MassTamilan", "KollySongs"):
                try:
                    albums = self._scrape_albums(src, year_cat, 4, started)
                    album_src_pairs.extend((a, src) for a in albums)
                    album_contrib[src] = album_contrib.get(src, 0) + len(albums)
                    succeeded_parts.add(src)
                    elapsed = perf_counter() - started
                    self.after(0, lambda n=len(albums), s=src, t=elapsed:
                               self._log(f"  {s}: {n} albums  ·  {t:.1f}s"))
                except Exception as exc:
                    logger.warning("Top songs %s: error from %s: %s", year_cat, src, exc)
                    failed_parts.append(f"{src}: {exc}")
            album_src_pairs = album_src_pairs[:45]

        else:
            # Decade range: fetch each year individually from IsaiminiHQ + KollySongs.
            # This significantly improves coverage versus a single source.
            years_in_range = list(range(year_min, year_max + 1))
            self.after(0, lambda yr=years_in_range:
                       self._log(f"  Fetching years: {yr[0]}–{yr[-1]} from IsaiminiHQ + KollySongs…"))
            for yr in years_in_range:
                for src in ("IsaiminiHQ", "KollySongs"):
                    try:
                        yr_albums = self._scrape_albums(src, str(yr), 2, started)
                        album_src_pairs.extend((a, src) for a in yr_albums)
                        album_contrib[src] = album_contrib.get(src, 0) + len(yr_albums)
                        succeeded_parts.add(f"{src}/{yr}")
                        elapsed = perf_counter() - started
                        self.after(0, lambda n=len(yr_albums), y=yr, s=src, t=elapsed:
                                   self._log(f"  {s} {y}: {n} albums  ·  {t:.1f}s"))
                    except Exception as exc:
                        logger.warning("Top songs decade %d: error from %s: %s", yr, src, exc)
                        failed_parts.append(f"{src}/{yr}: {exc}")
            # Cap to avoid an overly long song-fetch phase
            album_src_pairs = album_src_pairs[:60]

        # Deduplicate albums by URL before song fetch.
        dedup_album_pairs: List[Tuple[Album, str]] = []
        seen_album_urls: Set[str] = set()
        for alb, src in album_src_pairs:
            if alb.url in seen_album_urls:
                continue
            seen_album_urls.add(alb.url)
            dedup_album_pairs.append((alb, src))
        album_src_pairs = dedup_album_pairs

        n_albums = len(album_src_pairs)
        if n_albums == 0:
            self.after(0, lambda lb=label: self._log(f"⚠  No albums found for {lb}"))
            self.after(0, lambda: self._set_loading(False))
            self.after(0, lambda: self._set_activity_progress(False))
            self.after(0, lambda: self._set_status("No albums found"))
            if failed_parts:
                self.after(
                    0,
                    lambda lb=label, fails="\n".join(failed_parts[:5]): messagebox.showerror(
                        "Source Errors",
                        f"No albums found for '{lb}'.\n\nFailed:\n{fails}",
                    ),
                )
            else:
                self.after(
                    0,
                    lambda lb=label: messagebox.showwarning(
                        "No Results",
                        f"No albums found for '{lb}'.\n\nTry a different filter or source.",
                    ),
                )
            return

        self.after(0, lambda n=n_albums, lb=label: (
            self._show_top_albums_entry(f"⏳  {lb}  —  loading songs from {n} albums…"),
            self._set_status(f"Fetching songs from {n} albums…"),
        ))
        self.after(0, lambda t=n_albums: self._set_activity_progress(True, 0, max(1, t)))

        # ── Step 2: fetch songs for every album in parallel ───────────
        all_songs: List[Song] = []
        songs_lock = threading.Lock()
        completed_count: List[int] = [0]
        plateau_window: int = (
            self._top_adaptive_window_small
            if n_albums <= self._top_adaptive_large_cutoff
            else self._top_adaptive_window_large
        )
        plateau_checks: int = 0
        plateau_streak: int = 0
        unique_seen: Set[str] = set()
        unique_at_last_check: int = 0
        stop_adaptive: bool = False

        def _fetch_for_album(pair: Tuple[Album, str]) -> Tuple[List[Song], str]:
            alb, src_name = pair
            scraper = self._create_scraper(src_name)
            fetched: List[Song] = []
            try:
                try:
                    scraper._init_browser()
                except Exception:
                    pass
                fetched = scraper.get_songs(alb)
                # Pre-assign album context so download organises by artist/album folder
                for s in fetched:
                    if not s.album_name:
                        s.album_name = alb.safe_dirname
                    if not s.year and alb.year:
                        s.year = alb.year
            except Exception as exc:
                logger.warning("Top songs get_songs [%s]: %s", alb.display_name, exc)
            finally:
                try:
                    scraper._close_browser()
                except Exception:
                    pass
            return fetched, src_name

        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(_fetch_for_album, pair) for pair in album_src_pairs]
            for fut in as_completed(futures):
                try:
                    fetched, src_name = fut.result()
                except Exception as exc:
                    logger.warning("Top songs worker future error: %s", exc)
                    continue
                with songs_lock:
                    all_songs.extend(fetched)
                    song_contrib[src_name] = song_contrib.get(src_name, 0) + len(fetched)
                    for s in fetched:
                        norm = re.sub(r"[^a-z0-9]", "", s.display_name.lower())
                        if norm:
                            unique_seen.add(norm)
                    completed_count[0] += 1
                    c, t, n, u = completed_count[0], n_albums, len(all_songs), len(unique_seen)
                    if self._is_load_active(token):
                        self.after(0, lambda c=c, t=t, n=n, u=u, lb=label: (
                            self._set_status(f"Loading songs: {c}/{t} albums  ·  {n} found  ·  {u} unique"),
                            self._set_loading(True, f"⏳  {lb}: loading songs {c}/{t}  ·  found {n} ({u} unique)"),
                            self._show_top_albums_entry(f"⏳  {lb}  —  loading songs: {c}/{t} albums  ·  {n} found ({u} unique)"),
                            self._set_activity_progress(True, c, t),
                        ))

                    if (
                        self._top_adaptive_enabled
                        and n_albums >= self._top_adaptive_min_albums
                        and c >= (plateau_window * 2)
                        and c % plateau_window == 0
                    ):
                        plateau_checks += 1
                        growth = u - unique_at_last_check
                        unique_at_last_check = u
                        if growth <= self._top_adaptive_plateau_growth:
                            plateau_streak += 1
                        else:
                            plateau_streak = 0
                        if plateau_streak >= self._top_adaptive_plateau_streak:
                            stop_adaptive = True
                            cancelled = 0
                            for pending in futures:
                                if not pending.done() and pending.cancel():
                                    cancelled += 1
                            self.after(
                                0,
                                lambda c=c, t=t, u=u, g=growth, x=cancelled, w=plateau_window, lb=label, cfg=self._top_adaptive_plateau_growth:
                                    self._log(
                                        f"ℹ  {lb}: adaptive stop after {c}/{t} albums "
                                        f"(window={w}, growth={g}, threshold<={cfg}, unique={u}, cancelled={x})"
                                    ),
                            )
                            break

        elapsed = perf_counter() - started

        # ── Step 3: dedup + sort alphabetically ───────────────────────
        deduped = _dedup_songs(all_songs, strategy=self._dedupe_strategy)
        deduped.sort(key=lambda s: s.display_name.lower())
        n_songs = len(deduped)

        # Source contribution summary
        contrib_keys = sorted(set(album_contrib.keys()) | set(song_contrib.keys()))
        for src in contrib_keys:
            self.after(
                0,
                lambda s=src, a=album_contrib.get(src, 0), n=song_contrib.get(src, 0):
                    self._log(f"  Source contribution: {s}  albums={a}  songs={n}"),
            )

        # Show partial-failure details only when we still have successful data.
        if failed_parts and n_albums > 0:
            success_line = ", ".join(sorted(succeeded_parts)[:6]) or "(none)"
            fail_line = "\n".join(failed_parts[:6])
            self.after(
                0,
                lambda ok=success_line, bad=fail_line: messagebox.showwarning(
                    "Partial Source Failure",
                    f"Some sources/parts failed but results are available.\n\nSucceeded:\n{ok}\n\nFailed:\n{bad}",
                ),
            )

        if n_songs == 0:
            self.after(0, lambda lb=label: self._log(f"⚠  No songs returned for {lb}"))
            self.after(0, lambda: self._set_loading(False))
            self.after(0, lambda: self._set_activity_progress(False))
            self.after(
                0,
                lambda lb=label, n=n_albums: messagebox.showwarning(
                    "No Songs Found",
                    f"Fetched {n} album(s) for '{lb}' but got 0 songs.\n"
                    "The albums may have changed or require login.",
                ),
            )
            return

        if stop_adaptive:
            self.after(0, lambda pc=plateau_checks, ps=plateau_streak: self._log(
                f"ℹ  Adaptive top-loading enabled: plateau checks={pc}, plateau streak={ps}"
            ))

        # ── Step 4: synthetic album + populate UI ─────────────────────
        self._active_album = Album(
            name=f"{label} — {n_songs} songs from {n_albums} albums",
            url=f"top-songs-synthetic:{category}",
        )

        def _show() -> None:
            if not self._is_load_active(token):
                return
            self._populate_songs(deduped)
            self._show_top_albums_entry(
                f"🎯  {label}  —  {n_songs} songs / {n_albums} albums  ·  {elapsed:.0f}s"
            )
            self._set_loading(False)
            self._set_activity_progress(False)
            self._log(
                f"✓  {label}: {n_songs} unique songs from {n_albums} albums  ·  {elapsed:.1f}s"
            )
            self._set_status(f"{n_songs} songs · {n_albums} albums · {elapsed:.1f}s")
            if allow_cache:
                self._cache_set(
                    cache_file,
                    {
                        "albums": n_albums,
                        "songs": [self._song_to_dict(s) for s in deduped],
                    },
                )

        self.after(0, _show)

    def _search_worker(self, keyword: str, token: int) -> None:
        if not self._is_load_active(token):
            return
        started = perf_counter()
        category = "latest"
        max_pages = 8
        threshold = 0.50  # must reach word-boundary (0.85), substring (0.55) or fuzzy (0.50)
        cache_file = self._cache_path("search", keyword.lower())

        cached = self._cache_get(cache_file)
        if cached and self._is_load_active(token):
            try:
                hits = [
                    (
                        self._album_from_dict(h[0]),
                        h[1],
                        h[2],
                        float(h[3]),
                    )
                    for h in cached.get("hits", [])
                ]
                elapsed = perf_counter() - started

                def _show_cached() -> None:
                    if not self._is_load_active(token):
                        return
                    self._albums = [h[0] for h in hits]
                    self._album_sources = {h[0].url: (h[1], h[2]) for h in hits}
                    self._albums_lb.delete(0, tk.END)
                    for album, src, _, score in hits:
                        pct = int(score * 100)
                        year = album.year_str or "—"
                        name = album.display_name
                        if len(name) > 40:
                            name = name[:38] + "…"
                        text = f"[{pct:3d}%]  {name:<41}  {year}   [{src[:13]}]"
                        self._albums_lb.insert(tk.END, text)
                    self._log(f"⚡  Search cache: {len(hits)} results for '{keyword}'  ·  {self._cache_stats_text()}")
                    self._set_status(f"Search: {len(hits)} results (cache)  ·  {self._cache_stats_text()}")

                self.after(0, _show_cached)
                return
            except Exception:
                pass

        self.after(
            0,
            lambda: self._set_status(f"Searching for '{keyword}' across all sources…"),
        )

        hits: List[Tuple[Album, str, str, float]] = []
        source_names = self._ordered_sources(["IsaiminiHQ", "MassTamilan", "FriendsTamilMP3", "KollySongs"])

        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {
                pool.submit(self._scrape_albums, src, category, max_pages, started): src
                for src in source_names
            }
            for future in as_completed(futures):
                src = futures[future]
                try:
                    albums = future.result()
                except Exception as exc:
                    logger.warning("Search %s error: %s", src, exc)
                    continue

                for album in albums:
                    score = _search_score(keyword, album.display_name)
                    if score >= threshold:
                        hits.append((album, src, category, score))

                elapsed = perf_counter() - started
                self.after(
                    0,
                    lambda s=src, n=len(albums), t=elapsed: (
                        self._log(f"  {s}: {n} albums scanned  ·  {t:.1f}s")
                    ),
                )

        hits.sort(key=lambda x: (x[3], x[0].year or 0), reverse=True)
        elapsed = perf_counter() - started

        if not hits:
            self.after(0, lambda: self._log("⚠  No matches found — try broader keywords"))
            self.after(
                0,
                lambda t=elapsed: self._set_status(f"No results for '{keyword}'  ·  {t:.1f}s"),
            )
            return

        def _show_hits() -> None:
            if not self._is_load_active(token):
                return
            self._albums = [h[0] for h in hits]
            self._album_sources = {h[0].url: (h[1], h[2]) for h in hits}
            self._albums_lb.delete(0, tk.END)
            for album, src, _, score in hits:
                pct = int(score * 100)
                year = album.year_str or "—"
                name = album.display_name
                if len(name) > 40:
                    name = name[:38] + "…"
                text = f"[{pct:3d}%]  {name:<41}  {year}   [{src[:13]}]"
                self._albums_lb.insert(tk.END, text)
            n_hits = len(hits)
            self._log(f"✓  {n_hits} match(es) for '{keyword}'  ·  {elapsed:.1f}s")
            self._set_status(f"Search: {n_hits} results  ·  {elapsed:.1f}s")
            self._cache_set(
                cache_file,
                {
                    "hits": [
                        [self._album_to_dict(a), s, c, sc]
                        for (a, s, c, sc) in hits
                    ]
                },
            )

        self.after(0, _show_hits)

    def _download_worker(self, songs: List[Song], album: Album) -> None:
        started = perf_counter()

        # MP3-only mode — skip ZIP entries
        mp3_songs = [s for s in songs if not s.is_zip]
        skipped_zip = len(songs) - len(mp3_songs)
        if skipped_zip:
            self.after(
                0,
                lambda n=skipped_zip: self._log(
                    f"  Skipped {n} ZIP entry(ies)  (MP3-only mode)"
                ),
            )

        songs = mp3_songs
        if not songs:
            self.after(0, lambda: self._log("⚠  Nothing to download (no MP3 entries selected)"))
            return

        self._is_downloading = True
        self._last_failed_songs = []

        total = len(songs)
        logger.info("Download started: %s — %d song(s)", album.display_name, total)

        self.after(0, lambda: self._progress_bar.grid())
        self.after(0, lambda: self._progress_bar.set(0))
        self.after(
            0,
            lambda n=total: self._log(
                f"⬇  Download started:  {album.display_name}  —  {n} file(s)"
            ),
        )
        self.after(0, lambda: self._set_status(f"Downloading {album.display_name}…"))
        self.after(0, lambda n=total: self._queue_add(f"Queue start: {n} item(s)"))

        # Attach metadata for ID3 tagging / path organization
        # Top-songs synthetic albums: preserve per-song album_name from scraping
        is_top = album.url.startswith("top-songs-synthetic:")
        mp3_n = 0
        for s in songs:
            if not is_top:
                s.album_name = album.safe_dirname
                s.album_title = album.display_name
                s.year = album.year
            else:
                # Only fill blanks — keep artist-hits folder name from scraper
                s.album_name = s.album_name or album.safe_dirname
                s.album_title = s.album_title or album.display_name
            s.artist = s.artist or "Unknown Artist"
            if s.is_zip or is_top:
                s.track_number = None
            else:
                mp3_n += 1
                s.track_number = mp3_n

        self._downloader.output_dir = settings.output_dir
        ok_count = 0
        fail_count = 0
        aria2_exe = self._aria2_executable()
        use_external = aria2_exe is not None
        year = album.year

        if use_external:
            self.after(0, lambda a=aria2_exe: self._log(f"⬇  External downloader mode: {a}"))

        queue_mode = bool(settings.get("download.external_downloader.queue_mode", True))
        if use_external and queue_mode:
            pending_entries: List[Tuple[Song, Path]] = []
            for i, song in enumerate(songs):
                out_dir = self._song_output_dir(song, album, is_top, year)
                existing = self._find_existing_in_dir(song, out_dir)
                if existing is not None:
                    ok_count += 1
                    self.after(0, lambda n=song.display_name: self._queue_add(f"✓ skip  {n[:48]}"))
                    self.after(0, lambda n=song.display_name: self._log(f"  ✓  skipped (already downloaded):  {n[:55]}"))
                    self.after(0, lambda p=(i + 1) / total: self._progress_bar.set(p))
                    continue
                pending_entries.append((song, out_dir))

            if pending_entries:
                try:
                    queue_file = self._build_aria2_queue_file(pending_entries)
                    launched = self._launch_aria2_batch(aria2_exe, queue_file)
                    if launched:
                        ok_count += len(pending_entries)
                        self.after(0, lambda n=len(pending_entries): self._queue_add(f"↗ launched queue  {n} item(s)"))
                        self.after(0, lambda q=queue_file: self._log(f"  ℹ  aria2 queue file: {q}"))
                        self.after(0, lambda: self._progress_bar.set(1.0))
                except Exception as exc:
                    fail_count += len(pending_entries)
                    self.after(0, lambda e=exc: self._log(f"  ✗  external queue launch failed — {e}"))
                    self.after(0, lambda n=len(pending_entries): self._queue_add(f"✗ queue failed  {n} item(s)"))

            total_elapsed = perf_counter() - started
            out_path = settings.output_dir if is_top else (settings.output_dir / str(year) / album.safe_dirname if year else settings.output_dir / album.safe_dirname)

            def _finish_external_queue() -> None:
                self._progress_bar.set(1.0)
                self.after(800, lambda: self._progress_bar.grid_remove())
                summary = f"✓ {ok_count} queued"
                if fail_count:
                    summary += f"  ✗ {fail_count} failed"
                self._log(f"Download complete!  {summary}  ({total_elapsed:.1f}s total)")
                self._log(f"📁  Saved to:  {out_path}")
                self._set_status(
                    f"Done — {ok_count} queued"
                    + (f", {fail_count} failed" if fail_count else "")
                    + f"  ·  {total_elapsed:.1f}s"
                )
                self._is_downloading = False
                self._cancel_download_requested = False

            self.after(0, _finish_external_queue)
            return

        for i, song in enumerate(songs):
            if self._cancel_download_requested:
                self.after(0, lambda: self._log("⏹  Download cancelled by user"))
                self.after(0, lambda: self._queue_add("⏹ cancelled"))
                break
            item_started = perf_counter()
            label_short = song.display_name[:52]
            self.after(
                0,
                lambda lb=label_short, ci=i, ct=total: (
                    self._set_status(f"⬇  {ci + 1}/{ct}  {lb}…")
                ),
            )
            logger.info("Downloading [%d/%d]: %s", i + 1, total, song.display_name)
            self.after(0, lambda n=song.display_name, ci=i, ct=total: self._queue_add(f"↓ {ci + 1}/{ct}  {n[:48]}"))

            item_out_dir = self._song_output_dir(song, album, is_top, year)

            existing = self._find_existing_in_dir(song, item_out_dir)
            if existing is not None:
                ok_count += 1
                self.after(0, lambda n=song.display_name: self._queue_add(f"✓ skip  {n[:48]}"))
                self.after(0, lambda n=song.display_name: self._log(f"  ✓  skipped (already downloaded):  {n[:55]}"))
                progress = (i + 1) / total
                self.after(0, lambda p=progress: self._progress_bar.set(p))
                continue

            if use_external:
                try:
                    launched = self._launch_aria2_song(aria2_exe, song, item_out_dir)
                    if launched:
                        ok_count += 1
                        self.after(0, lambda n=song.display_name: self._queue_add(f"↗ launch {n[:48]}"))
                        progress = (i + 1) / total
                        self.after(0, lambda p=progress: self._progress_bar.set(p))
                        continue
                except Exception as exc:
                    self.after(0, lambda e=exc, n=song.display_name: self._log(f"  ✗  external launch failed for {n[:50]} — {e}"))
                    self.after(0, lambda n=song.display_name: self._queue_add(f"✗ launch {n[:48]}"))
                    fail_count += 1
                    progress = (i + 1) / total
                    self.after(0, lambda p=progress: self._progress_bar.set(p))
                    continue

            with self._download_lock:
                result = self._downloader.download_song(song)

            item_elapsed = perf_counter() - item_started

            if result.success:
                ok_count += 1
                mb = result.size_downloaded / (1024 * 1024)
                if result.size_downloaded == 0:
                    self.after(
                        0,
                        lambda n=song.display_name: (
                            self._log(f"  ✓  skipped (already downloaded):  {n[:55]}")
                        ),
                    )
                    self.after(0, lambda n=song.display_name: self._queue_add(f"✓ skip  {n[:48]}"))
                else:
                    self.after(
                        0,
                        lambda n=song.display_name, m=mb, t=item_elapsed: (
                            self._log(f"  ✓  {n[:55]}   {m:.1f} MB  ·  {t:.1f}s")
                        ),
                    )
                    self.after(0, lambda n=song.display_name: self._queue_add(f"✓ done  {n[:48]}"))
                    logger.info(
                        "  Done: %s  (%.1f MB, %.1fs)",
                        song.display_name, mb, item_elapsed,
                    )
            else:
                fail_count += 1
                self._last_failed_songs.append(song)
                self.after(
                    0,
                    lambda n=song.display_name, err=result.error_message, t=item_elapsed: (
                        self._log(f"  ✗  {n[:55]}  —  {err}  ·  {t:.1f}s")
                    ),
                )
                logger.error("  Failed: %s — %s", song.display_name, result.error_message)
                self.after(0, lambda n=song.display_name: self._queue_add(f"✗ fail  {n[:48]}"))

            progress = (i + 1) / total
            self.after(0, lambda p=progress: self._progress_bar.set(p))

        # ── Finish ────────────────────────────────────────────────────
        total_elapsed = perf_counter() - started
        year = album.year
        if is_top:
            out_path = settings.output_dir  # songs scatter into per-artist sub-folders
        elif year:
            out_path = settings.output_dir / str(year) / album.safe_dirname
        else:
            out_path = settings.output_dir / album.safe_dirname

        def _finish() -> None:
            self._progress_bar.set(1.0)
            self.after(800, lambda: self._progress_bar.grid_remove())
            summary = f"✓ {ok_count} {'queued' if use_external else 'downloaded'}"
            if fail_count:
                summary += f"  ✗ {fail_count} failed"
            if self._cancel_download_requested:
                summary += "  ⏹ cancelled"
            self._log(
                f"Download complete!  {summary}  ({total_elapsed:.1f}s total)"
            )
            self._log(f"📁  Saved to:  {out_path}")
            self._set_status(
                f"Done — {ok_count} downloaded"
                + (f", {fail_count} failed" if fail_count else "")
                + f"  ·  {total_elapsed:.1f}s"
            )
            logger.info(
                "Download complete: %s — %d ok, %d failed, %.1fs",
                album.display_name, ok_count, fail_count, total_elapsed,
            )
            self._is_downloading = False
            self._cancel_download_requested = False

        self.after(0, _finish)


# ─── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    app = TamilMP3GUI()
    app.mainloop()


if __name__ == "__main__":
    main()
