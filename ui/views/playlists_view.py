"""
Playlists and User Personalization (Favorites, Ratings) View for Desktop Application.
Phase V5.6: Playlists, Ratings, Favorites, and External URL Import.
"""

from __future__ import annotations

import math
import tkinter as tk
from tkinter import messagebox, simpledialog
from typing import Any, Callable, Dict, List, Optional

import customtkinter as ctk

from ui import theme
from ui.services.library_service import LibraryService


class PlaylistsView(ctk.CTkFrame):
    """
    Main Playlists & Personalization View.
    Provides tabs: 'My Playlists', '⭐ Favorites', and '🌟 Top Rated'.
    """

    def __init__(
        self,
        master: Any,
        service: LibraryService,
        on_open_playlist: Callable[[int], None],
        on_navigate: Optional[Callable[[str], None]] = None,
        on_open_artist: Optional[Callable[[int], None]] = None,
        on_open_movie: Optional[Callable[[int], None]] = None,
        **kwargs,
    ):
        super().__init__(master, fg_color=theme.BG_APP, corner_radius=0, **kwargs)
        self.service = service
        self.on_open_playlist = on_open_playlist
        self.on_navigate = on_navigate
        self.on_open_artist = on_open_artist
        self.on_open_movie = on_open_movie

        self.current_tab: str = "playlists"  # 'playlists', 'favorites', 'rated'
        self.current_query: str = ""
        self.current_page: int = 1
        self.page_size: int = 18  # 6 rows x 3 columns for cards, 18 for list
        self._total_items: int = 0
        self._current_data: List[Dict[str, Any]] = []

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._init_ui()

    def _init_ui(self) -> None:
        # ── 1. Top Header & Action Controls ──────────────────────────
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 10))
        header.grid_columnconfigure(1, weight=1)

        # Title
        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.grid(row=0, column=0, sticky="w")

        title_lbl = ctk.CTkLabel(
            title_box,
            text="📑 Playlists & Favorites",
            font=theme.font_title(),
            text_color=theme.TEXT_PRIMARY,
        )
        title_lbl.pack(anchor="w")

        # Top Right Actions: Create Playlist & Import URL
        actions_box = ctk.CTkFrame(header, fg_color="transparent")
        actions_box.grid(row=0, column=2, sticky="e")

        self.create_btn = ctk.CTkButton(
            actions_box,
            text="➕ Create Playlist",
            font=theme.font_button(),
            fg_color=theme.PRIMARY,
            hover_color=theme.PRIMARY_HOVER,
            text_color=theme.TEXT_PRIMARY,
            height=32,
            width=135,
            command=self._prompt_create_playlist,
        )
        self.create_btn.pack(side="left", padx=4)

        self.import_btn = ctk.CTkButton(
            actions_box,
            text="📥 Import URL",
            font=theme.font_button(),
            fg_color=theme.SURFACE_CARD,
            hover_color=theme.SURFACE_MUTED,
            text_color=theme.TEXT_PRIMARY,
            height=32,
            width=120,
            command=self._prompt_import_url,
        )
        self.import_btn.pack(side="left", padx=4)

        # ── Filter Tabs & Search Bar ─────────────────────────────────
        filter_bar = ctk.CTkFrame(self, fg_color="transparent")
        filter_bar.grid(row=1, column=0, sticky="ew", padx=24, pady=(4, 12))
        filter_bar.grid_columnconfigure(1, weight=1)

        # Tab Segmented Buttons
        tabs_box = ctk.CTkFrame(filter_bar, fg_color="transparent")
        tabs_box.grid(row=0, column=0, sticky="w")

        self.tab_playlists_btn = ctk.CTkButton(
            tabs_box,
            text="📑 My Playlists",
            font=theme.font_caption_bold(),
            fg_color=theme.PRIMARY,
            hover_color=theme.PRIMARY_HOVER,
            text_color=theme.TEXT_PRIMARY,
            height=30,
            width=120,
            command=lambda: self._set_tab("playlists"),
        )
        self.tab_playlists_btn.pack(side="left", padx=(0, 6))

        self.tab_favorites_btn = ctk.CTkButton(
            tabs_box,
            text="⭐ Favorites",
            font=theme.font_caption_bold(),
            fg_color=theme.SURFACE_CARD,
            hover_color=theme.SURFACE_MUTED,
            text_color=theme.TEXT_SECONDARY,
            height=30,
            width=110,
            command=lambda: self._set_tab("favorites"),
        )
        self.tab_favorites_btn.pack(side="left", padx=6)

        self.tab_rated_btn = ctk.CTkButton(
            tabs_box,
            text="🌟 Top Rated",
            font=theme.font_caption_bold(),
            fg_color=theme.SURFACE_CARD,
            hover_color=theme.SURFACE_MUTED,
            text_color=theme.TEXT_SECONDARY,
            height=30,
            width=110,
            command=lambda: self._set_tab("rated"),
        )
        self.tab_rated_btn.pack(side="left", padx=6)

        # Search Bar
        self.search_entry = ctk.CTkEntry(
            filter_bar,
            placeholder_text="Search playlists or songs...",
            font=theme.font_body(),
            fg_color=theme.SURFACE_CARD,
            text_color=theme.TEXT_PRIMARY,
            border_color=theme.BORDER,
            width=260,
            height=32,
        )
        self.search_entry.grid(row=0, column=2, sticky="e")
        self.search_entry.bind("<KeyRelease>", self._on_search_key)

        # ── 2. Scrollable Body Content ───────────────────────────────
        self.scroll_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            corner_radius=0,
        )
        self.scroll_frame.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 8))
        self.grid_rowconfigure(2, weight=1)

        # Configure 3 equal columns for playlist card view
        for i in range(3):
            self.scroll_frame.grid_columnconfigure(i, weight=1, uniform="playlist_grid")

        # ── 3. Pagination Footer ─────────────────────────────────────
        self.footer = ctk.CTkFrame(self, fg_color=theme.BG_SIDEBAR, height=44, corner_radius=0)
        self.footer.grid(row=3, column=0, sticky="ew")

        self.info_lbl = ctk.CTkLabel(
            self.footer,
            text="Showing 0 items",
            font=theme.font_caption(),
            text_color=theme.TEXT_MUTED,
        )
        self.info_lbl.pack(side="left", padx=20, pady=8)

        nav_btns = ctk.CTkFrame(self.footer, fg_color="transparent")
        nav_btns.pack(side="right", padx=20, pady=8)

        self.first_btn = ctk.CTkButton(
            nav_btns, text="« First", width=55, height=26,
            font=theme.font_caption(), fg_color=theme.SURFACE_CARD,
            command=lambda: self._go_page(1)
        )
        self.first_btn.pack(side="left", padx=2)

        self.prev_btn = ctk.CTkButton(
            nav_btns, text="‹ Prev", width=55, height=26,
            font=theme.font_caption(), fg_color=theme.SURFACE_CARD,
            command=lambda: self._go_page(self.current_page - 1)
        )
        self.prev_btn.pack(side="left", padx=2)

        self.page_num_lbl = ctk.CTkLabel(
            nav_btns, text="1 / 1", font=theme.font_caption_bold(), width=50,
            text_color=theme.TEXT_PRIMARY
        )
        self.page_num_lbl.pack(side="left", padx=4)

        self.next_btn = ctk.CTkButton(
            nav_btns, text="Next ›", width=55, height=26,
            font=theme.font_caption(), fg_color=theme.SURFACE_CARD,
            command=lambda: self._go_page(self.current_page + 1)
        )
        self.next_btn.pack(side="left", padx=2)

        self.last_btn = ctk.CTkButton(
            nav_btns, text="Last »", width=55, height=26,
            font=theme.font_caption(), fg_color=theme.SURFACE_CARD,
            command=self._go_last_page
        )
        self.last_btn.pack(side="left", padx=2)

        # Initial render
        self.refresh()

    def _set_tab(self, tab: str) -> None:
        if self.current_tab == tab:
            return
        self.current_tab = tab
        self.current_page = 1
        self.search_entry.delete(0, "end")
        self.current_query = ""

        # Update button highlights
        def _btn_style(btn, active):
            if active:
                btn.configure(fg_color=theme.PRIMARY, text_color=theme.TEXT_PRIMARY)
            else:
                btn.configure(fg_color=theme.SURFACE_CARD, text_color=theme.TEXT_SECONDARY)

        _btn_style(self.tab_playlists_btn, tab == "playlists")
        _btn_style(self.tab_favorites_btn, tab == "favorites")
        _btn_style(self.tab_rated_btn, tab == "rated")

        self.refresh()

    def _on_search_key(self, event=None) -> None:
        q = self.search_entry.get().strip()
        if q != self.current_query:
            self.current_query = q
            self.current_page = 1
            self.refresh()

    def _go_page(self, page: int) -> None:
        max_page = max(1, math.ceil(self._total_items / self.page_size))
        target = max(1, min(page, max_page))
        if target != self.current_page:
            self.current_page = target
            self.refresh()

    def _go_last_page(self) -> None:
        max_page = max(1, math.ceil(self._total_items / self.page_size))
        self._go_page(max_page)

    def refresh(self) -> None:
        """Fetch current tab page from SQLite and render immediately."""
        # Clear existing children in scroll frame
        for w in self.scroll_frame.winfo_children():
            w.destroy()

        if self.current_tab == "playlists":
            self._render_playlists_tab()
        elif self.current_tab == "favorites":
            self._render_favorites_tab()
        elif self.current_tab == "rated":
            self._render_rated_tab()

    def _render_playlists_tab(self) -> None:
        # Re-enable 3-column grid
        for i in range(3):
            self.scroll_frame.grid_columnconfigure(i, weight=1, uniform="playlist_grid")

        items, total = self.service.get_playlists_page(
            query=self.current_query,
            page=self.current_page,
            page_size=self.page_size,
        )
        self._current_data = items
        self._total_items = total

        if not items:
            self._render_empty_state("No Playlists Found", "Create a new playlist or import from Spotify/YouTube to begin.")
            self._update_pagination(0)
            return

        for idx, pl in enumerate(items):
            row = idx // 3
            col = idx % 3
            card = self._create_playlist_card(self.scroll_frame, pl)
            card.grid(row=row, column=col, sticky="nsew", padx=8, pady=8)

        self._update_pagination(total)

    def _create_playlist_card(self, parent: Any, pl: Dict[str, Any]) -> ctk.CTkFrame:
        card = ctk.CTkFrame(
            parent,
            fg_color=theme.SURFACE_CARD,
            corner_radius=theme.RADIUS_MD,
            border_width=1,
            border_color=theme.BORDER,
        )

        top_row = ctk.CTkFrame(card, fg_color="transparent")
        top_row.pack(fill="x", padx=14, pady=(14, 6))

        icon_lbl = ctk.CTkLabel(top_row, text="📑", font=ctk.CTkFont(size=22))
        icon_lbl.pack(side="left", padx=(0, 10))

        title_box = ctk.CTkFrame(top_row, fg_color="transparent")
        title_box.pack(side="left", fill="both", expand=True)

        name_text = pl.get("name", "Untitled Playlist")
        name_lbl = ctk.CTkLabel(
            title_box,
            text=name_text[:28] + ("..." if len(name_text) > 28 else ""),
            font=theme.font_subtitle(),
            text_color=theme.TEXT_PRIMARY,
            anchor="w",
        )
        name_lbl.pack(anchor="w")

        desc_text = pl.get("description") or "Custom User Playlist"
        desc_lbl = ctk.CTkLabel(
            title_box,
            text=desc_text[:35] + ("..." if len(desc_text) > 35 else ""),
            font=theme.font_caption(),
            text_color=theme.TEXT_MUTED,
            anchor="w",
        )
        desc_lbl.pack(anchor="w")

        # Stats Chips Row
        stats_box = ctk.CTkFrame(card, fg_color=theme.SURFACE, corner_radius=theme.RADIUS_SM)
        stats_box.pack(fill="x", padx=14, pady=8)

        tot = pl.get("total_songs", 0)
        dl = pl.get("downloaded_songs", 0)
        miss = pl.get("missing_songs", 0)

        ctk.CTkLabel(
            stats_box,
            text=f"🎵 {tot} Tracks",
            font=theme.font_caption_bold(),
            text_color=theme.TEXT_PRIMARY,
        ).pack(side="left", padx=12, pady=6)

        ctk.CTkLabel(
            stats_box,
            text=f"✓ {dl} Downloaded",
            font=theme.font_caption_bold(),
            text_color=theme.SUCCESS if dl > 0 else theme.TEXT_MUTED,
        ).pack(side="left", padx=8, pady=6)

        if miss > 0:
            ctk.CTkLabel(
                stats_box,
                text=f"⬇ {miss} Missing",
                font=theme.font_caption_bold(),
                text_color=theme.WARNING,
            ).pack(side="right", padx=12, pady=6)

        # Action Buttons
        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=14, pady=(6, 14))

        open_btn = ctk.CTkButton(
            btn_row,
            text="Open Playlist →",
            font=theme.font_caption_bold(),
            fg_color=theme.PRIMARY_MUTED,
            hover_color=theme.PRIMARY,
            text_color=theme.TEXT_PRIMARY,
            height=28,
            command=lambda pid=pl["id"]: self.on_open_playlist(pid),
        )
        open_btn.pack(side="left", fill="x", expand=True, padx=(0, 4))

        rename_btn = ctk.CTkButton(
            btn_row,
            text="✏",
            font=theme.font_caption(),
            fg_color=theme.SURFACE,
            hover_color=theme.SURFACE_MUTED,
            text_color=theme.TEXT_PRIMARY,
            width=30,
            height=28,
            command=lambda p=pl: self._prompt_rename_playlist(p),
        )
        rename_btn.pack(side="left", padx=2)

        del_btn = ctk.CTkButton(
            btn_row,
            text="🗑",
            font=theme.font_caption(),
            fg_color=theme.SURFACE,
            hover_color=theme.ERROR,
            text_color=theme.TEXT_MUTED,
            width=30,
            height=28,
            command=lambda pid=pl["id"], pn=pl["name"]: self._confirm_delete_playlist(pid, pn),
        )
        del_btn.pack(side="left", padx=2)

        return card

    def _render_favorites_tab(self) -> None:
        # Reset grid columns to single column list
        for i in range(3):
            self.scroll_frame.grid_columnconfigure(i, weight=0, uniform="")
        self.scroll_frame.grid_columnconfigure(0, weight=1)

        items, total = self.service.get_favorites_page(
            query=self.current_query,
            page=self.current_page,
            page_size=self.page_size,
        )
        self._current_data = items
        self._total_items = total

        if not items:
            self._render_empty_state("No Favorite Songs", "Mark songs with ❤️ in any view to collect them here.")
            self._update_pagination(0)
            return

        self._render_song_table_header()
        for idx, song in enumerate(items):
            row = self._create_song_row(self.scroll_frame, song, idx + 1)
            row.pack(fill="x", padx=4, pady=2)

        self._update_pagination(total)

    def _render_rated_tab(self) -> None:
        for i in range(3):
            self.scroll_frame.grid_columnconfigure(i, weight=0, uniform="")
        self.scroll_frame.grid_columnconfigure(0, weight=1)

        items, total = self.service.get_rated_songs_page(
            min_rating=1,
            query=self.current_query,
            page=self.current_page,
            page_size=self.page_size,
        )
        self._current_data = items
        self._total_items = total

        if not items:
            self._render_empty_state("No Rated Songs", "Rate songs 1-5 stars to curate your highest-rated music here.")
            self._update_pagination(0)
            return

        self._render_song_table_header()
        for idx, song in enumerate(items):
            row = self._create_song_row(self.scroll_frame, song, idx + 1)
            row.pack(fill="x", padx=4, pady=2)

        self._update_pagination(total)

    def _render_song_table_header(self) -> None:
        hdr = ctk.CTkFrame(self.scroll_frame, fg_color=theme.SURFACE, height=32, corner_radius=theme.RADIUS_SM)
        hdr.pack(fill="x", padx=4, pady=(0, 6))
        hdr.grid_columnconfigure(2, weight=2)
        hdr.grid_columnconfigure(3, weight=2)
        hdr.grid_columnconfigure(4, weight=2)

        ctk.CTkLabel(hdr, text="#", font=theme.font_caption_bold(), text_color=theme.TEXT_MUTED, width=40).grid(row=0, column=0, padx=6)
        ctk.CTkLabel(hdr, text="Fav", font=theme.font_caption_bold(), text_color=theme.TEXT_MUTED, width=40).grid(row=0, column=1, padx=4)
        ctk.CTkLabel(hdr, text="Title", font=theme.font_caption_bold(), text_color=theme.TEXT_MUTED, anchor="w").grid(row=0, column=2, sticky="ew", padx=8)
        ctk.CTkLabel(hdr, text="Artist", font=theme.font_caption_bold(), text_color=theme.TEXT_MUTED, anchor="w").grid(row=0, column=3, sticky="ew", padx=8)
        ctk.CTkLabel(hdr, text="Movie / Album", font=theme.font_caption_bold(), text_color=theme.TEXT_MUTED, anchor="w").grid(row=0, column=4, sticky="ew", padx=8)
        ctk.CTkLabel(hdr, text="Rating", font=theme.font_caption_bold(), text_color=theme.TEXT_MUTED, width=90).grid(row=0, column=5, padx=6)
        ctk.CTkLabel(hdr, text="Status", font=theme.font_caption_bold(), text_color=theme.TEXT_MUTED, width=110).grid(row=0, column=6, padx=6)
        ctk.CTkLabel(hdr, text="Action", font=theme.font_caption_bold(), text_color=theme.TEXT_MUTED, width=80).grid(row=0, column=7, padx=6)

    def _create_song_row(self, parent: Any, song: Dict[str, Any], display_index: int) -> ctk.CTkFrame:
        row = ctk.CTkFrame(
            parent,
            fg_color=theme.SURFACE_CARD,
            corner_radius=theme.RADIUS_SM,
            border_width=1,
            border_color=theme.BORDER,
            height=40,
        )
        row.grid_columnconfigure(2, weight=2)
        row.grid_columnconfigure(3, weight=2)
        row.grid_columnconfigure(4, weight=2)

        s_id = song["song_id"]

        # # Index
        ctk.CTkLabel(
            row, text=str(display_index),
            font=theme.font_caption(), text_color=theme.TEXT_MUTED, width=40,
        ).grid(row=0, column=0, padx=6)

        # Fav Heart Toggle
        is_fav = song.get("is_favorite", False)
        fav_btn = ctk.CTkButton(
            row,
            text="❤️" if is_fav else "🤍",
            font=theme.font_caption(),
            fg_color="transparent",
            hover_color=theme.SURFACE_MUTED,
            width=36,
            height=26,
            command=lambda sid=s_id: self._toggle_favorite_and_refresh(sid),
        )
        fav_btn.grid(row=0, column=1, padx=4)

        # Title
        t_text = song.get("title", "Unknown Title")
        ctk.CTkLabel(
            row,
            text=t_text[:35] + ("..." if len(t_text) > 35 else ""),
            font=theme.font_body_bold(),
            text_color=theme.TEXT_PRIMARY,
            anchor="w",
        ).grid(row=0, column=2, sticky="ew", padx=8)

        # Artist link
        a_name = song.get("artist", "Unknown Artist")
        a_id = song.get("artist_id")
        if a_id and self.on_open_artist:
            ctk.CTkButton(
                row,
                text=a_name[:24] + ("..." if len(a_name) > 24 else ""),
                font=theme.font_caption(),
                text_color=theme.PRIMARY_LIGHT,
                fg_color="transparent",
                hover_color=theme.PRIMARY_MUTED,
                anchor="w",
                command=lambda aid=a_id: self.on_open_artist(aid),
            ).grid(row=0, column=3, sticky="ew", padx=4)
        else:
            ctk.CTkLabel(
                row,
                text=a_name[:24] + ("..." if len(a_name) > 24 else ""),
                font=theme.font_caption(),
                text_color=theme.TEXT_MUTED,
                anchor="w",
            ).grid(row=0, column=3, sticky="ew", padx=8)

        # Movie / Album link
        m_name = song.get("album", "Unknown")
        m_id = song.get("movie_id")
        if m_id and self.on_open_movie:
            ctk.CTkButton(
                row,
                text=m_name[:22] + ("..." if len(m_name) > 22 else ""),
                font=theme.font_caption(),
                text_color=theme.PRIMARY_LIGHT,
                fg_color="transparent",
                hover_color=theme.PRIMARY_MUTED,
                anchor="w",
                command=lambda mid=m_id: self.on_open_movie(mid),
            ).grid(row=0, column=4, sticky="ew", padx=4)
        else:
            ctk.CTkLabel(
                row,
                text=m_name[:22] + ("..." if len(m_name) > 22 else ""),
                font=theme.font_caption(),
                text_color=theme.TEXT_MUTED,
                anchor="w",
            ).grid(row=0, column=4, sticky="ew", padx=8)

        # Rating Stars Box
        rating = song.get("rating") or 0
        stars_box = ctk.CTkFrame(row, fg_color="transparent", width=90)
        stars_box.grid(row=0, column=5, padx=6)

        stars_text = "★" * rating + "☆" * (5 - rating)
        star_btn = ctk.CTkButton(
            stars_box,
            text=stars_text,
            font=ctk.CTkFont(size=12),
            text_color=theme.WARNING if rating > 0 else theme.TEXT_MUTED,
            fg_color="transparent",
            hover_color=theme.SURFACE_MUTED,
            width=85,
            height=24,
            command=lambda sid=s_id, r=rating: self._cycle_rating_and_refresh(sid, r),
        )
        star_btn.pack()

        # Status
        is_dl = song.get("is_downloaded", False)
        status_lbl = ctk.CTkLabel(
            row,
            text="✓ Downloaded" if is_dl else "Not Downloaded",
            font=theme.font_badge(),
            text_color=theme.SUCCESS if is_dl else theme.TEXT_MUTED,
            width=110,
        )
        status_lbl.grid(row=0, column=6, padx=6)

        # Action Button: Play or Download
        f_path = song.get("file_path")
        action_btn = ctk.CTkButton(
            row,
            text="▶ Play" if is_dl else "⬇ Download",
            font=theme.font_caption_bold(),
            fg_color=theme.PRIMARY_MUTED if is_dl else theme.PRIMARY,
            hover_color=theme.PRIMARY if is_dl else theme.PRIMARY_HOVER,
            text_color=theme.TEXT_PRIMARY,
            height=26,
            width=78,
            command=lambda sid=s_id, dl=is_dl, fp=f_path: self._on_song_action(sid, dl, fp),
        )
        action_btn.grid(row=0, column=7, padx=6)

        return row

    def _toggle_favorite_and_refresh(self, song_id: int) -> None:
        self.service.toggle_favorite(song_id)
        self.refresh()

    def _cycle_rating_and_refresh(self, song_id: int, current_rating: int) -> None:
        """Cycle rating 0 -> 5 -> 4 -> 3 -> 2 -> 1 -> 0."""
        next_r = 5 if current_rating == 0 else (current_rating - 1)
        self.service.rate_song(song_id, next_r if next_r > 0 else None)
        self.refresh()

    def _on_song_action(self, song_id: int, is_dl: bool, file_path: Optional[str]) -> None:
        if is_dl and file_path:
            ok, msg = self.service.play_audio_file(file_path)
            if not ok:
                messagebox.showwarning("Playback", msg)
        else:
            plan = self.service.preview_download_plan(song_ids=[song_id])
            if plan.new_songs:
                self.service.execute_download_plan(plan, run_async=True)
                messagebox.showinfo("Downloading", f"Download started for song ID {song_id}!")
                self.refresh()

    def _render_empty_state(self, title: str, subtitle: str) -> None:
        frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        frame.grid(row=0, column=0, columnspan=3, pady=60)

        ctk.CTkLabel(frame, text="📁", font=ctk.CTkFont(size=48)).pack(pady=(0, 10))
        ctk.CTkLabel(frame, text=title, font=theme.font_subtitle(), text_color=theme.TEXT_PRIMARY).pack()
        ctk.CTkLabel(frame, text=subtitle, font=theme.font_caption(), text_color=theme.TEXT_MUTED).pack(pady=4)

    def _update_pagination(self, total: int) -> None:
        max_page = max(1, math.ceil(total / self.page_size))
        self.page_num_lbl.configure(text=f"{self.current_page} / {max_page}")

        start_idx = (self.current_page - 1) * self.page_size + 1 if total > 0 else 0
        end_idx = min(self.current_page * self.page_size, total)
        self.info_lbl.configure(text=f"Showing {start_idx}–{end_idx} of {total} items")

        self.first_btn.configure(state="normal" if self.current_page > 1 else "disabled")
        self.prev_btn.configure(state="normal" if self.current_page > 1 else "disabled")
        self.next_btn.configure(state="normal" if self.current_page < max_page else "disabled")
        self.last_btn.configure(state="normal" if self.current_page < max_page else "disabled")

    # ── Action Dialog Handlers ───────────────────────────────────────
    def _prompt_create_playlist(self) -> None:
        name = simpledialog.askstring("Create Playlist", "Enter playlist name:", parent=self)
        if not name or not name.strip():
            return
        desc = simpledialog.askstring("Create Playlist", "Enter description (optional):", parent=self) or ""
        pid = self.service.create_playlist(name=name.strip(), description=desc.strip())
        if pid:
            self.refresh()
            self.on_open_playlist(pid)

    def _prompt_rename_playlist(self, pl: Dict[str, Any]) -> None:
        new_name = simpledialog.askstring("Rename Playlist", "Enter new name:", initialvalue=pl["name"], parent=self)
        if not new_name or not new_name.strip():
            return
        new_desc = simpledialog.askstring("Update Description", "Enter description:", initialvalue=pl.get("description", ""), parent=self)
        self.service.update_playlist(pl["id"], name=new_name.strip(), description=new_desc.strip() if new_desc else None)
        self.refresh()

    def _confirm_delete_playlist(self, playlist_id: int, name: str) -> None:
        confirm = messagebox.askyesno(
            "Delete Playlist",
            f"Are you sure you want to delete '{name}'?\n\n(This will NOT delete any songs or downloaded files from disk.)",
            parent=self,
        )
        if confirm:
            self.service.delete_playlist(playlist_id)
            self.refresh()

    def _prompt_import_url(self) -> None:
        url = simpledialog.askstring("Import Playlist URL", "Enter Spotify, YouTube, or web playlist URL:", parent=self)
        if not url or not url.strip():
            return

        import threading
        self.import_btn.configure(state="disabled", text="Importing...")

        def worker():
            res = self.service.import_external_playlist(url.strip())
            def done():
                self.import_btn.configure(state="normal", text="📥 Import URL")
                if res.get("success"):
                    msg = f"Successfully imported '{res['playlist_name']}'!\n\nAdded {res['songs_added']} songs ({res['already_in_lib']} matched existing library songs)."
                    messagebox.showinfo("Import Successful", msg, parent=self)
                    self.refresh()
                    if res.get("playlist_id"):
                        self.on_open_playlist(res["playlist_id"])
                else:
                    err = res.get("error", "Failed to resolve playlist URL.")
                    messagebox.showerror("Import Error", f"Could not import playlist:\n{err}", parent=self)

            try:
                if self.winfo_exists():
                    self.after(0, done)
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()
