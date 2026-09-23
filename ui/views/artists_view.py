"""
Artists and People Discovery and Library View.

Provides:
- Paginated directory of Tamil music artists, singers, music directors, and actors
- Filter by role: All, Singers, Music Directors, Actors
- Instant debounced search by name (English and Tamil Unicode)
- Aggregated soundtrack metrics (Total Songs, Downloaded Count, Missing Count, Total Movies)
- Interactive cards with role chips and download status indicators
- One-click navigation to Artist Detail page
"""

import threading
from typing import Dict, List, Any, Callable, Optional
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk

from ui.services.library_service import LibraryService
from ui import theme


class ArtistsView(ctk.CTkFrame):
    """
    User-facing Artists and People Directory View.
    """

    def __init__(
        self,
        master: Any,
        service: LibraryService,
        on_open_artist: Callable[[int], None],
        on_navigate: Optional[Callable[[str], None]] = None,
        **kwargs,
    ):
        super().__init__(master, fg_color=theme.BG_APP, corner_radius=0, **kwargs)
        self.service = service
        self.on_open_artist = on_open_artist
        self.on_navigate = on_navigate

        self.current_query = ""
        self.current_role: str = "all"  # 'all', 'singer', 'music_director', 'actor'
        self.current_page = 1
        self.page_size = 18
        self.sort_by = "name"
        self.sort_ascending = True
        self._search_debounce_id: Optional[str] = None
        self._current_artists: List[Dict[str, Any]] = []
        self._total_artists: int = 0

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
            text="👥  ARTISTS & PEOPLE",
            font=theme.font_hero(),
            text_color=theme.TEXT_PRIMARY,
        ).pack(side="left")

        ctk.CTkLabel(
            hdr_box,
            text="Singers • Composers • Actors",
            font=theme.font_caption(),
            text_color=theme.TEXT_MUTED,
        ).pack(side="left", padx=(10, 0), pady=(4, 0))

        # Header Right: Search
        header_right = ctk.CTkFrame(header, fg_color="transparent")
        header_right.pack(side="right", padx=20, pady=10)

        search_box = ctk.CTkFrame(header_right, fg_color="transparent")
        search_box.pack(side="left", padx=(0, 10))

        self.search_var = tk.StringVar()
        self.search_entry = ctk.CTkEntry(
            search_box,
            textvariable=self.search_var,
            placeholder_text="Search artist, composer, or actor…",
            width=260,
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

        # ── 2. Filter & Sort Bar ─────────────────────────────────────
        filter_bar = ctk.CTkFrame(self, height=44, corner_radius=0, fg_color=theme.SURFACE)
        filter_bar.grid(row=1, column=0, sticky="ew")
        filter_bar.grid_propagate(False)

        fb_left = ctk.CTkFrame(filter_bar, fg_color="transparent")
        fb_left.pack(side="left", padx=20, pady=6)

        # Role Segmented Buttons
        self.role_buttons: Dict[str, ctk.CTkButton] = {}
        roles_spec = [
            ("all", "All People"),
            ("singer", "🎤 Singers"),
            ("music_director", "🎼 Music Directors"),
            ("actor", "🎬 Actors"),
        ]
        for role_key, label in roles_spec:
            btn = ctk.CTkButton(
                fb_left,
                text=label,
                height=28,
                width=110 if role_key != "all" else 85,
                font=theme.font_caption_bold() if role_key == "all" else theme.font_caption(),
                fg_color=theme.PRIMARY if role_key == "all" else theme.SURFACE_ELEVATED,
                hover_color=theme.PRIMARY_HOVER if role_key == "all" else theme.SURFACE_HOVER,
                corner_radius=theme.RADIUS_SM,
                command=lambda r=role_key: self._on_role_select(r),
            )
            btn.pack(side="left", padx=2)
            self.role_buttons[role_key] = btn

        # Sort Dropdown
        ctk.CTkLabel(
            fb_left,
            text="Sort:",
            font=theme.font_caption_bold(),
            text_color=theme.TEXT_MUTED,
        ).pack(side="left", padx=(14, 6))

        self.sort_var = tk.StringVar(value="Name (A-Z)")
        self.sort_menu = ctk.CTkOptionMenu(
            fb_left,
            variable=self.sort_var,
            values=[
                "Name (A-Z)",
                "Name (Z-A)",
                "Most Songs",
                "Most Movies",
                "Most Downloaded",
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
            text="Loading artists…",
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
            width=85,
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

    # ── Actions & Event Handlers ─────────────────────────────────────

    def refresh(self) -> None:
        """Reload artists page from database."""
        self.load_page(self.current_page)

    def _on_role_select(self, role: str) -> None:
        """Filter by role."""
        if self.current_role == role:
            return
        self.current_role = role
        for k, btn in self.role_buttons.items():
            if k == role:
                btn.configure(fg_color=theme.PRIMARY, hover_color=theme.PRIMARY_HOVER, font=theme.font_caption_bold())
            else:
                btn.configure(fg_color=theme.SURFACE_ELEVATED, hover_color=theme.SURFACE_HOVER, font=theme.font_caption())
        self.current_page = 1
        self.load_page(1)

    def _on_search_keyrelease(self, _event: tk.Event) -> None:
        """Debounce search key strokes (250ms)."""
        if self._search_debounce_id:
            self.after_cancel(self._search_debounce_id)
        self._search_debounce_id = self.after(250, self._on_search)

    def _on_search(self) -> None:
        """Execute search."""
        query = self.search_var.get().strip()
        if query == self.current_query and self.current_page == 1:
            return
        self.current_query = query
        self.current_page = 1
        self.load_page(1)

    def _clear_search(self) -> None:
        """Clear search input."""
        self.search_var.set("")
        self.current_query = ""
        self.current_page = 1
        self.load_page(1)

    def _on_sort_change(self, choice: str) -> None:
        """Handle sort menu selection."""
        sort_map = {
            "Name (A-Z)": ("name", True),
            "Name (Z-A)": ("name", False),
            "Most Songs": ("songs", False),
            "Most Movies": ("movies", False),
            "Most Downloaded": ("downloaded", False),
        }
        sb, asc = sort_map.get(choice, ("name", True))
        self.sort_by = sb
        self.sort_ascending = asc
        self.current_page = 1
        self.load_page(1)

    def _go_page(self, page_num: int) -> None:
        """Navigate to specific page."""
        max_pages = max(1, (self._total_artists + self.page_size - 1) // self.page_size)
        target = max(1, min(page_num, max_pages))
        if target != self.current_page:
            self.current_page = target
            self.load_page(target)

    def _go_last_page(self) -> None:
        """Navigate to the final page."""
        max_pages = max(1, (self._total_artists + self.page_size - 1) // self.page_size)
        self._go_page(max_pages)

    # ── Data Loading & Card Rendering ────────────────────────────────

    def load_page(self, page_num: int) -> None:
        """Fetch and render paginated artists."""
        role_filter = None if self.current_role == "all" else self.current_role
        artists, total_count = self.service.get_artists_page(
            query=self.current_query,
            role=role_filter,
            sort_by=self.sort_by,
            ascending=self.sort_ascending,
            page=page_num,
            page_size=self.page_size,
        )
        self._current_artists = artists
        self._total_artists = total_count
        self.current_page = page_num

        self._render_pagination(total_count, page_num)
        self._render_cards(artists)

    def _render_pagination(self, total_count: int, page_num: int) -> None:
        """Update pagination controls and label."""
        total_pages = max(1, (total_count + self.page_size - 1) // self.page_size)
        self.page_indicator.configure(text=f"Page {page_num} of {total_pages}")
        self.count_label.configure(text=f"Found {total_count} {'person' if total_count == 1 else 'people'}")

        self.btn_first.configure(state="normal" if page_num > 1 else "disabled")
        self.btn_prev.configure(state="normal" if page_num > 1 else "disabled")
        self.btn_next.configure(state="normal" if page_num < total_pages else "disabled")
        self.btn_last.configure(state="normal" if page_num < total_pages else "disabled")

    def _render_cards(self, artists: List[Dict[str, Any]]) -> None:
        """Render artist cards in scrollable grid."""
        for widget in self.cards_scroll.winfo_children():
            widget.destroy()

        if not artists:
            self._render_empty_state()
            return

        for idx, artist_data in enumerate(artists):
            row = idx // 3
            col = idx % 3
            card = self._create_artist_card(self.cards_scroll, artist_data)
            card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")

    def _render_empty_state(self) -> None:
        """Display friendly empty state when no artists match."""
        container = ctk.CTkFrame(self.cards_scroll, fg_color="transparent")
        container.grid(row=0, column=0, columnspan=3, pady=60, sticky="nsew")

        ctk.CTkLabel(
            container,
            text="👥",
            font=ctk.CTkFont(size=48),
        ).pack(pady=(0, 10))

        msg = "No artists or personnel found."
        if self.current_query:
            msg = f"No people found matching '{self.current_query}'."

        ctk.CTkLabel(
            container,
            text=msg,
            font=theme.font_subtitle(),
            text_color=theme.TEXT_PRIMARY,
        ).pack(pady=(0, 6))

        ctk.CTkLabel(
            container,
            text="Try adjusting your search query, selecting 'All People', or discovering new music.",
            font=theme.font_caption(),
            text_color=theme.TEXT_MUTED,
        ).pack(pady=(0, 16))

        if self.current_query or self.current_role != "all":
            ctk.CTkButton(
                container,
                text="Reset Filters",
                width=120,
                height=32,
                font=theme.font_body_bold(),
                fg_color=theme.PRIMARY,
                hover_color=theme.PRIMARY_HOVER,
                corner_radius=theme.RADIUS_MD,
                command=lambda: [self._clear_search(), self._on_role_select("all")],
            ).pack()

    def _create_artist_card(self, parent: Any, data: Dict[str, Any]) -> ctk.CTkFrame:
        """Create a polished artist card widget."""
        card = ctk.CTkFrame(
            parent,
            fg_color=theme.SURFACE,
            corner_radius=theme.RADIUS_LG,
            border_color=theme.BORDER,
            border_width=1,
        )

        # Hover feedback
        card.bind("<Enter>", lambda e: card.configure(border_color=theme.BORDER_LIGHT))
        card.bind("<Leave>", lambda e: card.configure(border_color=theme.BORDER))

        artist_id = data["id"]
        artist_name = data.get("name", "Unknown Artist")
        roles = data.get("roles", [])
        roles_display = data.get("roles_display", "Artist")

        # Top Bar: Avatar icon and Name
        top_bar = ctk.CTkFrame(card, fg_color="transparent")
        top_bar.pack(fill="x", padx=14, pady=(12, 6))

        icon_frame = ctk.CTkFrame(
            top_bar,
            width=42,
            height=42,
            corner_radius=theme.RADIUS_MD,
            fg_color=theme.SURFACE_ELEVATED,
        )
        icon_frame.pack(side="left", padx=(0, 10))
        icon_frame.pack_propagate(False)

        img_src = data.get("image_url")
        icon_lbl = ctk.CTkLabel(icon_frame, text="")
        icon_lbl.pack(expand=True, fill="both")
        self.service.artwork.bind_artwork(
            widget=icon_lbl,
            source=img_src,
            size=(42, 42),
            entity_type="artist",
            fallback_text=artist_name,
        )

        name_box = ctk.CTkFrame(top_bar, fg_color="transparent")
        name_box.pack(side="left", fill="both", expand=True)

        ctk.CTkLabel(
            name_box,
            text=data["name"],
            font=theme.font_body_bold(),
            text_color=theme.TEXT_PRIMARY,
            anchor="w",
        ).pack(anchor="w")

        ctk.CTkLabel(
            name_box,
            text=roles_display,
            font=theme.font_caption(),
            text_color=theme.PRIMARY_LIGHT,
            anchor="w",
        ).pack(anchor="w")

        # Middle Metrics
        metrics_frame = ctk.CTkFrame(card, fg_color=theme.SURFACE_ELEVATED, corner_radius=theme.RADIUS_SM)
        metrics_frame.pack(fill="x", padx=14, pady=6)

        tot_songs = data.get("total_songs", 0)
        dl_songs = data.get("downloaded_songs", 0)
        tot_movies = data.get("total_movies", 0)

        ctk.CTkLabel(
            metrics_frame,
            text=f"🎵 {tot_songs} Songs   •   🎬 {tot_movies} Movies",
            font=theme.font_caption(),
            text_color=theme.TEXT_SECONDARY,
        ).pack(side="left", padx=10, pady=5)

        # Download Badge
        if tot_songs > 0 and dl_songs >= tot_songs:
            badge_text = "✓ Downloaded"
            badge_fg = theme.SUCCESS_LIGHT
            badge_bg = theme.SUCCESS_BG
        elif dl_songs > 0:
            badge_text = f"{dl_songs}/{tot_songs} Saved"
            badge_fg = theme.PRIMARY_LIGHT
            badge_bg = theme.SURFACE_MUTED
        else:
            badge_text = f"{tot_songs} Tracks"
            badge_fg = theme.TEXT_MUTED
            badge_bg = theme.SURFACE_MUTED

        badge = ctk.CTkFrame(metrics_frame, fg_color=badge_bg, corner_radius=theme.RADIUS_SM)
        badge.pack(side="right", padx=6, pady=4)
        ctk.CTkLabel(
            badge,
            text=badge_text,
            font=theme.font_caption_bold(),
            text_color=badge_fg,
        ).pack(padx=6, pady=2)

        # Bottom: Navigation Action Button
        btn_action = ctk.CTkButton(
            card,
            text="Inspect Person  ›",
            height=30,
            font=theme.font_caption_bold(),
            fg_color=theme.SURFACE_ELEVATED,
            hover_color=theme.SURFACE_HOVER,
            text_color=theme.TEXT_PRIMARY,
            corner_radius=theme.RADIUS_MD,
            command=lambda: self.on_open_artist(artist_id),
        )
        btn_action.pack(fill="x", padx=14, pady=(6, 12))

        # Make entire card clickable
        for child in [card, top_bar, name_box]:
            child.bind("<Button-1>", lambda _e, aid=artist_id: self.on_open_artist(aid))

        return card
