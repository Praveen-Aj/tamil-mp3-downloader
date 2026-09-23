"""
Movies Discovery and Movie Library View.

Provides:
- Paginated listing of Tamil movies with database-level pagination and sorting
- Instant debounced search by movie title and director
- Aggregated download metrics (Total Songs, Downloaded Count, Missing Count)
- Movie cards with rich visual hierarchy and download status indicators
- One-click navigation to Movie Detail page
- Online movie discovery trigger
"""

import threading
from typing import Dict, List, Any, Callable, Optional
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk

from ui.services.library_service import LibraryService
from ui import theme


class MoviesView(ctk.CTkFrame):
    """
    User-facing Movies Discovery & Library View.
    """

    def __init__(
        self,
        master: Any,
        service: LibraryService,
        on_open_movie: Callable[[int], None],
        on_navigate: Optional[Callable[[str], None]] = None,
        **kwargs,
    ):
        super().__init__(master, fg_color=theme.BG_APP, corner_radius=0, **kwargs)
        self.service = service
        self.on_open_movie = on_open_movie
        self.on_navigate = on_navigate

        self.current_query = ""
        self.current_page = 1
        self.page_size = 18
        self.sort_by = "year"
        self.sort_ascending = False
        self._search_debounce_id: Optional[str] = None
        self._current_movies: List[Dict[str, Any]] = []
        self._total_movies: int = 0

        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── 1. Top Header & Search Toolbar ───────────────────────────
        header = ctk.CTkFrame(self, height=56, corner_radius=0, fg_color=theme.BG_HEADER)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)

        hdr_box = ctk.CTkFrame(header, fg_color="transparent")
        hdr_box.pack(side="left", padx=20, pady=10)

        ctk.CTkLabel(
            hdr_box,
            text="🎬  MOVIES",
            font=theme.font_hero(),
            text_color=theme.TEXT_PRIMARY,
        ).pack(side="left")

        ctk.CTkLabel(
            hdr_box,
            text="Soundtracks & Albums",
            font=theme.font_caption(),
            text_color=theme.TEXT_MUTED,
        ).pack(side="left", padx=(10, 0), pady=(4, 0))

        # Header Right: Search and Discover
        header_right = ctk.CTkFrame(header, fg_color="transparent")
        header_right.pack(side="right", padx=20, pady=10)

        search_box = ctk.CTkFrame(header_right, fg_color="transparent")
        search_box.pack(side="left", padx=(0, 10))

        self.search_var = tk.StringVar()
        self.search_entry = ctk.CTkEntry(
            search_box,
            textvariable=self.search_var,
            placeholder_text="Search movie title or director…",
            width=240,
            height=32,
            font=theme.font_body(),
            fg_color=theme.SURFACE_MUTED,
            border_color=theme.BORDER,
            corner_radius=theme.RADIUS_MD,
        )
        self.search_entry.pack(side="left", padx=(0, 4))
        self.search_entry.bind("<Return>", lambda _e: self._on_search())
        self.search_entry.bind("<KeyRelease>", self._on_search_keyrelease)

        self.btn_clear_search = ctk.CTkButton(
            search_box,
            text="✕",
            width=28,
            height=32,
            font=theme.font_caption_bold(),
            fg_color=theme.SURFACE_ELEVATED,
            hover_color=theme.SURFACE_HOVER,
            text_color=theme.TEXT_MUTED,
            corner_radius=theme.RADIUS_MD,
            command=self._clear_search,
        )
        self.btn_clear_search.pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            search_box,
            text="Search",
            width=65,
            height=32,
            font=theme.font_body_bold(),
            fg_color=theme.PRIMARY,
            hover_color=theme.PRIMARY_HOVER,
            corner_radius=theme.RADIUS_MD,
            command=self._on_search,
        ).pack(side="left")

        # Discover Button
        ctk.CTkButton(
            header_right,
            text="⚡  Discover Online",
            width=140,
            height=32,
            font=theme.font_body_bold(),
            fg_color=theme.PRIMARY,
            hover_color=theme.PRIMARY_HOVER,
            corner_radius=theme.RADIUS_MD,
            command=self._on_discover_clicked,
        ).pack(side="left", padx=(6, 0))

        # ── 2. Filter & Summary Subheader ────────────────────────────
        filter_bar = ctk.CTkFrame(self, height=44, corner_radius=0, fg_color=theme.BG_SIDEBAR)
        filter_bar.grid(row=1, column=0, sticky="ew")
        filter_bar.grid_propagate(False)

        fb_left = ctk.CTkFrame(filter_bar, fg_color="transparent")
        fb_left.pack(side="left", padx=20, pady=6)

        ctk.CTkLabel(
            fb_left,
            text="Sort by:",
            font=theme.font_caption(),
            text_color=theme.TEXT_MUTED,
        ).pack(side="left", padx=(0, 6))

        self.sort_var = tk.StringVar(value="Year (Newest)")
        self.sort_menu = ctk.CTkOptionMenu(
            fb_left,
            variable=self.sort_var,
            values=[
                "Year (Newest)",
                "Year (Oldest)",
                "Title (A-Z)",
                "Title (Z-A)",
                "Most Songs",
            ],
            width=135,
            height=28,
            font=theme.font_caption(),
            dropdown_font=theme.font_caption(),
            fg_color=theme.SURFACE_ELEVATED,
            button_color=theme.SURFACE_HOVER,
            command=self._on_sort_change,
            corner_radius=theme.RADIUS_SM,
        )
        self.sort_menu.pack(side="left", padx=(0, 12))

        # Result count label
        self.count_label = ctk.CTkLabel(
            fb_left,
            text="Loading movies…",
            font=theme.font_caption(),
            text_color=theme.TEXT_MUTED,
        )
        self.count_label.pack(side="left", padx=10)

        # Right side: Refresh button
        fb_right = ctk.CTkFrame(filter_bar, fg_color="transparent")
        fb_right.pack(side="right", padx=20, pady=6)

        ctk.CTkButton(
            fb_right,
            text="🔄 Refresh",
            width=80,
            height=28,
            font=theme.font_caption(),
            fg_color=theme.SURFACE_ELEVATED,
            hover_color=theme.SURFACE_HOVER,
            corner_radius=theme.RADIUS_SM,
            command=self.refresh,
        ).pack(side="right")

        # ── 3. Scrollable Grid Area ──────────────────────────────────
        self.cards_scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.cards_scroll.grid(row=2, column=0, sticky="nsew", padx=16, pady=(10, 6))
        # Configure 3 equal-width columns for card grid
        self.cards_scroll.grid_columnconfigure(0, weight=1)
        self.cards_scroll.grid_columnconfigure(1, weight=1)
        self.cards_scroll.grid_columnconfigure(2, weight=1)

        # ── 4. Bottom Pagination Toolbar ─────────────────────────────
        self.pagination_bar = ctk.CTkFrame(self, height=44, corner_radius=0, fg_color=theme.BG_HEADER)
        self.pagination_bar.grid(row=3, column=0, sticky="ew")
        self.pagination_bar.grid_propagate(False)

        pag_box = ctk.CTkFrame(self.pagination_bar, fg_color="transparent")
        pag_box.pack(side="right", padx=20, pady=6)

        self.btn_first = ctk.CTkButton(
            pag_box, text="« First", width=65, height=28,
            font=theme.font_caption(), fg_color=theme.SURFACE_ELEVATED,
            hover_color=theme.SURFACE_HOVER, corner_radius=theme.RADIUS_SM,
            command=lambda: self._go_page(1)
        )
        self.btn_first.pack(side="left", padx=3)

        self.btn_prev = ctk.CTkButton(
            pag_box, text="‹ Prev", width=65, height=28,
            font=theme.font_caption(), fg_color=theme.SURFACE_ELEVATED,
            hover_color=theme.SURFACE_HOVER, corner_radius=theme.RADIUS_SM,
            command=lambda: self._go_page(self.current_page - 1)
        )
        self.btn_prev.pack(side="left", padx=3)

        self.page_indicator = ctk.CTkLabel(
            pag_box, text="Page 1 of 1",
            font=theme.font_body_bold(), text_color=theme.TEXT_PRIMARY
        )
        self.page_indicator.pack(side="left", padx=10)

        self.btn_next = ctk.CTkButton(
            pag_box, text="Next ›", width=65, height=28,
            font=theme.font_caption(), fg_color=theme.SURFACE_ELEVATED,
            hover_color=theme.SURFACE_HOVER, corner_radius=theme.RADIUS_SM,
            command=lambda: self._go_page(self.current_page + 1)
        )
        self.btn_next.pack(side="left", padx=3)

        self.btn_last = ctk.CTkButton(
            pag_box, text="Last »", width=65, height=28,
            font=theme.font_caption(), fg_color=theme.SURFACE_ELEVATED,
            hover_color=theme.SURFACE_HOVER, corner_radius=theme.RADIUS_SM,
            command=self._go_last_page
        )
        self.btn_last.pack(side="left", padx=3)

        # Initial load
        self.refresh()

    def refresh(self) -> None:
        """Reload movies page from SQLite with current search and sort criteria."""
        movies, total = self.service.get_movies_page(
            query=self.current_query,
            sort_by=self.sort_by,
            ascending=self.sort_ascending,
            page=self.current_page,
            page_size=self.page_size,
        )
        self._current_movies = movies
        self._total_movies = total

        self._render_cards()
        self._update_pagination()

    def _render_cards(self) -> None:
        """Render movie cards in the scrollable grid or empty state."""
        # Clear existing cards
        for widget in self.cards_scroll.winfo_children():
            widget.destroy()

        if not self._current_movies:
            self._render_empty_state()
            return

        # Render cards 3 across
        num_cols = 3
        for idx, movie in enumerate(self._current_movies):
            row = idx // num_cols
            col = idx % num_cols
            self._build_movie_card(movie, row, col)

    def _build_movie_card(self, movie: Dict[str, Any], row: int, col: int) -> None:
        """Build an individual responsive movie card."""
        movie_id = movie["id"]
        title = movie["title"]
        year = movie.get("year")
        director = movie.get("director")
        total_songs = movie.get("total_songs", 0)
        downloaded = movie.get("downloaded_count", 0)
        missing = movie.get("missing_count", 0)

        card = ctk.CTkFrame(
            self.cards_scroll,
            fg_color=theme.SURFACE,
            border_color=theme.BORDER,
            border_width=1,
            corner_radius=theme.RADIUS_LG,
        )
        # Hover feedback
        card.bind("<Enter>", lambda e: card.configure(border_color=theme.BORDER_LIGHT))
        card.bind("<Leave>", lambda e: card.configure(border_color=theme.BORDER))

        # Top Header of Card: Poster Icon Box + Year Pill
        top_box = ctk.CTkFrame(card, fg_color="transparent")
        top_box.pack(fill="x", padx=14, pady=(14, 8))

        icon_frame = ctk.CTkFrame(
            top_box,
            width=46,
            height=46,
            corner_radius=theme.RADIUS_MD,
            fg_color=theme.SURFACE_ELEVATED,
        )
        icon_frame.pack(side="left")
        icon_frame.pack_propagate(False)

        poster_url = movie.get("poster_url") or movie.get("image_url")
        icon_lbl = ctk.CTkLabel(icon_frame, text="")
        icon_lbl.pack(expand=True, fill="both")
        self.service.artwork.bind_artwork(
            widget=icon_lbl,
            source=poster_url,
            size=(46, 46),
            entity_type="movie",
            fallback_text=title,
        )

        if year:
            year_badge = ctk.CTkFrame(
                top_box,
                fg_color=theme.SURFACE_ELEVATED,
                corner_radius=theme.RADIUS_SM,
            )
            year_badge.pack(side="right")
            ctk.CTkLabel(
                year_badge,
                text=str(year),
                font=theme.font_caption_bold(),
                text_color=theme.PRIMARY_LIGHT,
            ).pack(padx=8, pady=3)

        # Title
        title_lbl = ctk.CTkLabel(
            card,
            text=title,
            font=theme.font_title(),
            text_color=theme.TEXT_PRIMARY,
            anchor="w",
            wraplength=220,
        )
        title_lbl.pack(fill="x", padx=14, pady=(4, 2))

        # Director / Subtitle
        dir_text = f"Dir. {director}" if director else "Tamil Movie Soundtrack"
        ctk.CTkLabel(
            card,
            text=dir_text,
            font=theme.font_caption(),
            text_color=theme.TEXT_MUTED,
            anchor="w",
        ).pack(fill="x", padx=14, pady=(0, 10))

        # Metrics & Badges Row
        metrics_box = ctk.CTkFrame(card, fg_color="transparent")
        metrics_box.pack(fill="x", padx=14, pady=(0, 12))

        # Song Count Pill
        songs_pill = ctk.CTkFrame(metrics_box, fg_color=theme.SURFACE_MUTED, corner_radius=theme.RADIUS_SM)
        songs_pill.pack(side="left", padx=(0, 6))
        ctk.CTkLabel(
            songs_pill,
            text=f"🎵  {total_songs} songs",
            font=theme.font_badge(),
            text_color=theme.TEXT_SECONDARY,
        ).pack(padx=6, pady=3)

        # Download Status Pill
        if total_songs > 0 and downloaded >= total_songs:
            status_text = "✓ Downloaded"
            st_bg = theme.SUCCESS_BG
            st_fg = theme.SUCCESS_LIGHT
        elif downloaded > 0:
            status_text = f"⏳ {downloaded}/{total_songs} DL"
            st_bg = theme.WARNING_BG
            st_fg = theme.WARNING_LIGHT
        else:
            status_text = "Not Downloaded"
            st_bg = theme.SURFACE_ELEVATED
            st_fg = theme.TEXT_MUTED

        dl_pill = ctk.CTkFrame(metrics_box, fg_color=st_bg, corner_radius=theme.RADIUS_SM)
        dl_pill.pack(side="left")
        ctk.CTkLabel(
            dl_pill,
            text=status_text,
            font=theme.font_badge(),
            text_color=st_fg,
        ).pack(padx=7, pady=3)

        # Open Movie Action Button
        btn_view = ctk.CTkButton(
            card,
            text="Open Movie  ›",
            height=32,
            font=theme.font_caption_bold(),
            fg_color=theme.SURFACE_ELEVATED,
            hover_color=theme.PRIMARY,
            text_color=theme.TEXT_PRIMARY,
            corner_radius=theme.RADIUS_SM,
            command=lambda mid=movie_id: self.on_open_movie(mid),
        )
        btn_view.pack(fill="x", padx=14, pady=(0, 14))

    def _render_empty_state(self) -> None:
        """Render empty state when no movies match query or library is empty."""
        empty_frame = ctk.CTkFrame(self.cards_scroll, fg_color="transparent")
        empty_frame.grid(row=0, column=0, columnspan=3, pady=60, sticky="nsew")

        ctk.CTkLabel(
            empty_frame,
            text="🎬",
            font=ctk.CTkFont(size=56),
        ).pack(pady=(0, 12))

        ctk.CTkLabel(
            empty_frame,
            text="No movies found" if self.current_query else "No movies in catalog yet",
            font=theme.font_title(),
            text_color=theme.TEXT_PRIMARY,
        ).pack(pady=(0, 6))

        sub_msg = (
            f"No movies matched '{self.current_query}'. Try a different search."
            if self.current_query
            else "Discover Tamil movie soundtracks directly from online sources or add your local music library."
        )
        ctk.CTkLabel(
            empty_frame,
            text=sub_msg,
            font=theme.font_body(),
            text_color=theme.TEXT_MUTED,
            wraplength=420,
        ).pack(pady=(0, 18))

        btn_box = ctk.CTkFrame(empty_frame, fg_color="transparent")
        btn_box.pack()

        if self.current_query:
            ctk.CTkButton(
                btn_box,
                text="Clear Search",
                width=120,
                height=34,
                font=theme.font_body_bold(),
                fg_color=theme.SURFACE_ELEVATED,
                hover_color=theme.SURFACE_HOVER,
                corner_radius=theme.RADIUS_MD,
                command=self._clear_search,
            ).pack(side="left", padx=6)

        ctk.CTkButton(
            btn_box,
            text="⚡  Discover Online Movies",
            width=180,
            height=34,
            font=theme.font_body_bold(),
            fg_color=theme.PRIMARY,
            hover_color=theme.PRIMARY_HOVER,
            corner_radius=theme.RADIUS_MD,
            command=self._on_discover_clicked,
        ).pack(side="left", padx=6)

    def _update_pagination(self) -> None:
        """Update pagination buttons and labels."""
        total_pages = max(1, (self._total_movies + self.page_size - 1) // self.page_size)
        start_idx = (self.current_page - 1) * self.page_size + 1 if self._total_movies > 0 else 0
        end_idx = min(self.current_page * self.page_size, self._total_movies)

        self.count_label.configure(
            text=f"Showing {start_idx}–{end_idx} of {self._total_movies} movies"
        )
        self.page_indicator.configure(text=f"Page {self.current_page} of {total_pages}")

        self.btn_first.configure(state="normal" if self.current_page > 1 else "disabled")
        self.btn_prev.configure(state="normal" if self.current_page > 1 else "disabled")
        self.btn_next.configure(state="normal" if self.current_page < total_pages else "disabled")
        self.btn_last.configure(state="normal" if self.current_page < total_pages else "disabled")

    def _go_page(self, page: int) -> None:
        total_pages = max(1, (self._total_movies + self.page_size - 1) // self.page_size)
        if 1 <= page <= total_pages:
            self.current_page = page
            self.refresh()

    def _go_last_page(self) -> None:
        total_pages = max(1, (self._total_movies + self.page_size - 1) // self.page_size)
        self._go_page(total_pages)

    def _on_search(self) -> None:
        self.current_query = self.search_var.get().strip()
        self.current_page = 1
        self.refresh()

    def _on_search_keyrelease(self, _event) -> None:
        if self._search_debounce_id:
            self.after_cancel(self._search_debounce_id)
        self._search_debounce_id = self.after(300, self._on_search)

    def _clear_search(self) -> None:
        self.search_var.set("")
        self.current_query = ""
        self.current_page = 1
        self.refresh()

    def _on_sort_change(self, value: str) -> None:
        sort_configs = {
            "Year (Newest)": ("year", False),
            "Year (Oldest)": ("year", True),
            "Title (A-Z)": ("title", True),
            "Title (Z-A)": ("title", False),
            "Most Songs": ("tracks", False),
        }
        self.sort_by, self.sort_ascending = sort_configs.get(value, ("year", False))
        self.current_page = 1
        self.refresh()

    def _on_discover_clicked(self) -> None:
        """Trigger background movie discovery from online regional scrapers."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Discover Movies")
        dialog.geometry("400x220")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        ctk.CTkLabel(
            dialog,
            text="⚡  Discover Online Movies",
            font=theme.font_title(),
            text_color=theme.TEXT_PRIMARY,
        ).pack(pady=(20, 10))

        ctk.CTkLabel(
            dialog,
            text="Fetch latest Tamil movies and soundtrack albums into your library catalog:",
            font=theme.font_caption(),
            text_color=theme.TEXT_MUTED,
            wraplength=340,
        ).pack(pady=(0, 14))

        status_lbl = ctk.CTkLabel(
            dialog,
            text="Ready to discover from MassTamilan & TamilMP3",
            font=theme.font_caption(),
            text_color=theme.PRIMARY_LIGHT,
        )
        status_lbl.pack(pady=(0, 14))

        prog_bar = ctk.CTkProgressBar(dialog, width=320, mode="indeterminate")
        prog_bar.pack(pady=(0, 14))

        btn_run = ctk.CTkButton(
            dialog,
            text="Start Discovery",
            font=theme.font_body_bold(),
            fg_color=theme.PRIMARY,
            hover_color=theme.PRIMARY_HOVER,
        )
        btn_run.pack(pady=4)

        def _worker():
            try:
                res = self.service.discover_movies_from_sources(category="latest", max_pages=1)
                m_cnt = res.get("movies_discovered", 0)
                s_cnt = res.get("songs_registered", 0)
                dialog.after(0, lambda: [
                    prog_bar.stop(),
                    status_lbl.configure(text=f"Discovered {m_cnt} movies ({s_cnt} songs)!"),
                    btn_run.configure(text="Done", command=dialog.destroy, state="normal"),
                    self.refresh(),
                ])
            except Exception as e:
                err_str = str(e)
                dialog.after(0, lambda: [
                    prog_bar.stop(),
                    status_lbl.configure(text=f"Error: {err_str[:40]}"),
                    btn_run.configure(text="Close", command=dialog.destroy, state="normal"),
                ])

        def _start():
            btn_run.configure(state="disabled")
            status_lbl.configure(text="Connecting to online sources…")
            prog_bar.start()
            threading.Thread(target=_worker, daemon=True).start()

        btn_run.configure(command=_start)
