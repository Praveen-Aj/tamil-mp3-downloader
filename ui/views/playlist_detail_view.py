"""
Detailed Tracklist & Management View for a User Playlist.
Phase V5.6: Playlists, Ratings, Favorites, and External URL Import.
"""

from __future__ import annotations

import math
import os
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog
from typing import Any, Callable, Dict, List, Optional

import customtkinter as ctk

from ui import theme
from ui.services.library_service import LibraryService, DownloadProgressEvent


class PlaylistDetailView(ctk.CTkFrame):
    """
    Detailed Tracklist and Management View for a User Playlist.
    Supports track reordering, add/remove songs, ratings, favorites, and download planning.
    """

    def __init__(
        self,
        master: Any,
        service: LibraryService,
        on_back: Callable[[], None],
        on_open_artist: Optional[Callable[[int], None]] = None,
        on_open_movie: Optional[Callable[[int], None]] = None,
        on_start_downloads: Optional[Callable[[List[int]], None]] = None,
        **kwargs,
    ):
        super().__init__(master, fg_color=theme.BG_APP, corner_radius=0, **kwargs)
        self.service = service
        self.on_back = on_back
        self.on_open_artist = on_open_artist
        self.on_open_movie = on_open_movie
        self.on_start_downloads = on_start_downloads

        self.playlist_id: Optional[int] = None
        self._playlist_data: Optional[Dict[str, Any]] = None
        self._current_items: List[Dict[str, Any]] = []
        self.search_query: str = ""
        self.current_page: int = 1
        self.page_size: int = 50
        self._total_matching: int = 0

        self._status_labels: Dict[int, ctk.CTkLabel] = {}
        self._action_buttons: Dict[int, ctk.CTkButton] = {}

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._init_ui()

        # Subscribe to download progress events
        if hasattr(self.service, "event_bus") and self.service.event_bus:
            self.service.event_bus.subscribe(DownloadProgressEvent, self._on_download_progress)

    def _init_ui(self) -> None:
        # ── 1. Top Header & Hero Card ────────────────────────────────
        self.header_frame = ctk.CTkFrame(self, fg_color=theme.SURFACE_CARD, corner_radius=0)
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        self.header_frame.grid_columnconfigure(1, weight=1)

        # Back button row
        top_nav = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        top_nav.pack(fill="x", padx=24, pady=(16, 8))

        back_btn = ctk.CTkButton(
            top_nav,
            text="← Back to Playlists",
            font=theme.font_caption_bold(),
            fg_color="transparent",
            hover_color=theme.SURFACE_MUTED,
            text_color=theme.PRIMARY_LIGHT,
            width=140,
            height=28,
            anchor="w",
            command=self.on_back,
        )
        back_btn.pack(side="left")

        # Hero content row
        hero_row = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        hero_row.pack(fill="x", padx=24, pady=(0, 16))

        # Icon / Cover
        icon_box = ctk.CTkFrame(
            hero_row,
            width=64,
            height=64,
            fg_color=theme.PRIMARY_MUTED,
            corner_radius=theme.RADIUS_MD,
        )
        icon_box.pack(side="left", padx=(0, 16))
        icon_box.pack_propagate(False)

        icon_lbl = ctk.CTkLabel(icon_box, text="📑", font=ctk.CTkFont(size=30))
        icon_lbl.place(relx=0.5, rely=0.5, anchor="center")

        # Titles
        info_col = ctk.CTkFrame(hero_row, fg_color="transparent")
        info_col.pack(side="left", fill="both", expand=True)

        self.title_label = ctk.CTkLabel(
            info_col,
            text="Playlist Title",
            font=theme.font_title(),
            text_color=theme.TEXT_PRIMARY,
            anchor="w",
        )
        self.title_label.pack(anchor="w")

        self.desc_label = ctk.CTkLabel(
            info_col,
            text="Playlist Description",
            font=theme.font_caption(),
            text_color=theme.TEXT_MUTED,
            anchor="w",
        )
        self.desc_label.pack(anchor="w", pady=(2, 0))

        # Stats Chips
        stats_col = ctk.CTkFrame(hero_row, fg_color="transparent")
        stats_col.pack(side="right", padx=(12, 0))

        chips_box = ctk.CTkFrame(stats_col, fg_color="transparent")
        chips_box.pack(anchor="e", pady=(0, 10))

        self.chip_tracks = ctk.CTkLabel(
            chips_box,
            text="0 Tracks",
            font=theme.font_caption_bold(),
            text_color=theme.TEXT_PRIMARY,
        )
        self.chip_tracks.pack(side="left", padx=8)

        self.chip_downloaded = ctk.CTkLabel(
            chips_box,
            text="✓ 0 Downloaded",
            font=theme.font_caption_bold(),
            text_color=theme.SUCCESS,
        )
        self.chip_downloaded.pack(side="left", padx=8)

        self.chip_missing = ctk.CTkLabel(
            chips_box,
            text="0 Missing",
            font=theme.font_caption_bold(),
            text_color=theme.WARNING,
        )
        self.chip_missing.pack(side="left", padx=8)

        # Action Buttons Row
        actions_box = ctk.CTkFrame(stats_col, fg_color="transparent")
        actions_box.pack(anchor="e")

        self.add_songs_btn = ctk.CTkButton(
            actions_box,
            text="➕ Add Songs",
            font=theme.font_caption_bold(),
            fg_color=theme.SURFACE,
            hover_color=theme.SURFACE_MUTED,
            text_color=theme.TEXT_PRIMARY,
            height=30,
            width=100,
            command=self._prompt_add_songs,
        )
        self.add_songs_btn.pack(side="left", padx=4)

        self.rename_btn = ctk.CTkButton(
            actions_box,
            text="✏ Rename",
            font=theme.font_caption_bold(),
            fg_color=theme.SURFACE,
            hover_color=theme.SURFACE_MUTED,
            text_color=theme.TEXT_PRIMARY,
            height=30,
            width=80,
            command=self._prompt_rename,
        )
        self.rename_btn.pack(side="left", padx=4)

        self.dl_missing_btn = ctk.CTkButton(
            actions_box,
            text="⬇ Download Missing",
            font=theme.font_button(),
            fg_color=theme.PRIMARY,
            hover_color=theme.PRIMARY_HOVER,
            text_color=theme.TEXT_PRIMARY,
            height=30,
            width=140,
            command=self._on_download_missing_clicked,
        )
        self.dl_missing_btn.pack(side="left", padx=4)

        self.dl_all_btn = ctk.CTkButton(
            actions_box,
            text="⚡ Download All",
            font=theme.font_caption_bold(),
            fg_color=theme.SURFACE,
            hover_color=theme.SURFACE_MUTED,
            text_color=theme.TEXT_PRIMARY,
            height=30,
            width=110,
            command=self._on_download_all_clicked,
        )
        self.dl_all_btn.pack(side="left", padx=4)

        # ── 2. In-Playlist Filter & Search Bar ───────────────────────
        filter_bar = ctk.CTkFrame(self, fg_color="transparent")
        filter_bar.grid(row=1, column=0, sticky="ew", padx=24, pady=(12, 6))
        filter_bar.grid_columnconfigure(0, weight=1)

        self.counter_lbl = ctk.CTkLabel(
            filter_bar,
            text="Showing 0 tracks",
            font=theme.font_caption(),
            text_color=theme.TEXT_MUTED,
        )
        self.counter_lbl.grid(row=0, column=0, sticky="w")

        self.search_entry = ctk.CTkEntry(
            filter_bar,
            placeholder_text="Filter tracks in playlist...",
            font=theme.font_body(),
            fg_color=theme.SURFACE_CARD,
            text_color=theme.TEXT_PRIMARY,
            border_color=theme.BORDER,
            width=260,
            height=30,
        )
        self.search_entry.grid(row=0, column=1, sticky="e")
        self.search_entry.bind("<KeyRelease>", self._on_search_key)

        # ── 3. Scrollable Tracklist Table ────────────────────────────
        self.table_scroll = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            corner_radius=0,
        )
        self.table_scroll.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 8))
        self.grid_rowconfigure(2, weight=1)

        # ── 4. Pagination Footer ─────────────────────────────────────
        self.footer = ctk.CTkFrame(self, fg_color=theme.BG_SIDEBAR, height=44, corner_radius=0)
        self.footer.grid(row=3, column=0, sticky="ew")

        self.footer_info = ctk.CTkLabel(
            self.footer,
            text="Page 1",
            font=theme.font_caption(),
            text_color=theme.TEXT_MUTED,
        )
        self.footer_info.pack(side="left", padx=20, pady=8)

        nav_btns = ctk.CTkFrame(self.footer, fg_color="transparent")
        nav_btns.pack(side="right", padx=20, pady=8)

        self.first_btn = ctk.CTkButton(nav_btns, text="« First", width=55, height=26, font=theme.font_caption(), fg_color=theme.SURFACE_CARD, command=lambda: self._go_page(1))
        self.first_btn.pack(side="left", padx=2)

        self.prev_btn = ctk.CTkButton(nav_btns, text="‹ Prev", width=55, height=26, font=theme.font_caption(), fg_color=theme.SURFACE_CARD, command=lambda: self._go_page(self.current_page - 1))
        self.prev_btn.pack(side="left", padx=2)

        self.page_lbl = ctk.CTkLabel(nav_btns, text="1 / 1", font=theme.font_caption_bold(), width=50, text_color=theme.TEXT_PRIMARY)
        self.page_lbl.pack(side="left", padx=4)

        self.next_btn = ctk.CTkButton(nav_btns, text="Next ›", width=55, height=26, font=theme.font_caption(), fg_color=theme.SURFACE_CARD, command=lambda: self._go_page(self.current_page + 1))
        self.next_btn.pack(side="left", padx=2)

        self.last_btn = ctk.CTkButton(nav_btns, text="Last »", width=55, height=26, font=theme.font_caption(), fg_color=theme.SURFACE_CARD, command=self._go_last_page)
        self.last_btn.pack(side="left", padx=2)

    def load_playlist(self, playlist_id: int) -> None:
        """Load and display a specific playlist."""
        self.playlist_id = playlist_id
        self.current_page = 1
        self.search_query = ""
        self.search_entry.delete(0, "end")
        self.refresh()

    def refresh(self) -> None:
        """Fetch playlist details and items synchronously and render immediately."""
        if not self.playlist_id:
            return
        details = self.service.get_playlist_details(
            playlist_id=self.playlist_id,
            query=self.search_query,
            page=self.current_page,
            page_size=self.page_size,
        )
        self._apply_playlist_details(details)

    def _apply_playlist_details(self, details: Optional[Dict[str, Any]]) -> None:
        if not details:
            self.title_label.configure(text="Playlist Not Found")
            return

        self._playlist_data = details
        pl = details["playlist"]
        stats = details["stats"]
        items = details["items"]
        total_matching = details["total_matching"]

        self._current_items = items
        self._total_matching = total_matching

        self.title_label.configure(text=pl.name)
        self.desc_label.configure(text=pl.description or "Custom User Playlist")

        tot = stats["total_songs"]
        dl = stats["downloaded_songs"]
        miss = stats["missing_songs"]

        self.chip_tracks.configure(text=f"{tot} Tracks")
        self.chip_downloaded.configure(text=f"✓ {dl} Downloaded")
        self.chip_missing.configure(text=f"{miss} Missing")

        self.counter_lbl.configure(text=f"Showing {len(items)} of {total_matching} tracks in playlist")

        # Clear existing table rows
        for w in self.table_scroll.winfo_children():
            w.destroy()
        self._status_labels.clear()
        self._action_buttons.clear()

        if not items:
            self._render_empty_tracklist()
            self._update_pagination(0)
            return

        self._render_table_header()
        for item in items:
            self._render_track_row(item)

        self._update_pagination(total_matching)

    def _render_table_header(self) -> None:
        hdr = ctk.CTkFrame(self.table_scroll, fg_color=theme.SURFACE, height=32, corner_radius=theme.RADIUS_SM)
        hdr.pack(fill="x", padx=4, pady=(0, 4))
        hdr.grid_columnconfigure(3, weight=2)
        hdr.grid_columnconfigure(4, weight=2)
        hdr.grid_columnconfigure(5, weight=2)

        ctk.CTkLabel(hdr, text="#", font=theme.font_caption_bold(), text_color=theme.TEXT_MUTED, width=32).grid(row=0, column=0, padx=4)
        ctk.CTkLabel(hdr, text="Order", font=theme.font_caption_bold(), text_color=theme.TEXT_MUTED, width=44).grid(row=0, column=1, padx=2)
        ctk.CTkLabel(hdr, text="Fav", font=theme.font_caption_bold(), text_color=theme.TEXT_MUTED, width=36).grid(row=0, column=2, padx=2)
        ctk.CTkLabel(hdr, text="Title", font=theme.font_caption_bold(), text_color=theme.TEXT_MUTED, anchor="w").grid(row=0, column=3, sticky="ew", padx=6)
        ctk.CTkLabel(hdr, text="Artist", font=theme.font_caption_bold(), text_color=theme.TEXT_MUTED, anchor="w").grid(row=0, column=4, sticky="ew", padx=6)
        ctk.CTkLabel(hdr, text="Movie / Album", font=theme.font_caption_bold(), text_color=theme.TEXT_MUTED, anchor="w").grid(row=0, column=5, sticky="ew", padx=6)
        ctk.CTkLabel(hdr, text="Rating", font=theme.font_caption_bold(), text_color=theme.TEXT_MUTED, width=80).grid(row=0, column=6, padx=4)
        ctk.CTkLabel(hdr, text="Status", font=theme.font_caption_bold(), text_color=theme.TEXT_MUTED, width=105).grid(row=0, column=7, padx=4)
        ctk.CTkLabel(hdr, text="Action", font=theme.font_caption_bold(), text_color=theme.TEXT_MUTED, width=80).grid(row=0, column=8, padx=4)
        ctk.CTkLabel(hdr, text="", width=28).grid(row=0, column=9, padx=2)  # remove button

    def _render_track_row(self, item: Dict[str, Any]) -> None:
        row = ctk.CTkFrame(
            self.table_scroll,
            fg_color=theme.SURFACE_CARD,
            corner_radius=theme.RADIUS_SM,
            border_width=1,
            border_color=theme.BORDER,
            height=38,
        )
        row.pack(fill="x", padx=4, pady=2)
        row.grid_columnconfigure(3, weight=2)
        row.grid_columnconfigure(4, weight=2)
        row.grid_columnconfigure(5, weight=2)

        s_id = item["song_id"]
        pos = item["position"]

        # 0: Position
        ctk.CTkLabel(
            row, text=str(pos), font=theme.font_caption_bold(), text_color=theme.TEXT_MUTED, width=32,
        ).grid(row=0, column=0, padx=4)

        # 1: Order Up/Down buttons
        order_box = ctk.CTkFrame(row, fg_color="transparent", width=44)
        order_box.grid(row=0, column=1, padx=2)

        up_btn = ctk.CTkButton(
            order_box, text="▲", font=ctk.CTkFont(size=9), width=20, height=18,
            fg_color="transparent", hover_color=theme.SURFACE_MUTED, text_color=theme.TEXT_MUTED,
            command=lambda sid=s_id: self._move_item(sid, "up"),
        )
        up_btn.pack(side="left", padx=1)

        down_btn = ctk.CTkButton(
            order_box, text="▼", font=ctk.CTkFont(size=9), width=20, height=18,
            fg_color="transparent", hover_color=theme.SURFACE_MUTED, text_color=theme.TEXT_MUTED,
            command=lambda sid=s_id: self._move_item(sid, "down"),
        )
        down_btn.pack(side="left", padx=1)

        # 2: Favorite
        is_fav = item.get("is_favorite", False)
        fav_btn = ctk.CTkButton(
            row,
            text="❤️" if is_fav else "🤍",
            font=theme.font_caption(),
            fg_color="transparent",
            hover_color=theme.SURFACE_MUTED,
            width=32,
            height=26,
            command=lambda sid=s_id: self._toggle_favorite(sid),
        )
        fav_btn.grid(row=0, column=2, padx=2)

        # 3: Title
        t_text = item.get("title", "Unknown Title")
        ctk.CTkLabel(
            row,
            text=t_text[:32] + ("..." if len(t_text) > 32 else ""),
            font=theme.font_body_bold(),
            text_color=theme.TEXT_PRIMARY,
            anchor="w",
        ).grid(row=0, column=3, sticky="ew", padx=6)

        # 4: Artist link
        a_name = item.get("artist", "Unknown Artist")
        a_id = item.get("artist_id")
        if a_id and self.on_open_artist:
            ctk.CTkButton(
                row,
                text=a_name[:22] + ("..." if len(a_name) > 22 else ""),
                font=theme.font_caption(),
                text_color=theme.PRIMARY_LIGHT,
                fg_color="transparent",
                hover_color=theme.PRIMARY_MUTED,
                anchor="w",
                command=lambda aid=a_id: self.on_open_artist(aid),
            ).grid(row=0, column=4, sticky="ew", padx=4)
        else:
            ctk.CTkLabel(
                row,
                text=a_name[:22] + ("..." if len(a_name) > 22 else ""),
                font=theme.font_caption(),
                text_color=theme.TEXT_MUTED,
                anchor="w",
            ).grid(row=0, column=4, sticky="ew", padx=6)

        # 5: Movie / Album link
        m_name = item.get("album", "Unknown")
        m_id = item.get("movie_id")
        if m_id and self.on_open_movie:
            ctk.CTkButton(
                row,
                text=m_name[:20] + ("..." if len(m_name) > 20 else ""),
                font=theme.font_caption(),
                text_color=theme.PRIMARY_LIGHT,
                fg_color="transparent",
                hover_color=theme.PRIMARY_MUTED,
                anchor="w",
                command=lambda mid=m_id: self.on_open_movie(mid),
            ).grid(row=0, column=5, sticky="ew", padx=4)
        else:
            ctk.CTkLabel(
                row,
                text=m_name[:20] + ("..." if len(m_name) > 20 else ""),
                font=theme.font_caption(),
                text_color=theme.TEXT_MUTED,
                anchor="w",
            ).grid(row=0, column=5, sticky="ew", padx=6)

        # 6: Rating Stars
        rating = item.get("rating") or 0
        stars_text = "★" * rating + "☆" * (5 - rating)
        star_btn = ctk.CTkButton(
            row,
            text=stars_text,
            font=ctk.CTkFont(size=11),
            text_color=theme.WARNING if rating > 0 else theme.TEXT_MUTED,
            fg_color="transparent",
            hover_color=theme.SURFACE_MUTED,
            width=78,
            height=24,
            command=lambda sid=s_id, r=rating: self._cycle_rating(sid, r),
        )
        star_btn.grid(row=0, column=6, padx=4)

        # 7: Status
        is_dl = item.get("is_downloaded", False)
        status_lbl = ctk.CTkLabel(
            row,
            text="✓ Downloaded" if is_dl else "Not Downloaded",
            font=theme.font_badge(),
            text_color=theme.SUCCESS if is_dl else theme.TEXT_MUTED,
            width=105,
        )
        status_lbl.grid(row=0, column=7, padx=4)
        self._status_labels[s_id] = status_lbl

        # 8: Action: Play or Download
        f_path = item.get("file_path")
        action_btn = ctk.CTkButton(
            row,
            text="▶ Play" if is_dl else "⬇ Download",
            font=theme.font_caption_bold(),
            fg_color=theme.PRIMARY_MUTED if is_dl else theme.PRIMARY,
            hover_color=theme.PRIMARY if is_dl else theme.PRIMARY_HOVER,
            text_color=theme.TEXT_PRIMARY,
            height=26,
            width=76,
            command=lambda sid=s_id, dl=is_dl, fp=f_path: self._on_row_action(sid, dl, fp),
        )
        action_btn.grid(row=0, column=8, padx=4)
        self._action_buttons[s_id] = action_btn

        # 9: Remove from playlist button
        remove_btn = ctk.CTkButton(
            row,
            text="✖",
            font=ctk.CTkFont(size=11),
            fg_color="transparent",
            hover_color=theme.ERROR,
            text_color=theme.TEXT_MUTED,
            width=24,
            height=24,
            command=lambda sid=s_id: self._remove_item(sid),
        )
        remove_btn.grid(row=0, column=9, padx=2)

    def _render_empty_tracklist(self) -> None:
        frame = ctk.CTkFrame(self.table_scroll, fg_color="transparent")
        frame.pack(pady=60)

        ctk.CTkLabel(frame, text="🎵", font=ctk.CTkFont(size=44)).pack(pady=(0, 8))
        ctk.CTkLabel(frame, text="No Tracks in Playlist", font=theme.font_subtitle(), text_color=theme.TEXT_PRIMARY).pack()
        ctk.CTkLabel(frame, text="Click '➕ Add Songs' above to add tracks from your music library.", font=theme.font_caption(), text_color=theme.TEXT_MUTED).pack(pady=4)

    def _update_pagination(self, total: int) -> None:
        max_page = max(1, math.ceil(total / self.page_size))
        self.page_lbl.configure(text=f"{self.current_page} / {max_page}")

        self.first_btn.configure(state="normal" if self.current_page > 1 else "disabled")
        self.prev_btn.configure(state="normal" if self.current_page > 1 else "disabled")
        self.next_btn.configure(state="normal" if self.current_page < max_page else "disabled")
        self.last_btn.configure(state="normal" if self.current_page < max_page else "disabled")

    def _go_page(self, page: int) -> None:
        max_page = max(1, math.ceil(self._total_matching / self.page_size))
        target = max(1, min(page, max_page))
        if target != self.current_page:
            self.current_page = target
            self.refresh()

    def _go_last_page(self) -> None:
        max_page = max(1, math.ceil(self._total_matching / self.page_size))
        self._go_page(max_page)

    def _on_search_key(self, event=None) -> None:
        q = self.search_entry.get().strip()
        if q != self.search_query:
            self.search_query = q
            self.current_page = 1
            self.refresh()

    def _move_item(self, song_id: int, direction: str) -> None:
        if not self.playlist_id:
            return
        if self.service.move_playlist_song(self.playlist_id, song_id, direction):
            self.refresh()

    def _toggle_favorite(self, song_id: int) -> None:
        self.service.toggle_favorite(song_id)
        self.refresh()

    def _cycle_rating(self, song_id: int, current_rating: int) -> None:
        next_r = 5 if current_rating == 0 else (current_rating - 1)
        self.service.rate_song(song_id, next_r if next_r > 0 else None)
        self.refresh()

    def _remove_item(self, song_id: int) -> None:
        if not self.playlist_id:
            return
        if self.service.remove_song_from_playlist(self.playlist_id, song_id):
            self.refresh()

    def _on_row_action(self, song_id: int, is_dl: bool, file_path: Optional[str]) -> None:
        if is_dl and file_path:
            ok, msg = self.service.play_audio_file(file_path)
            if not ok:
                messagebox.showwarning("Playback", msg, parent=self)
        else:
            plan = self.service.plan_playlist_entry_download(self.playlist_id, song_id)
            if plan.new_songs:
                enqueued = self.service.execute_download_plan(plan, run_async=True)
                if song_id in self._status_labels:
                    self._status_labels[song_id].configure(text="⏳ Downloading...", text_color=theme.WARNING)
                if self.on_start_downloads and enqueued:
                    try:
                        self.after(0, lambda: self.on_start_downloads(enqueued))
                    except Exception:
                        pass

    def _on_download_missing_clicked(self) -> None:
        if not self.playlist_id:
            return
        plan = self.service.plan_playlist_download_missing(self.playlist_id)
        if not plan.new_songs:
            messagebox.showinfo("All Downloaded", "All tracks in this playlist are already downloaded!", parent=self)
            return

        enqueued = self.service.execute_download_plan(plan, run_async=True)
        self.dl_missing_btn.configure(state="disabled", text="Downloading...")
        for planned in plan.new_songs:
            if planned.song_id in self._status_labels:
                self._status_labels[planned.song_id].configure(text="⏳ Queued", text_color=theme.INFO_LIGHT)

        if self.on_start_downloads and enqueued:
            try:
                self.after(0, lambda: self.on_start_downloads(enqueued))
            except Exception:
                pass

    def _on_download_all_clicked(self) -> None:
        if not self.playlist_id:
            return
        plan = self.service.plan_playlist_download_all(self.playlist_id)
        if not plan.new_songs and not plan.upgrades:
            messagebox.showinfo("All Downloaded", "All tracks in this playlist are already downloaded at target quality!", parent=self)
            return

        enqueued = self.service.execute_download_plan(plan, run_async=True)
        self.dl_all_btn.configure(state="disabled", text="Downloading...")
        if self.on_start_downloads and enqueued:
            try:
                self.after(0, lambda: self.on_start_downloads(enqueued))
            except Exception:
                pass

    def _on_download_progress(self, event: DownloadProgressEvent) -> None:
        """Live progress updates for items in this playlist."""
        if not event.song_id:
            return

        def update():
            sid = event.song_id
            if sid in self._status_labels:
                lbl = self._status_labels[sid]
                if event.status == "COMPLETED":
                    lbl.configure(text="✓ Downloaded", text_color=theme.SUCCESS)
                    if sid in self._action_buttons:
                        self._action_buttons[sid].configure(text="▶ Play", fg_color=theme.PRIMARY_MUTED)
                elif event.status == "DOWNLOADING":
                    pct = int((event.percent or 0) * 100)
                    lbl.configure(text=f"⏳ {pct}%", text_color=theme.WARNING)
                elif event.status == "FAILED":
                    lbl.configure(text="✗ Failed", text_color=theme.ERROR)

        try:
            if self.winfo_exists():
                self.after(0, update)
        except Exception:
            pass

    def _prompt_rename(self) -> None:
        if not self._playlist_data:
            return
        pl = self._playlist_data["playlist"]
        name = simpledialog.askstring("Rename Playlist", "Enter new name:", initialvalue=pl.name, parent=self)
        if not name or not name.strip():
            return
        desc = simpledialog.askstring("Update Description", "Enter description:", initialvalue=pl.description or "", parent=self)
        self.service.update_playlist(self.playlist_id, name=name.strip(), description=desc.strip() if desc else None)
        self.refresh()

    def _prompt_add_songs(self) -> None:
        """Dialog allowing user to select songs from library to add to this playlist."""
        if not self.playlist_id:
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("Add Songs to Playlist")
        dialog.geometry("600x500")
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="Select Songs from Library", font=theme.font_subtitle()).pack(pady=(16, 8))

        # Search bar in dialog
        search_var = tk.StringVar()
        search_entry = ctk.CTkEntry(dialog, placeholder_text="Search songs by title or artist...", textvariable=search_var, width=400)
        search_entry.pack(pady=4)

        # Scrollable check list
        list_frame = ctk.CTkScrollableFrame(dialog, width=540, height=320)
        list_frame.pack(padx=20, pady=8, fill="both", expand=True)

        all_songs = self.service.db.list_songs()
        existing_song_ids = {item["song_id"] for item in self._current_items}
        check_vars: Dict[int, tk.BooleanVar] = {}

        def populate(filter_txt=""):
            for w in list_frame.winfo_children():
                w.destroy()
            check_vars.clear()
            f = filter_txt.strip().lower()
            count = 0
            for s in all_songs:
                if s.id in existing_song_ids:
                    continue
                if f and f not in s.title.lower() and f not in (s.artist or "").lower():
                    continue
                var = tk.BooleanVar(value=False)
                check_vars[s.id] = var
                cb = ctk.CTkCheckBox(
                    list_frame,
                    text=f"{s.title} — {s.artist or 'Unknown'} ({s.album or 'Single'})",
                    variable=var,
                    font=theme.font_caption(),
                )
                cb.pack(anchor="w", padx=8, pady=3)
                count += 1
                if count >= 100:  # limit rendering to top 100 matching
                    break

        populate()
        search_entry.bind("<KeyRelease>", lambda e: populate(search_var.get()))

        def on_add():
            selected_ids = [sid for sid, var in check_vars.items() if var.get()]
            if selected_ids:
                added = self.service.add_songs_to_playlist(self.playlist_id, selected_ids)
                messagebox.showinfo("Songs Added", f"Added {added} songs to playlist!", parent=dialog)
                self.refresh()
            dialog.destroy()

        btn_box = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_box.pack(pady=12)

        ctk.CTkButton(btn_box, text="Cancel", width=90, fg_color=theme.SURFACE_CARD, command=dialog.destroy).pack(side="left", padx=6)
        ctk.CTkButton(btn_box, text="Add Selected", width=120, fg_color=theme.PRIMARY, command=on_add).pack(side="left", padx=6)
