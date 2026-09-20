"""
Music Library View.

Desktop music library interface backed by SQLite FTS5 search and composable SQL filtering.
Supports:
- Debounced Search (Title, Artist, Album) with instant Clear
- Multi-dimensional Filtering (Status: ALL / DOWNLOADED / NOT DOWNLOADED, Quality, Source, Artist)
- Multi-column Sorting (Recently Added, Title, Artist, Album, Bitrate, Status, Year) with Direction Toggle
- Presentation Switch (Table View / Grid View)
- Multi-selection & Select All Page
- Direct Actions: [Open Folder], [Delete] with confirmation, [Download Selected]
- Secondary Action: Import Existing Files (local MP3 folder scanner)
- Double-click or click Details to open Song Details dialog
- Dedicated Empty State with quick filter reset
"""

from typing import Dict, List, Any, Callable, Optional
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk

from library.models import LibrarySong, SongState
from ui.components.song_table import SongTable
from ui.dialogs.song_details import SongDetailsDialog
from ui.dialogs.plan_preview import PlanPreviewDialog
from ui.services.library_service import LibraryService
from ui import theme


class LibraryView(ctk.CTkFrame):
    """
    Paginated Music Library view with Table/Grid switch, composable filters, FTS search,
    and inspector dialogs.
    """

    def __init__(
        self,
        master: Any,
        service: LibraryService,
        on_start_downloads: Optional[Callable[[List[int]], None]] = None,
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", corner_radius=0, **kwargs)
        self.service = service
        self.on_start_downloads = on_start_downloads

        self.current_filter = "ALL"
        self.current_query = ""
        self.current_page = 1
        self.current_view_mode = "TABLE"  # "TABLE" or "GRID"
        self.sort_by = "id"
        self.sort_ascending = False
        self._search_debounce_id: Optional[str] = None
        self._current_songs: List[LibrarySong] = []

        self.grid_rowconfigure(3, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── 1. Top Header & Search Toolbar ───────────────────────────
        header = ctk.CTkFrame(self, height=56, corner_radius=0, fg_color=theme.BG_HEADER)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)

        hdr_box = ctk.CTkFrame(header, fg_color="transparent")
        hdr_box.pack(side="left", padx=20, pady=10)

        ctk.CTkLabel(
            hdr_box,
            text="📚  MUSIC LIBRARY",
            font=theme.font_hero(),
            text_color=theme.TEXT_PRIMARY,
        ).pack(side="left")

        # View Mode Toggle & Search Box on Right
        header_right = ctk.CTkFrame(header, fg_color="transparent")
        header_right.pack(side="right", padx=20, pady=10)

        # Search Box Container
        search_box = ctk.CTkFrame(header_right, fg_color="transparent")
        search_box.pack(side="left", padx=(0, 10))

        self.search_var = tk.StringVar()
        self.search_entry = ctk.CTkEntry(
            search_box,
            textvariable=self.search_var,
            placeholder_text="Search title, artist, album…",
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

        # Quick Clear Search button
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

        # Presentation Switch (Table vs Grid)
        self.view_switch = ctk.CTkSegmentedButton(
            header_right,
            values=["📄 Table", "▦ Grid"],
            font=theme.font_caption_bold(),
            height=30,
            selected_color=theme.PRIMARY,
            command=self._on_view_mode_changed,
        )
        self.view_switch.set("📄 Table")
        self.view_switch.pack(side="left")

        # ── 2. Composable Filter & Sorting Toolbar ───────────────────
        filter_bar = ctk.CTkFrame(
            self,
            corner_radius=theme.RADIUS_MD,
            fg_color=theme.SURFACE,
            border_width=1,
            border_color=theme.BORDER,
        )
        filter_bar.grid(row=1, column=0, sticky="ew", padx=20, pady=(10, 6))

        fb_inner = ctk.CTkFrame(filter_bar, fg_color="transparent")
        fb_inner.pack(fill="x", padx=12, pady=7)

        # State Filter Segmented Buttons (Consumer terminology: ALL, DOWNLOADED, NOT DOWNLOADED)
        self.filter_var = ctk.StringVar(value="ALL")
        self.filter_btn = ctk.CTkSegmentedButton(
            fb_inner,
            values=["ALL", "DOWNLOADED", "NOT DOWNLOADED"],
            variable=self.filter_var,
            font=theme.font_caption_bold(),
            height=28,
            selected_color=theme.PRIMARY,
            command=self._on_filter_changed,
        )
        self.filter_btn.pack(side="left", padx=(0, 10))

        # Quality Dropdown
        self.quality_var = ctk.StringVar(value="All Bitrates")
        self.quality_menu = ctk.CTkOptionMenu(
            fb_inner,
            values=["All Bitrates", "320 kbps", "128 kbps"],
            variable=self.quality_var,
            font=theme.font_caption(),
            dropdown_font=theme.font_caption(),
            width=110,
            height=28,
            fg_color=theme.SURFACE_ELEVATED,
            button_color=theme.SURFACE_HOVER,
            text_color=theme.TEXT_PRIMARY,
            corner_radius=theme.RADIUS_SM,
            command=lambda _val: self._on_filter_dropdown_changed(),
        )
        self.quality_menu.pack(side="left", padx=(0, 6))

        # Source Dropdown
        self.source_var = ctk.StringVar(value="All Sources")
        self.source_menu = ctk.CTkOptionMenu(
            fb_inner,
            values=["All Sources"],
            variable=self.source_var,
            font=theme.font_caption(),
            dropdown_font=theme.font_caption(),
            width=120,
            height=28,
            fg_color=theme.SURFACE_ELEVATED,
            button_color=theme.SURFACE_HOVER,
            text_color=theme.TEXT_PRIMARY,
            corner_radius=theme.RADIUS_SM,
            command=lambda _val: self._on_filter_dropdown_changed(),
        )
        self.source_menu.pack(side="left", padx=(0, 6))

        # Artist Dropdown
        self.artist_var = ctk.StringVar(value="All Artists")
        self.artist_menu = ctk.CTkOptionMenu(
            fb_inner,
            values=["All Artists"],
            variable=self.artist_var,
            font=theme.font_caption(),
            dropdown_font=theme.font_caption(),
            width=125,
            height=28,
            fg_color=theme.SURFACE_ELEVATED,
            button_color=theme.SURFACE_HOVER,
            text_color=theme.TEXT_PRIMARY,
            corner_radius=theme.RADIUS_SM,
            command=lambda _val: self._on_filter_dropdown_changed(),
        )
        self.artist_menu.pack(side="left", padx=(0, 10))

        # Right side: Sort controls & Reset Filters
        fb_right = ctk.CTkFrame(fb_inner, fg_color="transparent")
        fb_right.pack(side="right")

        ctk.CTkLabel(
            fb_right,
            text="Sort:",
            font=theme.font_caption(),
            text_color=theme.TEXT_MUTED,
        ).pack(side="left", padx=(0, 4))

        self.sort_var = ctk.StringVar(value="Recently Added")
        self.sort_menu = ctk.CTkOptionMenu(
            fb_right,
            values=["Recently Added", "Title", "Artist", "Album", "Bitrate", "Status", "Year"],
            variable=self.sort_var,
            font=theme.font_caption(),
            dropdown_font=theme.font_caption(),
            width=120,
            height=28,
            fg_color=theme.SURFACE_ELEVATED,
            button_color=theme.SURFACE_HOVER,
            text_color=theme.TEXT_PRIMARY,
            corner_radius=theme.RADIUS_SM,
            command=lambda _val: self._on_sort_changed(),
        )
        self.sort_menu.pack(side="left", padx=(0, 4))

        # Sort Direction Toggle Button
        self.sort_dir_btn = ctk.CTkButton(
            fb_right,
            text="↓",
            width=28,
            height=28,
            font=theme.font_caption_bold(),
            fg_color=theme.SURFACE_ELEVATED,
            hover_color=theme.SURFACE_HOVER,
            text_color=theme.TEXT_PRIMARY,
            corner_radius=theme.RADIUS_SM,
            command=self._toggle_sort_direction,
        )
        self.sort_dir_btn.pack(side="left", padx=(0, 8))

        # Reset All Filters
        ctk.CTkButton(
            fb_right,
            text="↺ Reset",
            width=65,
            height=28,
            font=theme.font_caption(),
            fg_color=theme.SURFACE_ELEVATED,
            hover_color=theme.SURFACE_HOVER,
            text_color=theme.TEXT_MUTED,
            corner_radius=theme.RADIUS_SM,
            command=self._clear_all_filters,
        ).pack(side="left")

        # ── 3. Actions & Selection Toolbar ───────────────────────────
        action_bar = ctk.CTkFrame(
            self,
            corner_radius=theme.RADIUS_MD,
            fg_color=theme.SURFACE,
            border_width=1,
            border_color=theme.BORDER,
        )
        action_bar.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 8))

        ab_inner = ctk.CTkFrame(action_bar, fg_color="transparent")
        ab_inner.pack(fill="x", padx=12, pady=6)

        # Selection Helpers
        ctk.CTkButton(
            ab_inner,
            text="Select All",
            width=75,
            height=26,
            font=theme.font_caption_bold(),
            fg_color=theme.SURFACE_ELEVATED,
            hover_color=theme.SURFACE_HOVER,
            text_color=theme.TEXT_SECONDARY,
            corner_radius=theme.RADIUS_SM,
            command=self._select_all,
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            ab_inner,
            text="Clear",
            width=60,
            height=26,
            font=theme.font_caption_bold(),
            fg_color=theme.SURFACE_ELEVATED,
            hover_color=theme.SURFACE_HOVER,
            text_color=theme.TEXT_SECONDARY,
            corner_radius=theme.RADIUS_SM,
            command=self._clear_selection,
        ).pack(side="left", padx=2)

        # Dynamic Results Count Label in Center
        self.count_label = ctk.CTkLabel(
            ab_inner,
            text="Loading library…",
            font=theme.font_caption(),
            text_color=theme.TEXT_MUTED,
        )
        self.count_label.pack(side="left", padx=16)

        # Right side actions
        right_actions = ctk.CTkFrame(ab_inner, fg_color="transparent")
        right_actions.pack(side="right")

        ctk.CTkButton(
            right_actions,
            text="🗑️ Delete Selected",
            font=theme.font_caption_bold(),
            width=120,
            height=26,
            fg_color=theme.SURFACE_ELEVATED,
            hover_color=theme.ERROR,
            text_color=theme.TEXT_SECONDARY,
            corner_radius=theme.RADIUS_SM,
            command=self._delete_selected_songs,
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            right_actions,
            text="📂 Import Files",
            font=theme.font_caption_bold(),
            width=105,
            height=26,
            fg_color=theme.SURFACE_ELEVATED,
            hover_color=theme.SURFACE_HOVER,
            text_color=theme.TEXT_PRIMARY,
            corner_radius=theme.RADIUS_SM,
            command=self._import_existing_files,
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            right_actions,
            text="⬇ Download Selected",
            font=theme.font_caption_bold(),
            width=140,
            height=26,
            fg_color=theme.SUCCESS,
            hover_color=theme.SUCCESS_BG,
            text_color=theme.TEXT_PRIMARY,
            corner_radius=theme.RADIUS_SM,
            command=self._plan_selected_downloads,
        ).pack(side="left", padx=(2, 0))

        # ── 4. Content Body Container (Table Wrap & Grid Scroll & Empty State) ────
        self.body_wrap = ctk.CTkFrame(self, fg_color="transparent")
        self.body_wrap.grid(row=3, column=0, sticky="nsew", padx=20, pady=(0, 12))
        self.body_wrap.grid_rowconfigure(0, weight=1)
        self.body_wrap.grid_columnconfigure(0, weight=1)

        # Table View Component
        self.table = SongTable(
            self.body_wrap,
            on_song_double_click=self._on_song_double_click,
            on_page_change=self._on_page_change,
            on_selection_change=self._on_selection_change,
            on_sort_change=self._on_table_sort_change,
        )
        self.table.grid(row=0, column=0, sticky="nsew")

        # Grid View Scrollable Container
        self.grid_scroll = ctk.CTkScrollableFrame(self.body_wrap, fg_color="transparent", corner_radius=0)
        self.grid_scroll.grid_columnconfigure(0, weight=1)
        self.grid_scroll.grid_columnconfigure(1, weight=1)
        self.grid_scroll.grid_columnconfigure(2, weight=1)

        # Empty State Container
        self.empty_card = ctk.CTkFrame(
            self.body_wrap,
            fg_color=theme.SURFACE,
            corner_radius=theme.RADIUS_MD,
            border_width=1,
            border_color=theme.BORDER,
        )
        empty_inner = ctk.CTkFrame(self.empty_card, fg_color="transparent")
        empty_inner.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            empty_inner,
            text="🔍",
            font=ctk.CTkFont(size=40),
        ).pack(pady=(0, 10))

        ctk.CTkLabel(
            empty_inner,
            text="No songs found",
            font=theme.font_title(),
            text_color=theme.TEXT_PRIMARY,
        ).pack(pady=(0, 4))

        ctk.CTkLabel(
            empty_inner,
            text="Try adjusting your search keywords or clearing active filters.",
            font=theme.font_body(),
            text_color=theme.TEXT_MUTED,
        ).pack(pady=(0, 14))

        ctk.CTkButton(
            empty_inner,
            text="Reset All Filters",
            font=theme.font_caption_bold(),
            width=130,
            height=32,
            fg_color=theme.PRIMARY,
            hover_color=theme.PRIMARY_HOVER,
            corner_radius=theme.RADIUS_MD,
            command=self._clear_all_filters,
        ).pack()

        # Load filter options dropdowns
        self._populate_filter_dropdowns()

        # Initial load
        self.refresh()

    def _populate_filter_dropdowns(self) -> None:
        """Populate source, quality, and artist dropdown choices from database."""
        try:
            opts = self.service.get_filter_options()
            sources = opts.get("sources", [])
            if sources:
                self.source_menu.configure(values=["All Sources"] + sources)

            artists = opts.get("artists", [])
            if artists:
                # Limit to 50 for clean UI
                self.artist_menu.configure(values=["All Artists"] + artists[:50])
        except Exception:
            pass

    def _on_view_mode_changed(self, mode_str: str) -> None:
        if "Grid" in mode_str:
            self.current_view_mode = "GRID"
            self.table.grid_remove()
            self.grid_scroll.grid(row=0, column=0, sticky="nsew")
            self._render_grid_view()
        else:
            self.current_view_mode = "TABLE"
            self.grid_scroll.grid_remove()
            self.table.grid(row=0, column=0, sticky="nsew")

    def refresh(self) -> None:
        """Fetch and render data for current filter/query/page/sort."""
        state_map = {
            "DOWNLOADED": "OWNED",
            "NOT DOWNLOADED": "NEW",
            "ALL": None,
        }
        state_filter = state_map.get(self.current_filter, None)

        # Parse quality
        q_val = self.quality_var.get()
        quality_kbps = None
        if "320" in q_val:
            quality_kbps = 320
        elif "128" in q_val:
            quality_kbps = 128

        # Parse source
        src_val = self.source_var.get()
        source_name = None if src_val in ("All Sources", "Source") else src_val

        # Parse artist
        art_val = self.artist_var.get()
        artist_name = None if art_val in ("All Artists", "Artist") else art_val

        # Parse sort
        sort_map = {
            "Recently Added": "id",
            "Title": "title",
            "Artist": "artist",
            "Album": "album",
            "Bitrate": "quality",
            "Status": "state",
            "Year": "year",
        }
        sort_col = sort_map.get(self.sort_var.get(), "id")

        res = self.service.get_library_page(
            query=self.current_query or "",
            state=state_filter,
            quality=quality_kbps,
            source=source_name,
            artist=artist_name,
            sort_by=sort_col,
            ascending=self.sort_ascending,
            page=self.current_page,
            page_size=50,
        )
        self._current_songs = res.get("songs", [])
        total_items = res.get("total_items", len(self._current_songs))
        cur_page = res.get("page", self.current_page)
        total_pages = res.get("total_pages", 1)

        # Update dynamic result count label
        has_active_filter = bool(
            self.current_query or state_filter or quality_kbps or source_name or artist_name
        )
        if has_active_filter:
            self.count_label.configure(
                text=f"🔍 Found {total_items:,} matching songs"
            )
        else:
            self.count_label.configure(
                text=f"📚 {total_items:,} songs in library"
            )

        # Handle empty results state
        if total_items == 0:
            self.table.grid_remove()
            self.grid_scroll.grid_remove()
            self.empty_card.grid(row=0, column=0, sticky="nsew")
            return
        else:
            self.empty_card.grid_remove()

        if self.current_view_mode == "GRID":
            self.table.grid_remove()
            self.grid_scroll.grid(row=0, column=0, sticky="nsew")
            self._render_grid_view()
        else:
            self.grid_scroll.grid_remove()
            self.table.grid(row=0, column=0, sticky="nsew")
            self.table.set_data(
                songs=self._current_songs,
                total_items=total_items,
                page=cur_page,
                total_pages=total_pages,
            )

    def _render_grid_view(self) -> None:
        """Render grid cards for music tracks."""
        for w in self.grid_scroll.winfo_children():
            w.destroy()

        if not self._current_songs:
            empty = ctk.CTkFrame(self.grid_scroll, fg_color="transparent")
            empty.pack(fill="both", expand=True, pady=40)
            ctk.CTkLabel(
                empty,
                text="No songs found matching your search or filter.",
                font=theme.font_body(),
                text_color=theme.TEXT_MUTED,
            ).pack()
            return

        cols = 3
        for idx, song in enumerate(self._current_songs):
            row = idx // cols
            col = idx % cols

            card = ctk.CTkFrame(
                self.grid_scroll,
                fg_color=theme.SURFACE,
                corner_radius=theme.RADIUS_MD,
                border_width=1,
                border_color=theme.BORDER,
            )
            card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")

            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill="both", padx=12, pady=10)

            # Header row with art and status
            top_row = ctk.CTkFrame(inner, fg_color="transparent")
            top_row.pack(fill="x")

            art = ctk.CTkFrame(
                top_row,
                width=38,
                height=38,
                corner_radius=theme.RADIUS_SM,
                fg_color=theme.SURFACE_ACTIVE,
            )
            art.pack(side="left")
            art.pack_propagate(False)
            ctk.CTkLabel(art, text="🎵", font=ctk.CTkFont(size=18)).pack(expand=True)

            status_badge = "✓ Downloaded" if song.state == SongState.OWNED else "Not Downloaded"
            badge_col = theme.SUCCESS if song.state == SongState.OWNED else theme.TEXT_DIM
            ctk.CTkLabel(
                top_row,
                text=status_badge,
                font=theme.font_badge(),
                text_color=badge_col,
            ).pack(side="right")

            # Title & details
            ctk.CTkLabel(
                inner,
                text=song.title,
                font=theme.font_body_bold(),
                text_color=theme.TEXT_PRIMARY,
                anchor="w",
            ).pack(anchor="w", pady=(8, 2))

            ctk.CTkLabel(
                inner,
                text=f"{song.artist or 'Unknown Artist'} · {song.album or 'Tamil Music'}",
                font=theme.font_caption(),
                text_color=theme.TEXT_MUTED,
                anchor="w",
            ).pack(anchor="w")

            # Bitrate & Action buttons row
            btn_row = ctk.CTkFrame(inner, fg_color="transparent")
            btn_row.pack(fill="x", pady=(10, 0))

            bitrate_text = f"{song.bitrate_kbps} kbps" if song.bitrate_kbps else "320 kbps"
            ctk.CTkLabel(
                btn_row,
                text=bitrate_text,
                font=theme.font_badge(),
                text_color=theme.ACCENT_CYAN,
            ).pack(side="left")

            if song.state == SongState.OWNED:
                ctk.CTkButton(
                    btn_row,
                    text="🗑️ Delete",
                    font=theme.font_caption_bold(),
                    width=60,
                    height=24,
                    fg_color=theme.SURFACE_ELEVATED,
                    hover_color=theme.ERROR,
                    text_color=theme.TEXT_SECONDARY,
                    command=lambda sid=song.id, t=song.title: self._confirm_delete_song(sid, t),
                ).pack(side="right", padx=(4, 0))

                ctk.CTkButton(
                    btn_row,
                    text="📁 Folder",
                    font=theme.font_caption_bold(),
                    width=65,
                    height=24,
                    fg_color=theme.SURFACE_ELEVATED,
                    hover_color=theme.SURFACE_HOVER,
                    text_color=theme.TEXT_SECONDARY,
                    command=lambda p=song.file_path: self.service.open_path_in_explorer(p),
                ).pack(side="right")
            else:
                ctk.CTkButton(
                    btn_row,
                    text="⬇ Download",
                    font=theme.font_caption_bold(),
                    width=85,
                    height=24,
                    fg_color=theme.PRIMARY,
                    hover_color=theme.PRIMARY_HOVER,
                    text_color=theme.TEXT_PRIMARY,
                    command=lambda sid=song.id: self._download_single_song(sid),
                ).pack(side="right")

    def _on_search_keyrelease(self, _event=None) -> None:
        """Debounce search keystrokes by 250ms."""
        if self._search_debounce_id:
            self.after_cancel(self._search_debounce_id)
        self._search_debounce_id = self.after(250, self._on_search_debounced)

    def _on_search_debounced(self) -> None:
        """Trigger search after debounce delay."""
        new_q = self.search_var.get().strip()
        if new_q != self.current_query:
            self.current_query = new_q
            self.current_page = 1
            self.refresh()

    def _on_search(self) -> None:
        """Immediately trigger search."""
        if self._search_debounce_id:
            self.after_cancel(self._search_debounce_id)
            self._search_debounce_id = None
        self.current_query = self.search_var.get().strip()
        self.current_page = 1
        self.refresh()

    def _clear_search(self) -> None:
        """Clear search query and restore normal library view."""
        if self._search_debounce_id:
            self.after_cancel(self._search_debounce_id)
            self._search_debounce_id = None
        self.search_var.set("")
        self.current_query = ""
        self.current_page = 1
        self.refresh()

    def _on_filter_changed(self, value: str) -> None:
        self.current_filter = value
        self.current_page = 1
        self.refresh()

    def _on_filter_dropdown_changed(self) -> None:
        self.current_page = 1
        self.refresh()

    def _on_sort_changed(self) -> None:
        self.refresh()

    def _toggle_sort_direction(self) -> None:
        self.sort_ascending = not self.sort_ascending
        self.sort_dir_btn.configure(text="↑" if self.sort_ascending else "↓")
        self.refresh()

    def _on_table_sort_change(self, col: str, ascending: bool) -> None:
        """Sync table header clicks with sort dropdown and direction."""
        col_to_label = {
            "id": "Recently Added",
            "title": "Title",
            "artist": "Artist",
            "album": "Album",
            "quality": "Bitrate",
            "state": "Status",
            "year": "Year",
        }
        label = col_to_label.get(col, "Recently Added")
        self.sort_var.set(label)
        self.sort_ascending = ascending
        self.sort_dir_btn.configure(text="↑" if ascending else "↓")
        self.refresh()

    def _clear_all_filters(self) -> None:
        """Reset all search and filter conditions to defaults."""
        if self._search_debounce_id:
            self.after_cancel(self._search_debounce_id)
            self._search_debounce_id = None
        self.search_var.set("")
        self.current_query = ""
        self.filter_var.set("ALL")
        self.current_filter = "ALL"
        self.quality_var.set("All Bitrates")
        self.source_var.set("All Sources")
        self.artist_var.set("All Artists")
        self.sort_var.set("Recently Added")
        self.sort_ascending = False
        self.sort_dir_btn.configure(text="↓")
        self.current_page = 1
        self.refresh()

    def _on_page_change(self, page: int) -> None:
        self.current_page = page
        self.refresh()

    def _on_selection_change(self, selected: List[LibrarySong]) -> None:
        pass

    def _select_all(self) -> None:
        self.table.select_all()

    def _clear_selection(self) -> None:
        self.table.clear_selection()

    def _confirm_delete_song(self, song_id: int, song_title: str) -> None:
        if messagebox.askyesno("Delete Song", f"Delete \"{song_title}\"?\n\nThis will remove the downloaded MP3 file from your computer and update your library."):
            self.service.delete_downloaded_song(song_id, delete_physical_file=True)
            self.refresh()

    def _delete_selected_songs(self) -> None:
        selected = self.table.get_selected_songs()
        if not selected:
            return
        downloaded = [s for s in selected if s.state == SongState.OWNED]
        if not downloaded:
            messagebox.showinfo("Delete Selection", "None of the selected songs are currently downloaded.")
            return
        if messagebox.askyesno("Delete Selected Songs", f"Delete {len(downloaded)} downloaded songs from your computer?"):
            for s in downloaded:
                self.service.delete_downloaded_song(s.id, delete_physical_file=True)
            self.refresh()

    def _download_single_song(self, song_id: int) -> None:
        plan = self.service.preview_download_plan([song_id])
        dl_ids = self.service.execute_download_plan(plan, run_async=True)
        if self.on_start_downloads and dl_ids:
            self.on_start_downloads(dl_ids)
        self.refresh()

    def _on_song_double_click(self, song: LibrarySong) -> None:
        """Open detailed duplicate & metadata inspector dialog."""
        details = self.service.get_song_details(song.id)
        SongDetailsDialog(
            self.winfo_toplevel(),
            song=song,
            sources=details.get("sources", []),
            contexts=details.get("contexts", []),
            planner_decision=details.get("planner_decision", None),
            service=self.service,
        )

    def _plan_selected_downloads(self) -> None:
        """Generate and preview download plan for selected songs."""
        selected = self.table.get_selected_songs()
        if not selected:
            return
        selected_ids = [s.id for s in selected if s.id is not None]
        plan = self.service.preview_download_plan(selected_ids)
        PlanPreviewDialog(
            self.winfo_toplevel(),
            plan=plan,
            on_confirm=lambda: self._on_plan_confirmed(plan),
        )

    def _on_plan_confirmed(self, plan: Any) -> None:
        """Execute approved plan and trigger callback."""
        dl_ids = self.service.execute_download_plan(plan, run_async=True)
        if self.on_start_downloads and dl_ids:
            self.on_start_downloads(dl_ids)
        self.refresh()

    def _import_existing_files(self) -> None:
        """Open folder picker to import existing MP3 collection."""
        from tkinter import filedialog
        folder = filedialog.askdirectory(title="Select Music Folder to Import")
        if folder:
            self.service.importer.import_directory(folder)
            self.refresh()
