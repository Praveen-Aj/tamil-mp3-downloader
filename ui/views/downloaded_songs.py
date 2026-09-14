"""
Dedicated Downloaded Songs View.

Displays exclusively songs that have been successfully downloaded and verified to exist
as physical audio files on disk. Provides instant Playback, Explorer revelation,
and safe destructive deletion.
"""

import logging
import tkinter as tk
from typing import Optional, Dict, Any, List, Callable
from tkinter import messagebox
from pathlib import Path
import customtkinter as ctk

from library.models import LibrarySong
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
            text="📁 Open Music Folder",
            font=theme.font_caption_bold(),
            height=32,
            width=140,
            fg_color=theme.SURFACE_ELEVATED,
            hover_color=theme.SURFACE_HOVER,
            text_color=theme.TEXT_PRIMARY,
            corner_radius=theme.RADIUS_MD,
            command=lambda: self.service.open_path_in_explorer(None),
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

        # ── 2. Filter & Sort Toolbar ────────────────────────────────
        toolbar = ctk.CTkFrame(self, fg_color=theme.SURFACE, corner_radius=theme.RADIUS_MD, border_width=1, border_color=theme.BORDER)
        toolbar.grid(row=1, column=0, sticky="ew", padx=24, pady=(14, 10))

        tb_inner = ctk.CTkFrame(toolbar, fg_color="transparent")
        tb_inner.pack(fill="x", padx=16, pady=10)

        # Search box
        self.search_entry = ctk.CTkEntry(
            tb_inner,
            placeholder_text="Filter downloaded music by title, artist, or movie...",
            height=32,
            width=320,
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
        ).pack(side="left", padx=(18, 6))

        self.sort_var = tk.StringVar(value="Recently Downloaded")
        sort_menu = ctk.CTkOptionMenu(
            tb_inner,
            values=["Recently Downloaded", "Title (A-Z)", "Artist (A-Z)", "Album (A-Z)", "Highest Quality"],
            variable=self.sort_var,
            font=theme.font_caption(),
            height=32,
            width=180,
            fg_color=theme.SURFACE_ELEVATED,
            button_color=theme.SURFACE_HOVER,
            command=self._on_sort_changed,
        )
        sort_menu.pack(side="left")

        # ── 3. Songs List Container (Scrollable) ────────────────────
        self.list_container = ctk.CTkFrame(self, fg_color="transparent")
        self.list_container.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0, 16))
        self.list_container.grid_columnconfigure(0, weight=1)
        self.list_container.grid_rowconfigure(0, weight=1)

        self.refresh()

    def refresh(self) -> None:
        """Fetch updated downloaded songs and re-render."""
        sort_key_map = {
            "Recently Downloaded": "recent",
            "Title (A-Z)": "title",
            "Artist (A-Z)": "artist",
            "Album (A-Z)": "album",
            "Highest Quality": "quality",
        }
        sort_key = sort_key_map.get(self.sort_var.get(), "recent")
        self._songs = self.service.get_downloaded_songs(
            query=self._search_query,
            sort_by=sort_key,
        )
        self._render_content()

    def _on_search_changed(self) -> None:
        self._search_query = self.search_entry.get().strip()
        self.refresh()

    def _on_sort_changed(self, choice: str) -> None:
        self.refresh()

    def _render_content(self) -> None:
        """Render either empty state or list of downloaded songs."""
        for w in self.list_container.winfo_children():
            w.destroy()

        total_bytes = sum(s.file_size_bytes or 0 for s in self._songs)
        storage_mb = total_bytes / (1024 * 1024) if total_bytes else len(self._songs) * 8.5
        self.summary_pill.configure(text=f"{len(self._songs)} Downloaded · {storage_mb:.1f} MB")

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
            text="Songs you download from YouTube or Spotify will appear here with instant offline playback.",
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
        card = ctk.CTkFrame(
            parent,
            fg_color=theme.SURFACE,
            corner_radius=theme.RADIUS_MD,
            border_width=1,
            border_color=theme.BORDER,
        )
        card.pack(fill="x", pady=4)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=10)

        # Left: Cover icon
        cover_box = ctk.CTkFrame(
            inner,
            width=48,
            height=48,
            corner_radius=theme.RADIUS_SM,
            fg_color=theme.SURFACE_ELEVATED,
        )
        cover_box.pack(side="left", padx=(0, 14))
        cover_box.pack_propagate(False)
        ctk.CTkLabel(cover_box, text="🎵", font=ctk.CTkFont(size=22)).pack(expand=True)

        # Mid-Left: Title, Artist, Album, Bitrate
        info_box = ctk.CTkFrame(inner, fg_color="transparent")
        info_box.pack(side="left", fill="both", expand=True)

        ctk.CTkLabel(
            info_box,
            text=song.title,
            font=theme.font_subtitle(),
            text_color=theme.TEXT_PRIMARY,
            anchor="w",
        ).pack(anchor="w")

        artist_text = song.artist or "Unknown Artist"
        album_text = f" · {song.album}" if song.album else ""
        quality_text = f" · {song.quality_kbps or 320} kbps"
        size_mb = f" · {song.file_size_bytes / (1024 * 1024):.1f} MB" if song.file_size_bytes else ""
        dur_str = f" · {song.duration_seconds // 60}:{song.duration_seconds % 60:02d}" if song.duration_seconds else ""

        meta_line = f"{artist_text}{album_text}{quality_text}{dur_str}{size_mb}"
        ctk.CTkLabel(
            info_box,
            text=meta_line,
            font=theme.font_caption(),
            text_color=theme.TEXT_MUTED,
            anchor="w",
        ).pack(anchor="w", pady=(2, 0))

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
        status_badge.pack(side="left", padx=12)

        # Right Actions
        act_box = ctk.CTkFrame(inner, fg_color="transparent")
        act_box.pack(side="right")

        # Play button
        ctk.CTkButton(
            act_box,
            text="▶ Play",
            font=theme.font_caption_bold(),
            height=32,
            width=75,
            fg_color=theme.SUCCESS,
            hover_color=theme.SUCCESS_BG,
            text_color=theme.TEXT_PRIMARY,
            corner_radius=theme.RADIUS_SM,
            command=lambda p=song.file_path: self._play_song(p),
        ).pack(side="left", padx=4)

        # Open folder
        ctk.CTkButton(
            act_box,
            text="📁 Folder",
            font=theme.font_caption_bold(),
            height=32,
            width=75,
            fg_color=theme.SURFACE_ELEVATED,
            hover_color=theme.SURFACE_HOVER,
            text_color=theme.TEXT_SECONDARY,
            corner_radius=theme.RADIUS_SM,
            command=lambda p=song.file_path: self.service.open_path_in_explorer(p),
        ).pack(side="left", padx=4)

        # Delete button
        ctk.CTkButton(
            act_box,
            text="🗑️",
            font=theme.font_body(),
            height=32,
            width=36,
            fg_color=theme.SURFACE_ELEVATED,
            hover_color=theme.ERROR,
            text_color=theme.TEXT_MUTED,
            corner_radius=theme.RADIUS_SM,
            command=lambda s=song: self._confirm_delete(s),
        ).pack(side="left", padx=4)

    def _play_song(self, file_path: Optional[str]) -> None:
        """Launch the song in the system audio player."""
        ok, msg = self.service.play_audio_file(file_path)
        if not ok:
            messagebox.showwarning("Playback", msg)

    def _confirm_delete(self, song: LibrarySong) -> None:
        """Prompt confirmation modal before destructive deletion."""
        confirm = messagebox.askyesno(
            "Delete Downloaded Song",
            f"Are you sure you want to delete '{song.title}'?\n\nThis will permanently remove the downloaded audio file from your computer.",
            icon="warning",
        )
        if confirm:
            success = self.service.delete_downloaded_song(song.id, delete_physical_file=True)
            if success:
                self.refresh()
            else:
                messagebox.showerror("Error", f"Failed to delete '{song.title}'.")
