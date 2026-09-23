"""
Dedicated Downloaded Songs View.

Displays exclusively songs that have been successfully downloaded and verified to exist
as physical audio files on disk. Provides instant Playback, Explorer revelation,
bulk selection, and safe destructive/unlink deletion.
"""

import logging
import os
import tkinter as tk
from typing import Optional, Dict, Any, List, Callable, Set
from tkinter import messagebox
from pathlib import Path
import customtkinter as ctk

from library.models import LibrarySong, SongState
from library.filter_engine import SongFilterCriteria
from ui.services.library_service import LibraryService
from ui import theme

logger = logging.getLogger(__name__)


class DownloadedSongsView(ctk.CTkFrame):
    """
    Dedicated view for verified locally downloaded songs.
    """

    def __init__(
        self,
        master: Any,
        service: LibraryService,
        on_navigate_add_music: Optional[Callable[[], None]] = None,
        **kwargs
    ):
        super().__init__(master, fg_color="transparent", corner_radius=0, **kwargs)
        self.service = service
        self.on_navigate_add_music = on_navigate_add_music

        self._songs: List[LibrarySong] = []
        self._sort_by: str = "recent"
        self._search_query: str = ""
        self._selected_ids: Set[int] = set()
        self.current_page: int = 1
        self.page_size: int = 20
        self.total_count: int = 0
        self.total_pages: int = 1

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._build_ui()

    def _build_ui(self) -> None:
        """Construct view layout."""
        # ── 1. Top Header ───────────────────────────────────────────
        header = ctk.CTkFrame(self, height=64, corner_radius=0, fg_color=theme.BG_HEADER)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)

        hdr_box = ctk.CTkFrame(header, fg_color="transparent")
        hdr_box.pack(side="left", padx=24, pady=12)

        ctk.CTkLabel(
            hdr_box,
            text="🎵  DOWNLOADED SONGS",
            font=theme.font_hero(),
            text_color=theme.TEXT_PRIMARY,
        ).pack(side="left")

        ctk.CTkLabel(
            hdr_box,
            text="Your Offline Music Collection",
            font=theme.font_caption(),
            text_color=theme.TEXT_MUTED,
        ).pack(side="left", padx=16, pady=(4, 0))

        # Top Right Actions
        hdr_right = ctk.CTkFrame(header, fg_color="transparent")
        hdr_right.pack(side="right", padx=20, pady=12)

        self.summary_pill = ctk.CTkLabel(
            hdr_right,
            text="0 Songs · 0 MB",
            font=theme.font_caption_bold(),
            text_color=theme.SUCCESS_LIGHT,
            fg_color=theme.SUCCESS_BG,
            corner_radius=8,
            padx=12,
            pady=4,
        )
        self.summary_pill.pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            hdr_right,
            text="📁 Open Downloads Folder",
            font=theme.font_caption_bold(),
            height=32,
            width=160,
            fg_color=theme.SURFACE_ELEVATED,
            hover_color=theme.SURFACE_HOVER,
            text_color=theme.TEXT_PRIMARY,
            corner_radius=theme.RADIUS_MD,
            command=lambda: self.service.open_path_in_explorer(str(self.service.download_dir)),
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            hdr_right,
            text="🔄 Refresh",
            font=theme.font_caption_bold(),
            height=32,
            width=80,
            fg_color=theme.SURFACE_ELEVATED,
            hover_color=theme.SURFACE_HOVER,
            text_color=theme.TEXT_SECONDARY,
            corner_radius=theme.RADIUS_MD,
            command=self.refresh,
        ).pack(side="left", padx=4)

        # ── 2. Filter & Sort & Bulk Toolbar ─────────────────────────
        toolbar = ctk.CTkFrame(self, fg_color=theme.SURFACE, corner_radius=theme.RADIUS_MD, border_width=1, border_color=theme.BORDER)
        toolbar.grid(row=1, column=0, sticky="ew", padx=24, pady=(14, 10))

        tb_inner = ctk.CTkFrame(toolbar, fg_color="transparent")
        tb_inner.pack(fill="x", padx=16, pady=10)

        # Search box
        self.search_entry = ctk.CTkEntry(
            tb_inner,
            placeholder_text="Filter downloaded music by title, artist, or movie...",
            height=32,
            width=280,
            font=theme.font_caption(),
            fg_color=theme.SURFACE_MUTED,
            border_color=theme.BORDER,
        )
        self.search_entry.pack(side="left")
        self.search_entry.bind("<KeyRelease>", lambda e: self._on_search_changed())

        # Sort Dropdown
        ctk.CTkLabel(
            tb_inner,
            text="Sort By:",
            font=theme.font_caption_bold(),
            text_color=theme.TEXT_MUTED,
        ).pack(side="left", padx=(14, 6))

        self.sort_var = tk.StringVar(value="Recently Downloaded")
        sort_menu = ctk.CTkOptionMenu(
            tb_inner,
            values=["Recently Downloaded", "Title (A-Z)", "Artist (A-Z)", "Album (A-Z)", "Highest Quality"],
            variable=self.sort_var,
            font=theme.font_caption(),
            height=32,
            width=160,
            fg_color=theme.SURFACE_ELEVATED,
            button_color=theme.SURFACE_HOVER,
            command=self._on_sort_changed,
        )
        sort_menu.pack(side="left")

        # Bulk Actions Container (Right side of toolbar)
        self.bulk_container = ctk.CTkFrame(tb_inner, fg_color="transparent")
        self.bulk_container.pack(side="right")

        self.select_all_btn = ctk.CTkButton(
            self.bulk_container,
            text="Select All",
            font=theme.font_caption(),
            height=30,
            width=80,
            fg_color=theme.SURFACE_ELEVATED,
            hover_color=theme.SURFACE_HOVER,
            text_color=theme.TEXT_SECONDARY,
            command=self._toggle_select_all,
        )
        self.select_all_btn.pack(side="left", padx=4)

        self.bulk_delete_btn = ctk.CTkButton(
            self.bulk_container,
            text="🗑️ Delete Selected",
            font=theme.font_caption_bold(),
            height=30,
            width=120,
            fg_color=theme.ERROR,
            hover_color=theme.SURFACE_HOVER,
            text_color=theme.TEXT_PRIMARY,
            state="disabled",
            command=self._confirm_bulk_delete,
        )
        self.bulk_delete_btn.pack(side="left", padx=4)

        # ── 3. Songs List Container (Scrollable) ────────────────────
        self.list_container = ctk.CTkFrame(self, fg_color="transparent")
        self.list_container.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0, 6))
        self.list_container.grid_columnconfigure(0, weight=1)
        self.list_container.grid_rowconfigure(0, weight=1)

        # ── 4. Bottom Pagination Bar ─────────────────────────────────
        self.pagination_bar = ctk.CTkFrame(self, height=44, corner_radius=0, fg_color=theme.BG_HEADER)
        self.pagination_bar.grid(row=3, column=0, sticky="ew")
        self.pagination_bar.grid_propagate(False)

        self.count_label = ctk.CTkLabel(
            self.pagination_bar,
            text="",
            font=theme.font_caption(),
            text_color=theme.TEXT_MUTED,
        )
        self.count_label.pack(side="left", padx=20, pady=10)

        nav_btns = ctk.CTkFrame(self.pagination_bar, fg_color="transparent")
        nav_btns.pack(side="right", padx=20, pady=6)

        self.btn_first = ctk.CTkButton(
            nav_btns, text="« First", width=65, height=28,
            font=theme.font_caption(), fg_color=theme.SURFACE_ELEVATED,
            hover_color=theme.SURFACE_HOVER, corner_radius=theme.RADIUS_SM,
            command=lambda: self._go_page(1)
        )
        self.btn_first.pack(side="left", padx=3)

        self.btn_prev = ctk.CTkButton(
            nav_btns, text="‹ Prev", width=65, height=28,
            font=theme.font_caption(), fg_color=theme.SURFACE_ELEVATED,
            hover_color=theme.SURFACE_HOVER, corner_radius=theme.RADIUS_SM,
            command=lambda: self._go_page(self.current_page - 1)
        )
        self.btn_prev.pack(side="left", padx=3)

        self.page_indicator = ctk.CTkLabel(
            nav_btns, text="Page 1 of 1",
            font=theme.font_body_bold(), text_color=theme.TEXT_PRIMARY
        )
        self.page_indicator.pack(side="left", padx=10)

        self.btn_next = ctk.CTkButton(
            nav_btns, text="Next ›", width=65, height=28,
            font=theme.font_caption(), fg_color=theme.SURFACE_ELEVATED,
            hover_color=theme.SURFACE_HOVER, corner_radius=theme.RADIUS_SM,
            command=lambda: self._go_page(self.current_page + 1)
        )
        self.btn_next.pack(side="left", padx=3)

        self.btn_last = ctk.CTkButton(
            nav_btns, text="Last »", width=65, height=28,
            font=theme.font_caption(), fg_color=theme.SURFACE_ELEVATED,
            hover_color=theme.SURFACE_HOVER, corner_radius=theme.RADIUS_SM,
            command=self._go_last_page
        )
        self.btn_last.pack(side="left", padx=3)

        self.refresh()

    def _go_page(self, page_num: int) -> None:
        """Navigate to specific page."""
        target = max(1, min(page_num, self.total_pages))
        if target != self.current_page:
            self.current_page = target
            self.refresh()

    def _go_last_page(self) -> None:
        """Navigate to last page."""
        self._go_page(self.total_pages)

    def refresh(self) -> None:
        """Fetch updated downloaded songs using SQL pagination and re-render."""
        sort_key_map = {
            "Recently Downloaded": ("id", False),
            "Title (A-Z)": ("title", True),
            "Artist (A-Z)": ("artist", True),
            "Album (A-Z)": ("album", True),
            "Highest Quality": ("quality", False),
        }
        sort_col, ascending = sort_key_map.get(self.sort_var.get(), ("id", False))

        # Overall summary stats
        with self.service.db._lock:
            cursor = self.service.db._conn.cursor()
            cursor.execute("SELECT COUNT(*), SUM(file_size_bytes) FROM songs WHERE state = 'OWNED'")
            stat_row = cursor.fetchone()
            overall_cnt = stat_row[0] or 0
            overall_bytes = stat_row[1] or 0

        if overall_bytes >= 1024 * 1024:
            storage_str = f"{overall_bytes / (1024 * 1024):.1f} MB"
        elif overall_bytes > 0:
            storage_str = f"{overall_bytes / 1024:.1f} KB"
        else:
            storage_str = "0 MB"
        self.summary_pill.configure(text=f"{overall_cnt} Downloaded · {storage_str}")

        # Centralized SQL search and pagination
        result = self.service.db.search_and_filter_songs(
            criteria=SongFilterCriteria(
                download_state=SongState.OWNED,
                search_query=self._search_query if self._search_query else None,
            ),
            sort_by=sort_col,
            ascending=ascending,
            page=self.current_page,
            page_size=self.page_size,
        )
        self._songs = result.get("songs", [])
        self.total_count = result.get("total_items", 0)
        self.total_pages = max(1, result.get("total_pages", 1))

        # Update pagination controls
        self.page_indicator.configure(text=f"Page {self.current_page} of {self.total_pages}")
        self.count_label.configure(text=f"Found {self.total_count} {'song' if self.total_count == 1 else 'songs'}")
        self.btn_first.configure(state="normal" if self.current_page > 1 else "disabled")
        self.btn_prev.configure(state="normal" if self.current_page > 1 else "disabled")
        self.btn_next.configure(state="normal" if self.current_page < self.total_pages else "disabled")
        self.btn_last.configure(state="normal" if self.current_page < self.total_pages else "disabled")

        # Clean selected ids of removed songs
        valid_ids = {s.id for s in self._songs if s.id is not None}
        self._selected_ids = self._selected_ids.intersection(valid_ids)

        self._render_content()

    def _on_search_changed(self) -> None:
        self._search_query = self.search_entry.get().strip()
        self.current_page = 1
        self.refresh()

    def _on_sort_changed(self, choice: str) -> None:
        self.current_page = 1
        self.refresh()

    def _toggle_select_all(self) -> None:
        if len(self._selected_ids) == len(self._songs) and self._songs:
            self._selected_ids.clear()
            self.select_all_btn.configure(text="Select All")
        else:
            self._selected_ids = {s.id for s in self._songs if s.id is not None}
            self.select_all_btn.configure(text="Clear Selection")
        self._update_bulk_buttons()
        self._render_content()

    def _update_bulk_buttons(self) -> None:
        count = len(self._selected_ids)
        if count > 0:
            self.bulk_delete_btn.configure(state="normal", text=f"🗑️ Delete ({count})")
        else:
            self.bulk_delete_btn.configure(state="disabled", text="🗑️ Delete Selected")

    def _toggle_song_selection(self, song_id: int) -> None:
        if song_id in self._selected_ids:
            self._selected_ids.remove(song_id)
        else:
            self._selected_ids.add(song_id)
        self._update_bulk_buttons()

    def _render_content(self) -> None:
        """Render either empty state or list of downloaded songs."""
        for w in self.list_container.winfo_children():
            w.destroy()

        self._update_bulk_buttons()

        if not self._songs:
            self._render_empty_state()
            return

        scroll = ctk.CTkScrollableFrame(
            self.list_container,
            fg_color="transparent",
            corner_radius=0,
        )
        scroll.pack(fill="both", expand=True)
        scroll.grid_columnconfigure(0, weight=1)

        for song in self._songs:
            self._render_song_row(scroll, song)

    def _render_empty_state(self) -> None:
        """Render empty state when no songs are downloaded yet."""
        empty_card = ctk.CTkFrame(
            self.list_container,
            corner_radius=theme.RADIUS_LG,
            fg_color=theme.SURFACE,
            border_width=1,
            border_color=theme.BORDER,
        )
        empty_card.pack(fill="both", expand=True)

        center = ctk.CTkFrame(empty_card, fg_color="transparent")
        center.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(center, text="🎧", font=ctk.CTkFont(size=52)).pack(pady=(0, 12))

        ctk.CTkLabel(
            center,
            text="No Downloaded Songs Yet",
            font=theme.font_title(),
            text_color=theme.TEXT_PRIMARY,
        ).pack()

        ctk.CTkLabel(
            center,
            text="Songs you download from YouTube, Spotify, or Tamil sources will appear here with verified offline playback.",
            font=theme.font_body(),
            text_color=theme.TEXT_MUTED,
            justify="center",
        ).pack(pady=(6, 18))

        if self.on_navigate_add_music:
            ctk.CTkButton(
                center,
                text="⚡ Add & Download Music",
                font=theme.font_body_bold(),
                height=38,
                width=200,
                fg_color=theme.PRIMARY,
                hover_color=theme.PRIMARY_HOVER,
                text_color=theme.TEXT_PRIMARY,
                corner_radius=theme.RADIUS_MD,
                command=self.on_navigate_add_music,
            ).pack()

    def _render_song_row(self, parent: ctk.CTkScrollableFrame, song: LibrarySong) -> None:
        """Render an individual downloaded song row."""
        is_selected = song.id in self._selected_ids
        card = ctk.CTkFrame(
            parent,
            fg_color=theme.SURFACE_ELEVATED if is_selected else theme.SURFACE,
            corner_radius=theme.RADIUS_MD,
            border_width=1,
            border_color=theme.PRIMARY if is_selected else theme.BORDER,
        )
        card.pack(fill="x", pady=4)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=10)

        # Checkbox
        chk_var = tk.BooleanVar(value=is_selected)
        chk = ctk.CTkCheckBox(
            inner,
            text="",
            variable=chk_var,
            width=24,
            checkbox_width=18,
            checkbox_height=18,
            corner_radius=4,
            command=lambda s_id=song.id: self._toggle_song_selection(s_id),
        )
        chk.pack(side="left", padx=(0, 10))

        # Left: Cover icon
        cover_box = ctk.CTkFrame(
            inner,
            width=44,
            height=44,
            corner_radius=theme.RADIUS_SM,
            fg_color=theme.SURFACE_ELEVATED,
        )
        cover_box.pack(side="left", padx=(0, 14))
        cover_box.pack_propagate(False)

        cover_lbl = ctk.CTkLabel(cover_box, text="")
        cover_lbl.pack(expand=True, fill="both")
        self.service.artwork.bind_artwork(
            widget=cover_lbl,
            source=getattr(song, "file_path", None),
            size=(44, 44),
            entity_type="song",
            fallback_text=song.title,
        )

        if not is_selected:
            card.bind("<Enter>", lambda e, c=card: c.configure(border_color=theme.BORDER_LIGHT))
            card.bind("<Leave>", lambda e, c=card: c.configure(border_color=theme.BORDER))

        # Right Actions (Pack first to guarantee layout space)
        act_box = ctk.CTkFrame(inner, fg_color="transparent")
        act_box.pack(side="right", padx=(8, 0))

        # Play button
        ctk.CTkButton(
            act_box,
            text="▶ Play",
            font=theme.font_caption_bold(),
            height=32,
            width=70,
            fg_color=theme.SUCCESS,
            hover_color=theme.SUCCESS_BG,
            text_color=theme.TEXT_PRIMARY,
            corner_radius=theme.RADIUS_SM,
            command=lambda s=song: self._play_song(s),
        ).pack(side="left", padx=3)

        # Open folder
        ctk.CTkButton(
            act_box,
            text="📁 Folder",
            font=theme.font_caption_bold(),
            height=32,
            width=70,
            fg_color=theme.SURFACE_ELEVATED,
            hover_color=theme.SURFACE_HOVER,
            text_color=theme.TEXT_SECONDARY,
            corner_radius=theme.RADIUS_SM,
            command=lambda p=song.file_path: self.service.open_path_in_explorer(p),
        ).pack(side="left", padx=3)

        # Delete button
        ctk.CTkButton(
            act_box,
            text="🗑️",
            font=theme.font_body(),
            height=32,
            width=34,
            fg_color=theme.SURFACE_ELEVATED,
            hover_color=theme.ERROR,
            text_color=theme.TEXT_MUTED,
            corner_radius=theme.RADIUS_SM,
            command=lambda s=song: self._delete_single_song(s),
        ).pack(side="left", padx=3)

        # Status Tag
        status_badge = ctk.CTkLabel(
            inner,
            text="✓ Downloaded",
            font=theme.font_badge(),
            text_color=theme.SUCCESS_LIGHT,
            fg_color=theme.SUCCESS_BG,
            corner_radius=6,
            padx=8,
            pady=3,
        )
        status_badge.pack(side="right", padx=8)

        # Mid-Left: Title, Artist, Album, Bitrate (Expands to fill remaining center)
        info_box = ctk.CTkFrame(inner, fg_color="transparent")
        info_box.pack(side="left", fill="both", expand=True)

        ctk.CTkLabel(
            info_box,
            text=song.title,
            font=theme.font_subtitle(),
            text_color=theme.TEXT_PRIMARY,
            anchor="w",
        ).pack(anchor="w")

        # Determine format/codec from file extension or path
        ext = os.path.splitext(song.file_path or "")[1].lower()
        if ext == ".webm":
            fmt_codec = "Opus (WebM)"
            default_kbps = 160
        elif ext == ".m4a":
            fmt_codec = "AAC (M4A)"
            default_kbps = 128
        elif ext == ".mp3":
            fmt_codec = "MP3"
            default_kbps = 320
        else:
            fmt_codec = (ext.replace(".", "").upper() if ext else "Audio")
            default_kbps = song.quality_kbps or 320

        artist_text = song.artist or "Unknown Artist"
        album_text = f" · {song.album}" if song.album else ""
        quality_text = f" · {fmt_codec} · {song.quality_kbps or default_kbps} kbps"
        
        size_bytes = song.file_size_bytes or 0
        if not size_bytes and song.file_path and os.path.isfile(song.file_path):
            try:
                size_bytes = os.path.getsize(song.file_path)
            except OSError:
                pass
        if size_bytes >= 1024 * 1024:
            size_str = f" · {size_bytes / (1024 * 1024):.1f} MB"
        elif size_bytes > 0:
            size_str = f" · {size_bytes / 1024:.1f} KB"
        else:
            size_str = ""
        dur_str = f" · {song.duration_seconds // 60}:{song.duration_seconds % 60:02d}" if song.duration_seconds else ""

        meta_line = f"{artist_text}{album_text}{quality_text}{dur_str}{size_str}"
        ctk.CTkLabel(
            info_box,
            text=meta_line,
            font=theme.font_caption(),
            text_color=theme.TEXT_MUTED,
            anchor="w",
        ).pack(anchor="w", pady=(2, 0))

    def _play_song(self, song: LibrarySong) -> None:
        """Launch the song in the system audio player with verification."""
        if not song.file_path or not os.path.isfile(song.file_path):
            messagebox.showwarning(
                "File Missing",
                f"The downloaded file for '{song.title}' was not found on your computer.\n\n"
                f"Path: {song.file_path or 'Empty'}\n\n"
                "Please download the track again."
            )
            self.refresh()
            return

        ok, msg = self.service.play_audio_file(song.file_path)
        if not ok:
            messagebox.showwarning("Playback", msg)

    def _confirm_delete(self, song: LibrarySong) -> None:
        """Prompt confirmation dialog with choice to delete file from disk or remove from library."""
        msg = (
            f"How would you like to delete '{song.title}'?\n\n"
            "• Yes: Permanently Delete File from computer disk\n"
            "• No: Remove from Library only (keep physical file)\n"
            "• Cancel: Keep song"
        )
        response = messagebox.askyesnocancel("Delete Downloaded Song", msg, icon="question")
        if response is None:
            return  # Cancel

        delete_physical = bool(response)  # True if Yes, False if No
        success = self.service.delete_downloaded_song(song.id, delete_physical_file=delete_physical)
        if success:
            self.refresh()
        else:
            messagebox.showerror("Error", f"Failed to delete '{song.title}'.")

    def _confirm_bulk_delete(self) -> None:
        """Perform bulk deletion of selected songs."""
        if not self._selected_ids:
            return

        count = len(self._selected_ids)
        msg = (
            f"Delete {count} selected downloaded songs?\n\n"
            "• Yes: Permanently Delete Files from computer disk\n"
            "• No: Remove from Library only (keep physical files)\n"
            "• Cancel: Do nothing"
        )
        response = messagebox.askyesnocancel(f"Bulk Delete ({count} Songs)", msg, icon="warning")
        if response is None:
            return

        delete_physical = bool(response)
        for song_id in list(self._selected_ids):
            self.service.delete_downloaded_song(song_id, delete_physical_file=delete_physical)

        self._selected_ids.clear()
        self.refresh()
